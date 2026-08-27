from uuid import UUID, uuid4

import pytest
from contracts.generated import ai_pb2
from sqlalchemy import func, select

from app.config import settings
from app.grpc import AIService
from app.models import AIRequestLog, Conversation
from app.provider import AIProvider
from app.schemas import IntakeTurn, MarriageProfile, NewBabyProfile


def test_intake_schema_requires_nullable_profile_for_openai_strict_output() -> None:
    schema = IntakeTurn.model_json_schema()
    assert set(schema["properties"]) == set(schema["required"])


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Please continue", "Certainly."),
        ("just tell me what to do", "keep this direct"),
        ("why do you need that?", "This helps us"),
        ("my dad died last week", "I'm sorry to hear that"),
    ],
)
def test_mock_intake_adapts_to_the_citizens_style(message: str, expected: str) -> None:
    reply = AIProvider._mock_reply(message, "Which city did they live in?")
    assert expected in reply
    assert reply.endswith("Which city did they live in?")


@pytest.mark.parametrize(
    ("category_id", "user_turns", "expected"),
    [
        ("new_baby", 2, "other parent's name"),
        ("marriage", 1, "your spouse's name"),
    ],
)
@pytest.mark.asyncio
async def test_mock_intake_does_not_ask_for_authenticated_citizen_name(
    category_id: str, user_turns: int, expected: str
) -> None:
    result = await AIProvider(settings).intake(
        [{"role": "user", "content": "answer"}] * user_turns,
        category_id,
    )
    assert expected in result.value.message.lower()


def auth(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


@pytest.mark.asyncio
async def test_intake_rejects_future_scope_categories(ai_context) -> None:
    client, _, events = ai_context
    response = await client.post(
        "/api/ai/intake/start",
        json={"category_id": "address_change"},
        headers=auth(uuid4()),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Unsupported intake category: address_change"
    assert events.events == []


@pytest.mark.asyncio
async def test_mock_intake_persists_and_confirms_profile(ai_context) -> None:
    client, sessions, events = ai_context
    user_id = uuid4()
    unauthorized = await client.post(
        "/api/ai/intake/start", json={"category_id": "bereavement"}
    )
    assert unauthorized.status_code == 401

    started = await client.post(
        "/api/ai/intake/start",
        json={"category_id": "bereavement"},
        headers=auth(user_id),
    )
    assert started.status_code == 201
    assert "sorry for your loss" in started.json()["message"].lower()
    conversation_id = started.json()["conversation_id"]

    for turn in range(4):
        response = await client.post(
            f"/api/ai/intake/{conversation_id}/message",
            json={"message": f"answer {turn}"},
            headers=auth(user_id),
        )
        assert response.status_code == 200
        if turn == 0:
            assert response.json()["message"] == "What was the date of death?"
            assert response.json()["input_type"] == "date"
    assert response.json()["status"] == "complete"
    assert response.json()["profile"]["location"]["city"] == "Bengaluru"
    assert response.json()["profile"]["death_date"] == "2026-08-20"

    confirmed = await client.post(
        f"/api/ai/intake/{conversation_id}/confirm",
        json={"profile_confirmed": True},
        headers=auth(user_id),
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["profile"]["assets"]["bescom"] is True
    repeated = await client.post(
        f"/api/ai/intake/{conversation_id}/confirm",
        json={"profile_confirmed": True},
        headers=auth(user_id),
    )
    assert repeated.status_code == 409

    async with sessions() as session:
        conversation = await session.get(Conversation, UUID(conversation_id))
        assert conversation is not None
        assert conversation.status == "completed"
        assert len(conversation.messages) == 10
        assert conversation.messages[0]["role"] == "system"
        assert '"name": "Asha Rao"' in conversation.messages[0]["content"]
        assert await session.scalar(
            select(func.count()).select_from(AIRequestLog).where(
                AIRequestLog.conversation_id == conversation.id
            )
        ) == 4
    assert [event["event_type"] for event in events.events] == [
        "ai.conversation_started",
        "ai.conversation_completed",
        "ai.profile_extracted",
    ]
    assert events.events[-1]["profile_fields"] == {
        "city": "Bengaluru",
        "state": "Karnataka",
    }


@pytest.mark.parametrize(
    ("category_id", "profile_type", "expected_field", "expected_value"),
    [
        ("new_baby", NewBabyProfile, ("baby", "name"), "Anaya Rao"),
        ("marriage", MarriageProfile, ("spouse1",), "Meera Rao"),
    ],
)
@pytest.mark.asyncio
async def test_mock_intake_routes_profile_by_category(
    ai_context, category_id, profile_type, expected_field, expected_value
) -> None:
    client, _, events = ai_context
    user_id = uuid4()
    started = await client.post(
        "/api/ai/intake/start",
        json={"category_id": category_id},
        headers=auth(user_id),
    )
    conversation_id = started.json()["conversation_id"]

    for turn in range(4):
        response = await client.post(
            f"/api/ai/intake/{conversation_id}/message",
            json={"message": f"answer {turn}"},
            headers=auth(user_id),
        )

    body = response.json()
    turn = IntakeTurn.model_validate(
        {"status": body["status"], "message": body["message"], "profile": body["profile"]}
    )
    assert isinstance(turn.profile, profile_type)
    value = body["profile"]
    for field in expected_field:
        value = value[field]
    assert value == expected_value

    confirmed = await client.post(
        f"/api/ai/intake/{conversation_id}/confirm",
        json={"profile_confirmed": True},
        headers=auth(user_id),
    )
    assert confirmed.status_code == 200
    assert events.events[-1]["category_id"] == category_id
    event_profile = events.events[-1]["profile"]
    assert event_profile == (
        {"marriage": body["profile"]} if category_id == "marriage" else body["profile"]
    )


@pytest.mark.asyncio
async def test_rejection_http_and_grpc_are_available(ai_context) -> None:
    client, sessions, events = ai_context
    user_id = uuid4()
    response = await client.post(
        "/api/ai/interpret-rejection",
        json={
            "rejection_text": "Legal heir certificate required",
            "task_type": "bescom_transfer",
            "context": {"case_id": str(uuid4())},
        },
        headers=auth(user_id),
    )
    assert response.status_code == 200
    assert response.json()["remediation_actions"][0]["workflow_id"] == (
        "legal_heir_certificate"
    )

    grpc = AIService(sessions, AIProvider(settings), events)
    interpreted = await grpc.InterpretRejection(
        ai_pb2.InterpretRejectionRequest(
            task_id=str(uuid4()), rejection_text="Legal heir certificate required"
        ),
        None,
    )
    assert interpreted.remediation_steps == [
        "add_task:legal_heir_certificate:bescom_transfer"
    ]

    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(AIRequestLog)) == 2
