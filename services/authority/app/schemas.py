from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ResourceType = Literal["case", "person", "document", "household"]
DelegationScope = Literal["case", "person", "all_cases"]
DelegatedRole = Literal["coordinator", "viewer"]
Action = Literal["view", "submit", "approve", "manage", "delegate", "delete"]


class AccessResponse(BaseModel):
    allowed: bool
    role: str = ""
    permissions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class CaseAccessResponse(BaseModel):
    case_id: UUID
    role: str
    granted_at: datetime


class CaseAccessList(BaseModel):
    cases: list[CaseAccessResponse]


class GrantRequest(BaseModel):
    grantee_id: UUID
    resource_type: ResourceType
    resource_id: UUID
    role: DelegatedRole
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def future_expiry(cls, value: datetime | None) -> datetime | None:
        if value is not None and value <= datetime.now(UTC):
            raise ValueError("expires_at must be in the future")
        return value


class GrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grant_id: UUID = Field(validation_alias="id")
    grantor_id: UUID | None
    grantee_id: UUID
    resource_type: str
    resource_id: UUID
    role: str
    permissions: list[str]
    granted_at: datetime
    expires_at: datetime | None


class RevokeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class DelegationRequest(BaseModel):
    delegate_id: UUID
    scope_type: DelegationScope
    scope_id: UUID | None = None
    role: DelegatedRole
    permissions: list[Action] = Field(default_factory=list)
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> "DelegationRequest":
        if self.scope_type in {"case", "person"} and self.scope_id is None:
            raise ValueError("scope_id is required for case and person delegation")
        if self.scope_type == "all_cases" and self.scope_id is not None:
            raise ValueError("scope_id must be omitted for all_cases delegation")
        if self.valid_until is not None and self.valid_until <= datetime.now(UTC):
            raise ValueError("valid_until must be in the future")
        return self


class DelegationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    delegation_id: UUID = Field(validation_alias="id")
    delegator_id: UUID
    delegate_id: UUID
    scope_type: str
    scope_id: UUID | None
    role: str
    permissions: list[str]
    valid_from: datetime
    valid_until: datetime | None
    status: str


class DelegationRequestCreate(BaseModel):
    delegate_to_user_id: UUID
    scope_type: Literal["case"] = "case"
    scope_id: UUID
    role: Literal["coordinator"] = "coordinator"
    message: str | None = Field(default=None, max_length=500)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def future_request_expiry(cls, value: datetime | None) -> datetime | None:
        if value is not None and value <= datetime.now(UTC):
            raise ValueError("expires_at must be in the future")
        return value


class DelegationRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    delegation_request_id: UUID = Field(validation_alias="id")
    from_user_id: UUID
    to_user_id: UUID
    scope_type: str
    scope_id: UUID
    role: str
    message: str | None
    status: str
    expires_at: datetime | None
    delegation_id: UUID | None
    created_at: datetime


class CaseAccessEntry(BaseModel):
    user_id: UUID
    name: str | None = None
    role: str
    granted_at: datetime
    granted_by: UUID | None = None
