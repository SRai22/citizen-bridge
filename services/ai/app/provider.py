import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from time import monotonic
from typing import Any, cast

from openai import APIError, AsyncOpenAI
from pydantic import ValidationError

from app.config import Settings
from app.schemas import (
    HouseholdAssets,
    HouseholdProfile,
    IntakeTurn,
    Interpretation,
    Location,
    PersonProfile,
    ProviderResult,
    RemediationAction,
)

PROMPTS = Path(__file__).parent / "prompts"

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
    "Which city and state did the person live in?",
    "Were they employed or retired, and were they receiving a government pension?",
    "Who else is in the household, and did they hold a BESCOM connection, ration card, "
    "or property?",
)
MOCK_INTERPRETATION = Interpretation(
    cause="missing_legal_heir_certificate",
    explanation=(
        "The application needs a Legal Heir Certificate before the electricity account can be "
        "transferred."
    ),
    confidence=0.99,
    remediation=RemediationAction(
        action="add_task",
        workflow_id="legal_heir_certificate",
        dependency_target="bescom_transfer",
    ),
)


class AIUnavailableError(RuntimeError):
    pass


class AIProvider:
    def __init__(self, settings: Settings, client: AsyncOpenAI | None = None) -> None:
        self.settings = settings
        self.client = client
        self.intake_prompt = (PROMPTS / "intake_system.md").read_text(encoding="utf-8")
        self.rejection_prompt = (PROMPTS / "rejection_interpretation.md").read_text(
            encoding="utf-8"
        )

    async def intake(
        self, messages: Sequence[Mapping[str, str]], category_id: str
    ) -> ProviderResult:
        if self.settings.ai_mock_mode:
            user_turns = sum(message.get("role") == "user" for message in messages)
            latest = next(
                (
                    message.get("content", "")
                    for message in reversed(messages)
                    if message.get("role") == "user"
                ),
                "",
            )
            value = (
                IntakeTurn(
                    status="complete",
                    message="I have everything I need. Here's a summary of what we'll handle:",
                    profile=MOCK_PROFILE,
                )
                if user_turns >= 4
                else IntakeTurn(
                    status="in_progress",
                    message=self._mock_reply(latest, MOCK_QUESTIONS[max(0, user_turns - 1)]),
                )
            )
            return ProviderResult(value=value, model="mock")
        return await self._request(
            "intake",
            self.settings.intake_model,
            [
                {
                    "role": "system",
                    "content": f"{self.intake_prompt}\n\nCategory context: {category_id}",
                },
                *messages,
            ],
            IntakeTurn,
            self.settings.intake_input_cost_per_million,
            self.settings.intake_output_cost_per_million,
        )

    @staticmethod
    def _mock_reply(message: str, question: str) -> str:
        lowered = message.lower()
        if "just tell me" in lowered or "stop asking" in lowered:
            return f"Understood — I'll keep this direct. {question}"
        if "?" in message or lowered.startswith("why"):
            return (
                "This helps us identify the right services and avoid irrelevant steps. "
                f"{question}"
            )
        if any(word in lowered for word in ("died", "passed away", "loss")):
            return f"I'm sorry to hear that. {question}"
        if any(word in lowered for word in ("please", "kindly", "could you")):
            return f"Certainly. {question}"
        if len(message.split()) <= 3:
            return question
        return f"Thank you for that context. {question}"

    async def interpret(self, rejection_text: str, context: Mapping[str, Any]) -> ProviderResult:
        if self.settings.ai_mock_mode:
            return ProviderResult(value=MOCK_INTERPRETATION, model="mock")
        return await self._request(
            "rejection_interpretation",
            self.settings.rejection_model,
            [
                {"role": "system", "content": self.rejection_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"rejection_text": rejection_text, "context": context}, sort_keys=True
                    ),
                },
            ],
            Interpretation,
            self.settings.rejection_input_cost_per_million,
            self.settings.rejection_output_cost_per_million,
        )

    async def _request(
        self,
        request_type: str,
        model: str,
        messages: list[dict[str, str]],
        response_model: type[IntakeTurn] | type[Interpretation],
        input_cost: float,
        output_cost: float,
    ) -> ProviderResult:
        if not self.settings.openai_api_key and self.client is None:
            raise AIUnavailableError("Configure OPENAI_API_KEY or enable AI_MOCK_MODE")
        client = self.client or AsyncOpenAI(api_key=self.settings.openai_api_key)
        started = monotonic()
        try:
            completion = await client.chat.completions.create(
                model=model,
                messages=cast(Any, messages),
                response_format=cast(
                    Any,
                    {
                        "type": "json_schema",
                        "json_schema": {
                            "name": f"citizen_bridge_{request_type}",
                            "strict": True,
                            "schema": response_model.model_json_schema(),
                        },
                    },
                ),
            )
            content = completion.choices[0].message.content
            if content is None:
                raise TypeError("OpenAI returned no structured content")
            value = response_model.model_validate_json(content)
            usage = completion.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            return ProviderResult(
                value=value,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=round((monotonic() - started) * 1000),
                cost_estimate=(input_tokens * input_cost + output_tokens * output_cost) / 1_000_000,
            )
        except (
            APIError,
            OSError,
            ValidationError,
            IndexError,
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            raise AIUnavailableError("The AI service is temporarily unavailable") from exc
