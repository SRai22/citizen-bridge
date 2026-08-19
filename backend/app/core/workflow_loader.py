"""Load and cross-validate static workflow definitions."""

from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from yaml import YAMLError

from app.core.workflow_schema import WorkflowDefinition

DEFAULT_DEFINITIONS_DIRECTORY = Path(__file__).parent.parent / "workflows" / "definitions"


class WorkflowDefinitionError(ValueError):
    """A workflow file or the definition collection is invalid."""


class WorkflowLoader:
    """Read YAML definitions and enforce collection-level invariants."""

    def __init__(self, definitions_directory: Path | str = DEFAULT_DEFINITIONS_DIRECTORY) -> None:
        self.definitions_directory = Path(definitions_directory)

    def load_all(self) -> list[WorkflowDefinition]:
        paths = self._definition_paths()
        definitions = [self._load_file(path) for path in paths]
        self._validate_collection(definitions)
        return definitions

    def _definition_paths(self) -> list[Path]:
        if not self.definitions_directory.is_dir():
            raise WorkflowDefinitionError(
                f"Workflow definitions directory does not exist: {self.definitions_directory}"
            )
        paths = sorted(self.definitions_directory.glob("*.yaml"))
        if not paths:
            raise WorkflowDefinitionError(
                f"No workflow definition YAML files found in {self.definitions_directory}"
            )
        return paths

    def _load_file(self, path: Path) -> WorkflowDefinition:
        try:
            with path.open(encoding="utf-8") as definition_file:
                raw_definition: Any = yaml.safe_load(definition_file)
        except (OSError, YAMLError) as error:
            message = f"Could not parse workflow definition '{path}': {error}"
            raise WorkflowDefinitionError(message) from error

        if not isinstance(raw_definition, dict):
            raise WorkflowDefinitionError(
                f"Workflow definition '{path}' must contain a YAML mapping at its root"
            )
        try:
            return WorkflowDefinition.model_validate(raw_definition)
        except ValidationError as error:
            raise WorkflowDefinitionError(
                f"Invalid workflow definition '{path}': {error}"
            ) from error

    def _validate_collection(self, definitions: list[WorkflowDefinition]) -> None:
        definitions_by_id: dict[str, WorkflowDefinition] = {}
        for definition in definitions:
            if definition.id in definitions_by_id:
                raise WorkflowDefinitionError(f"Duplicate workflow ID '{definition.id}'")
            definitions_by_id[definition.id] = definition

        for definition in definitions:
            for dependency_id in definition.inter_workflow_dependencies:
                if dependency_id not in definitions_by_id:
                    raise WorkflowDefinitionError(
                        f"Workflow '{definition.id}' references unknown dependency "
                        f"'{dependency_id}'"
                    )

        dependency_graph = {
            definition.id: set(definition.inter_workflow_dependencies) for definition in definitions
        }
        try:
            TopologicalSorter(dependency_graph).prepare()
        except CycleError as error:
            cycle = " -> ".join(str(node) for node in error.args[1])
            raise WorkflowDefinitionError(
                f"Circular inter-workflow dependency detected: {cycle}"
            ) from error

        self._validate_document_references(definitions_by_id)

    @staticmethod
    def _validate_document_references(
        definitions_by_id: dict[str, WorkflowDefinition],
    ) -> None:
        for definition in definitions_by_id.values():
            required_types = definition.required_document_types
            for dependency_id in definition.inter_workflow_dependencies:
                dependency = definitions_by_id[dependency_id]
                shared_types = required_types & dependency.produced_document_types
                if not shared_types:
                    raise WorkflowDefinitionError(
                        f"Workflow '{definition.id}' depends on '{dependency_id}', but does not "
                        "require any document that dependency produces"
                    )

        producers: dict[str, set[str]] = {}
        for definition in definitions_by_id.values():
            for document_type in definition.produced_document_types:
                producers.setdefault(document_type, set()).add(definition.id)

        for definition in definitions_by_id.values():
            declared = set(definition.inter_workflow_dependencies)
            for document_type in definition.required_document_types:
                undeclared_producers = (
                    producers.get(document_type, set()) - {definition.id} - declared
                )
                if undeclared_producers:
                    producer_list = ", ".join(sorted(undeclared_producers))
                    raise WorkflowDefinitionError(
                        f"Workflow '{definition.id}' requires '{document_type}' produced by "
                        f"undeclared workflow dependency: {producer_list}"
                    )
