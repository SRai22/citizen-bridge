import re
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegistrationRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=72)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    date_of_birth: date | None = None
    city: str | None = Field(default=None, min_length=1, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, min_length=7, max_length=32)

    @field_validator("username", "name", "city", "state", "phone")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("date_of_birth")
    @classmethod
    def reject_future_birth_date(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return value

    @field_validator("password")
    @classmethod
    def enforce_bcrypt_byte_limit(cls, value: str) -> str:
        if len(value.encode()) > 72:
            raise ValueError("password must be at most 72 UTF-8 bytes")
        return value


class LoginRequest(BaseModel):
    username: str
    password: str


class PhoneOtpRequest(BaseModel):
    phone: str
    intent: Literal["login", "register"]

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if not re.fullmatch(r"[6-9]\d{9}", digits):
            raise ValueError("Enter a valid 10-digit Indian mobile number")
        return f"+91{digits}"


class PhoneOtpVerify(PhoneOtpRequest):
    code: str = Field(pattern=r"^\d{6}$")


class PhoneOtpResponse(BaseModel):
    sent: bool = True
    demo_code: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    user_id: UUID
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PhoneTokenResponse(TokenResponse):
    is_new_user: bool


class AccessTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID = Field(validation_alias="id")
    username: str
    name: str | None
    date_of_birth: date | None
    city: str | None
    state: str | None
    phone: str | None
    aadhaar_linked: bool


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    date_of_birth: date | None = None
    city: str | None = Field(default=None, min_length=1, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, min_length=7, max_length=32)

    @field_validator("name", "city", "state", "phone")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("date_of_birth")
    @classmethod
    def reject_future_birth_date(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return value


class ProfileResponse(BaseModel):
    name: str | None
    date_of_birth: date | None
    city: str | None
    state: str | None
    gender: str | None
    caste_category: str | None
    annual_income: int | None
    occupation: str | None
    education_level: str | None
    marital_status: str | None
    last_enriched_at: datetime | None


class ProfileFieldUpdate(BaseModel):
    field_name: str
    value: Any
    source: Literal["user_input"] = "user_input"


class EnrichmentField(BaseModel):
    name: str
    value: Any
    source_type: Literal[
        "user_input",
        "document_extracted",
        "intake_conversation",
        "government_verified",
    ]
    source_reference: str | None = Field(default=None, max_length=500)
    verified: bool = False
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class EnrichmentRequest(BaseModel):
    fields: list[EnrichmentField] = Field(min_length=1, max_length=10)


class ProvenanceDecision(BaseModel):
    confirmed: bool


class ProvenanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    field_name: str
    value: str
    source_type: str
    source_reference: str | None
    verified: bool
    confirmed_by_user: bool
    confirmed_at: datetime | None
    disputed_at: datetime | None
    valid_from: datetime | None
    valid_until: datetime | None
    created_at: datetime


class FamilyMemberCreate(BaseModel):
    id: UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    relationship: str = Field(min_length=1, max_length=50)
    date_of_birth: date | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=32)
    is_deceased: bool = False
    death_date: date | None = None
    source: Literal["manual", "intake"] = "manual"

    @field_validator("name", "relationship", "phone")
    @classmethod
    def strip_family_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class FamilyMemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    relationship: str | None = Field(default=None, min_length=1, max_length=50)
    date_of_birth: date | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=32)
    is_deceased: bool | None = None
    death_date: date | None = None


class FamilyMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    relationship: str
    date_of_birth: date | None
    phone: str | None
    is_deceased: bool
    death_date: date | None
    source: str
    created_at: datetime
    updated_at: datetime


class DeletionRequest(BaseModel):
    confirmation: Literal["DELETE MY ACCOUNT"]
    password: str = Field(min_length=1, max_length=72)
