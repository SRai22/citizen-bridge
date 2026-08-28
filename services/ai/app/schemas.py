from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PersonProfile(StrictModel):
    name: str = Field(min_length=1)
    relationship: str = Field(min_length=1)
    occupation: str = Field(min_length=1)
    pension_status: Literal["active", "inactive", "none", "unknown"]


class Location(StrictModel):
    city: str = Field(min_length=1)
    state: str = Field(min_length=1)


class HouseholdAssets(StrictModel):
    bescom: bool
    ration_card: bool
    property: bool


class BereavementProfile(StrictModel):
    deceased: PersonProfile
    death_date: date
    surviving_members: list[PersonProfile]
    location: Location
    assets: HouseholdAssets


class BabyProfile(StrictModel):
    name: str = Field(min_length=1)
    dob: date
    gender: Literal["female", "male", "other", "unknown"]


class NewBabyProfile(StrictModel):
    baby: BabyProfile
    parents: list[str] = Field(min_length=2, max_length=2)
    location: Location
    birth_place: str = Field(min_length=1)
    hospital_record_uploaded: Literal[True]


class MarriageProfile(StrictModel):
    spouse1: str = Field(min_length=1)
    spouse2: str = Field(min_length=1)
    marriage_date: date
    marriage_place: str = Field(min_length=1)
    location: Location
    change_address: bool
    change_name: bool
    add_to_ration_card: bool


IntakeProfile = BereavementProfile | NewBabyProfile | MarriageProfile


class IntakeTurn(StrictModel):
    status: Literal["in_progress", "complete"]
    message: str = Field(min_length=1)
    profile: IntakeProfile | None


class RemediationAction(StrictModel):
    action: Literal["add_task"]
    workflow_id: str = Field(min_length=1)
    dependency_target: str = Field(min_length=1)


class Interpretation(StrictModel):
    cause: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    remediation: RemediationAction


class ProviderResult(BaseModel):
    value: IntakeTurn | Interpretation
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_estimate: float = 0


class StartIntakeRequest(StrictModel):
    category_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_-]+$")


class IntakeMessageRequest(StrictModel):
    message: str = Field(min_length=1, max_length=4000)


class ConfirmIntakeRequest(StrictModel):
    profile_confirmed: bool


class RejectionRequest(StrictModel):
    rejection_text: str = Field(min_length=1, max_length=10_000)
    task_type: str = Field(min_length=1, max_length=100)
    context: dict[str, Any] = Field(default_factory=dict)


class ConversationResponse(BaseModel):
    conversation_id: UUID
    message: str
    status: Literal["in_progress", "complete"]
    input_type: Literal["text", "date"] = "text"
    suggested_replies: list[str] = Field(default_factory=list)
    profile: IntakeProfile | None = None


class ConfirmedProfileResponse(BaseModel):
    profile: IntakeProfile


class InterpretationResponse(BaseModel):
    interpretation: str
    cause: str
    confidence: float
    remediation_actions: list[RemediationAction]


class MessageRecord(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime
    tokens_used: int | None = None
