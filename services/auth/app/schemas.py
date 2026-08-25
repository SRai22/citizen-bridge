from datetime import date
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


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    user_id: UUID
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


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
