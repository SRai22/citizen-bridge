"""Typed schema for static government workflow definitions."""

from collections.abc import Mapping
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=100)]


class WorkflowSchemaModel(BaseModel):
    """Reject unknown YAML keys so configuration mistakes fail at startup."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ApplicabilityRule(WorkflowSchemaModel):
    """A safe equality condition against a dotted path in a household profile."""

    field: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")]
    equals: JsonValue

    def evaluate(self, profile: Mapping[str, object]) -> bool:
        value: object = profile
        for segment in self.field.split("."):
            if not isinstance(value, Mapping) or segment not in value:
                return False
            value = value[segment]
        return type(value) is type(self.equals) and value == self.equals


class DocumentRequirement(WorkflowSchemaModel):
    type: Identifier
    owner: Identifier | None = None
    description: Annotated[str, Field(min_length=1, max_length=500)] | None = None


class DocumentProduced(WorkflowSchemaModel):
    type: Identifier
    owner: Identifier | None = None
    description: Annotated[str, Field(min_length=1, max_length=500)] | None = None


class TaskDefinition(WorkflowSchemaModel):
    id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=250)]
    type: Identifier
    requires_approval: bool
    required_documents: Annotated[list[DocumentRequirement], Field(min_length=1)]
    produces_documents: Annotated[list[DocumentProduced], Field(min_length=1)]
    estimated_duration_days: Annotated[int, Field(ge=1, le=3650)]

    @model_validator(mode="after")
    def document_types_are_unique(self) -> "TaskDefinition":
        required = [document.type for document in self.required_documents]
        produced = [document.type for document in self.produces_documents]
        if len(required) != len(set(required)):
            raise ValueError(f"task '{self.id}' contains duplicate required document types")
        if len(produced) != len(set(produced)):
            raise ValueError(f"task '{self.id}' contains duplicate produced document types")
        return self


class WorkflowDefinition(WorkflowSchemaModel):
    id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=250)]
    description: Annotated[str, Field(min_length=1, max_length=1000)]
    authority: Annotated[str, Field(min_length=1, max_length=250)]
    adapter_type: Identifier
    dynamic: bool = False
    applicability_rules: Annotated[list[ApplicabilityRule], Field(min_length=1)]
    tasks: Annotated[list[TaskDefinition], Field(min_length=1)]
    inter_workflow_dependencies: list[Identifier]

    @model_validator(mode="after")
    def internal_references_are_valid(self) -> "WorkflowDefinition":
        task_ids = [task.id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError(f"workflow '{self.id}' contains duplicate task IDs")

        dependencies = self.inter_workflow_dependencies
        if len(dependencies) != len(set(dependencies)):
            raise ValueError(f"workflow '{self.id}' contains duplicate dependencies")
        if self.id in dependencies:
            raise ValueError(f"workflow '{self.id}' cannot depend on itself")
        return self

    def is_applicable(self, profile: Mapping[str, object]) -> bool:
        """Evaluate all rules with deterministic AND semantics."""
        return all(rule.evaluate(profile) for rule in self.applicability_rules)

    @property
    def required_document_types(self) -> frozenset[str]:
        return frozenset(
            document.type for task in self.tasks for document in task.required_documents
        )

    @property
    def produced_document_types(self) -> frozenset[str]:
        return frozenset(
            document.type for task in self.tasks for document in task.produces_documents
        )
