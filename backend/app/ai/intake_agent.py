"""Structured conversational intake backed by OpenAI or a deterministic demo mode."""

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from openai import APIError, AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

PROMPT_PATH = Path(__file__).parent / "prompts" / "intake_system.md"


class IntakeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PersonProfile(IntakeSchema):
    name: str = Field(min_length=1)
    relationship: str = Field(min_length=1)
    occupation: str = Field(min_length=1)
    pension_status: Literal["active", "inactive", "none", "unknown"]


class Location(IntakeSchema):
    city: str = Field(min_length=1)
    state: str = Field(min_length=1)


class HouseholdAssets(IntakeSchema):
    bescom: bool
    ration_card: bool
    property: bool


class HouseholdProfile(IntakeSchema):
    deceased: PersonProfile
    surviving_members: list[PersonProfile]
    location: Location
    assets: HouseholdAssets

    def workflow_context(self) -> dict[str, object]:
        has_spouse = any(
            member.relationship.lower() in {"spouse", "wife", "husband"}
            for member in self.surviving_members
        )
        return {
            "deceased": {
                **self.deceased.model_dump(),
                "is_deceased": True,
                "was_electricity_account_holder": self.assets.bescom,
                "was_head_of_household": self.assets.ration_card,
            },
            "surviving_spouse": {"exists": has_spouse},
            "location": self.location.model_dump(),
            "assets": self.assets.model_dump(),
        }


class IntakeTurn(IntakeSchema):
    status: Literal["in_progress", "complete"]
    message: str = Field(min_length=1)
    profile: HouseholdProfile | None


class IntakeAIUnavailableError(RuntimeError):
    """Raised when the configured AI provider cannot serve an intake turn."""


MOCK_PROFILE = HouseholdProfile(
    deceased=PersonProfile(
        name="Arun Rao",
        relationship="father",
        occupation="retired Karnataka state government employee",
        pension_status="active",
    ),
    surviving_members=[
        PersonProfile(
            name="Meera Rao",
            relationship="spouse",
            occupation="homemaker",
            pension_status="none",
        )
    ],
    location=Location(city="Bengaluru", state="Karnataka"),
    assets=HouseholdAssets(bescom=True, ration_card=True, property=False),
)

MOCK_QUESTIONS = (
    "I’m sorry for your loss. Which city and state did your father live in?",
    "Was your father employed or retired, and was he receiving a government pension?",
    "Who survives him, and was he the holder of the BESCOM connection or ration card?",
)


class IntakeAgent:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        self.client = client
        self.system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def reply(self, messages: Sequence[Mapping[str, str]]) -> IntakeTurn:
        if os.getenv("MOCK_AI", "false").lower() == "true":
            return self._mock_reply(messages)

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key and self.client is None:
            raise IntakeAIUnavailableError(
                "The intake assistant is temporarily unavailable; configure OPENAI_API_KEY "
                "or enable MOCK_AI."
            )

        client = self.client or AsyncOpenAI(api_key=api_key)
        try:
            completion = await client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                messages=cast(
                    Any,
                    [{"role": "system", "content": self.system_prompt}, *messages],
                ),
                response_format=cast(
                    Any,
                    {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "citizen_bridge_intake_turn",
                            "strict": True,
                            "schema": IntakeTurn.model_json_schema(),
                        },
                    },
                ),
            )
            content = completion.choices[0].message.content
            if content is None:
                raise TypeError("OpenAI returned no structured intake content")
            return IntakeTurn.model_validate_json(content)
        except (
            APIError,
            OSError,
            ValidationError,
            IndexError,
            TypeError,
            json.JSONDecodeError,
        ) as error:
            raise IntakeAIUnavailableError(
                "The intake assistant is temporarily unavailable. Please try again shortly."
            ) from error

    @staticmethod
    def _mock_reply(messages: Sequence[Mapping[str, str]]) -> IntakeTurn:
        user_turns = sum(message.get("role") == "user" for message in messages)
        if user_turns >= 4:
            return IntakeTurn(
                status="complete",
                message="Thank you. I have enough information to prepare your service plan.",
                profile=MOCK_PROFILE,
            )
        return IntakeTurn(
            status="in_progress",
            message=MOCK_QUESTIONS[max(0, user_turns - 1)],
            profile=None,
        )
