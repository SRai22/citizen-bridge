from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotificationCreate(BaseModel):
    user_id: UUID
    notification_type: str = Field(min_length=1, max_length=50)
    priority: Literal["urgent", "normal", "low"] = "normal"
    title: str = Field(min_length=1, max_length=250)
    body: str = Field(min_length=1, max_length=1000)
    data: dict = Field(default_factory=dict)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    notification_type: str
    priority: str
    title: str
    body: str
    data: dict
    read: bool
    read_at: datetime | None
    created_at: datetime


class PreferencePatch(BaseModel):
    push_enabled: bool | None = None
    digest_enabled: bool | None = None
    digest_day: Literal[
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
    ] | None = None
    urgent_push: bool | None = None
    categories: dict[str, bool] | None = None


class PreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    push_enabled: bool
    digest_enabled: bool
    digest_day: str
    urgent_push: bool
    categories: dict
    updated_at: datetime
