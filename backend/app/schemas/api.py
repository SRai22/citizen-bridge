"""Request schemas for the case and task API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class APIRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LifeEventCreate(APIRequestModel):
    type: str = Field(min_length=1, max_length=100)
    context: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class PersonCreate(APIRequestModel):
    name: str = Field(min_length=1, max_length=200)
    relationship: str = Field(min_length=1, max_length=100)
    role: str | None = Field(default=None, max_length=100)
    is_deceased: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)


class HouseholdProfileCreate(APIRequestModel):
    location_city: str | None = Field(default=None, max_length=100)
    location_state: str | None = Field(default=None, max_length=100)
    people: list[PersonCreate] = Field(default_factory=list)


class CaseCreate(APIRequestModel):
    life_event: LifeEventCreate
    household_profile: HouseholdProfileCreate | None = None


class TaskInputUpdate(APIRequestModel):
    input_data: dict[str, Any]
