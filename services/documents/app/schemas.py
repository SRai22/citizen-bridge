from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["identity", "certificates", "address", "income", "family"]
Verification = Literal["pending", "verified", "expired", "rejected"]
Provenance = Literal["platform_issued", "user_uploaded", "digilocker", "auto_fetched"]


class DocumentCreate(BaseModel):
    owner_user_id: UUID
    subject_person_id: UUID | None = None
    document_type: Annotated[str, Field(min_length=1, max_length=100)]
    proof_category: Category
    title: Annotated[str, Field(min_length=1, max_length=250)]
    issuer: str | None = None
    issued_at: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    verification_status: Verification = "pending"
    provenance_type: Provenance = "platform_issued"
    provenance_source: str | None = None
    source_case_id: UUID | None = None
    source_task_id: UUID | None = None
    extracted_fields: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class UploadCreate(BaseModel):
    document_type: Annotated[str, Field(min_length=1, max_length=100)]
    title: Annotated[str, Field(min_length=1, max_length=250)]
    subject_person_id: UUID | None = None
    proof_category: Category | None = None
    issuer: str | None = None
    issued_at: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    extracted_fields: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    owner_user_id: UUID
    subject_person_id: UUID | None
    document_type: str
    proof_category: str
    title: str
    issuer: str | None
    issued_at: datetime | None
    valid_from: datetime | None
    valid_until: datetime | None
    verification_status: str
    provenance_type: str
    provenance_source: str | None
    source_case_id: UUID | None
    source_task_id: UUID | None
    extracted_fields: dict
    metadata: dict = Field(validation_alias="metadata_")
    file_name: str | None
    mime_type: str | None
    file_size: int | None
    superseded_by_id: UUID | None
    created_at: datetime
    updated_at: datetime


class AccessCreate(BaseModel):
    action: Literal["viewed", "shared", "submitted", "downloaded"]
    purpose: Annotated[str, Field(min_length=1, max_length=500)]
    recipient: str | None = None
    case_id: UUID | None = None
    task_id: UUID | None = None


class AccessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    action: str
    purpose: str | None
    recipient: str | None
    accessed_by_user_id: UUID
    accessed_by_service: str | None
    case_id: UUID | None
    task_id: UUID | None
    accessed_at: datetime
    revoked_at: datetime | None = None


class Requirement(BaseModel):
    type: Annotated[str, Field(min_length=1, max_length=100)]
    owner: UUID | None = None


class RequirementsRequest(BaseModel):
    user_id: UUID
    requirements: list[Requirement]


class RequirementResult(BaseModel):
    type: str
    status: Literal["satisfied", "missing"]
    document_id: UUID | None = None


class SupersedeRequest(BaseModel):
    new_document_data: UploadCreate
