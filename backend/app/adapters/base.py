"""Shared contracts for government service adapters."""

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.models import ExternalApplication


class AdapterStatus(StrEnum):
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    APPROVED = "approved"
    REJECTED = "rejected"
    ERROR = "error"


class AdapterResult(BaseModel):
    """Typed, immutable result returned across the adapter boundary."""

    model_config = ConfigDict(frozen=True)

    reference_id: str | None = None
    status: AdapterStatus
    message: str = Field(min_length=1)
    response_data: dict[str, Any] = Field(default_factory=dict)


class SubmissionResult(AdapterResult):
    """Result of sending an application to an authority."""


class StatusResult(AdapterResult):
    """Current authority-side status for a submitted application."""


@runtime_checkable
class GovernmentAdapter(Protocol):
    """Interface implemented by every government service integration."""

    async def submit_application(self, application: ExternalApplication) -> SubmissionResult: ...

    async def check_status(self, reference_id: str) -> StatusResult: ...

    async def get_requirements(self) -> list[str]: ...
