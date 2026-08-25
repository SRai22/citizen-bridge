from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from app.schemas import LifeEventCategory, ServiceDefinition, WorkflowDefinition


class Catalog:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.reload()

    def reload(self) -> None:
        categories = _load(self.data_dir / "categories.yaml", "categories")
        services = _load(self.data_dir / "services.yaml", "services")
        workflows = _load(self.data_dir / "workflows.yaml", "workflows")
        self.categories = _index(LifeEventCategory, categories)
        self.services = _index(ServiceDefinition, services)
        self.workflows = _index(WorkflowDefinition, workflows)
        self._validate_references()

    async def check(self) -> None:
        if not self.categories or not self.services or not self.workflows:
            raise RuntimeError("Catalog data is empty")

    def list_categories(self) -> list[dict[str, Any]]:
        return [
            {
                **category.model_dump(exclude={"services"}),
                "service_count": len(category.services),
            }
            for category in self.categories.values()
        ]

    def category(self, category_id: str) -> dict[str, Any] | None:
        category = self.categories.get(category_id)
        if category is None:
            return None
        return {
            **category.model_dump(exclude={"services"}),
            "services": [
                self.services[service_id].model_dump(
                    include={"id", "name", "authority", "typical_wait_days"}
                )
                for service_id in category.services
            ],
        }

    def list_services(self, category: str | None = None, search: str | None = None) -> list[dict]:
        matches = self.services.values()
        if category:
            matches = (service for service in matches if service.category == category)
        if search:
            query = search.casefold().strip()
            matches = (
                service
                for service in matches
                if query
                in " ".join(
                    (service.name, service.description, service.category, service.authority)
                ).casefold()
            )
        fields = {"id", "name", "authority", "category", "typical_wait_days", "stages_known"}
        return [service.model_dump(include=fields) for service in matches]

    def applicable_workflows(self, profile: Mapping[str, object]) -> list[WorkflowDefinition]:
        applicable = [
            workflow
            for workflow in self.workflows.values()
            if not workflow.dynamic
            and all(
                _matches(profile, rule.field, rule.equals)
                for rule in workflow.applicability_rules
            )
        ]
        active_ids = {workflow.id for workflow in applicable}
        for workflow in applicable:
            missing = set(workflow.inter_workflow_dependencies) - active_ids
            if missing:
                raise ValueError(
                    f"Workflow '{workflow.id}' requires inactive workflow(s): "
                    + ", ".join(sorted(missing))
                )
        return applicable

    def _validate_references(self) -> None:
        referenced_services = {
            service_id for category in self.categories.values() for service_id in category.services
        }
        missing_services = referenced_services - self.services.keys()
        missing_workflows = {
            service.workflow_id for service in self.services.values()
        } - self.workflows.keys()
        missing_dependencies = {
            dependency
            for workflow in self.workflows.values()
            for dependency in workflow.inter_workflow_dependencies
        } - self.workflows.keys()
        if missing_services or missing_workflows or missing_dependencies:
            raise ValueError(
                "Invalid catalog references: "
                f"services={sorted(missing_services)}, workflows={sorted(missing_workflows)}, "
                f"dependencies={sorted(missing_dependencies)}"
            )


def _load(path: Path, key: str) -> Any:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict) or key not in data:
        raise ValueError(f"{path} must contain '{key}'")
    return data[key]


def _index(model, values: list[dict]) -> dict:
    items = [model.model_validate(value) for value in values]
    indexed = {item.id: item for item in items}
    if len(indexed) != len(items):
        raise ValueError(f"Duplicate {model.__name__} ID")
    return indexed


def _matches(profile: Mapping[str, object], field: str, expected: object) -> bool:
    value: object = profile
    for segment in field.split("."):
        if not isinstance(value, Mapping) or segment not in value:
            return False
        value = value[segment]
    return type(value) is type(expected) and value == expected
