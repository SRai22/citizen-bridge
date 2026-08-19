"""Structured interpretation of government application rejections."""

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, cast

from openai import APIError, AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

PROMPT_PATH = Path(__file__).parent / "prompts" / "rejection_interpretation.md"


class InterpretationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RemediationAction(InterpretationSchema):
    action: Literal["add_task"]
    workflow_id: str = Field(min_length=1)
    dependency_target: str = Field(min_length=1)


class Interpretation(InterpretationSchema):
    cause: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    remediation: RemediationAction


class RejectionAIUnavailableError(RuntimeError):
    """Raised when a rejection cannot be interpreted by the configured provider."""


MOCK_INTERPRETATION = Interpretation(
    cause="missing_legal_heir_certificate",
    explanation=(
        "BESCOM requires a Legal Heir Certificate to establish the proposed transferee's "
        "succession rights before the electricity account can be transferred."
    ),
    confidence=0.99,
    remediation=RemediationAction(
        action="add_task",
        workflow_id="legal_heir_certificate",
        dependency_target="bescom_transfer",
    ),
)


class RejectionInterpreter:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        self.client = client
        self.system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def interpret(
        self,
        rejection_message: str,
        task_context: Mapping[str, Any],
    ) -> Interpretation:
        if os.getenv("MOCK_AI", "false").lower() == "true":
            return MOCK_INTERPRETATION

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key and self.client is None:
            raise RejectionAIUnavailableError(
                "Rejection analysis is temporarily unavailable; configure OPENAI_API_KEY "
                "or enable MOCK_AI."
            )

        client = self.client or AsyncOpenAI(api_key=api_key)
        try:
            completion = await client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                messages=cast(
                    Any,
                    [
                        {"role": "system", "content": self.system_prompt},
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "rejection_message": rejection_message,
                                    "task_context": task_context,
                                },
                                sort_keys=True,
                            ),
                        },
                    ],
                ),
                response_format=cast(
                    Any,
                    {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "citizen_bridge_rejection_interpretation",
                            "strict": True,
                            "schema": Interpretation.model_json_schema(),
                        },
                    },
                ),
            )
            content = completion.choices[0].message.content
            if content is None:
                raise TypeError("OpenAI returned no structured rejection interpretation")
            return Interpretation.model_validate_json(content)
        except (
            APIError,
            OSError,
            ValidationError,
            IndexError,
            TypeError,
            json.JSONDecodeError,
        ) as error:
            raise RejectionAIUnavailableError(
                "Rejection analysis is temporarily unavailable. Please try again shortly."
            ) from error
