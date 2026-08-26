from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Stage(CatalogModel):
    id: Identifier
    label: str = Field(min_length=1)
    description: str = ""
    order: int = Field(ge=1)


class TaskDefinition(CatalogModel):
    id: Identifier
    name: str = Field(min_length=1)
    estimated_duration_days: int = Field(ge=1)


class ApplicabilityRule(CatalogModel):
    field: str = Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")
    equals: Any = None
    exists: bool | None = None


class EligibilityRule(CatalogModel):
    field: Identifier
    operator: Literal["eq", "lt", "lte", "gt", "gte", "in", "age_gte"]
    value: Any | None = None
    values: list[Any] = Field(default_factory=list)


class BenefitDefinition(CatalogModel):
    id: Identifier
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    authority: str = Field(min_length=1)
    amount: str = Field(min_length=1)
    eligibility_rules: list[EligibilityRule] = Field(min_length=1)
    required_documents: list[Identifier] = Field(default_factory=list)
    workflow_id: Identifier


class WorkflowDefinition(CatalogModel):
    id: Identifier
    description: str = Field(min_length=1)
    adapter_type: Identifier
    dynamic: bool = False
    applicability_rules: list[ApplicabilityRule]
    tasks: list[TaskDefinition] = Field(min_length=1)
    inter_workflow_dependencies: list[Identifier] = Field(default_factory=list)
    stages: list[Stage]
    typical_duration_days: tuple[int, int]


class ServiceDefinition(CatalogModel):
    id: Identifier
    name: str = Field(min_length=1)
    authority: str = Field(min_length=1)
    category: Identifier
    description: str = Field(min_length=1)
    typical_wait_days: tuple[int, int]
    stages_known: bool
    stages: list[Stage]
    required_profile_fields: list[Identifier]
    workflow_id: Identifier


class LifeEventCategory(CatalogModel):
    id: Identifier
    title: str = Field(min_length=1)
    subtitle: str = Field(min_length=1)
    icon: Identifier
    description: str = Field(min_length=1)
    services: list[Identifier] = Field(min_length=1)
