import bcrypt
import pytest
from contracts.generated import auth_pb2
from sqlalchemy import select

from app.api import login_limiter, tokens
from app.grpc.server import AuthServicer
from app.models import User
from app.profile import fields_from_event

REGISTRATION = {
    "username": "asha",
    "password": "correct-horse",
    "name": "Asha Rao",
    "date_of_birth": "1990-04-12",
    "city": "Bengaluru",
    "state": "Karnataka",
}


@pytest.mark.asyncio
async def test_auth_session_lifecycle(api_context) -> None:
    client, publisher, sessions = api_context

    registered = await client.post("/api/auth/register", json=REGISTRATION)
    assert registered.status_code == 201
    issued = registered.json()
    assert issued["token_type"] == "bearer"
    assert publisher.events[0]["event_type"] == "user.registered"

    profile = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {issued['access_token']}"}
    )
    assert profile.status_code == 200
    assert profile.json()["username"] == "asha"

    duplicate = await client.post("/api/auth/register", json=REGISTRATION)
    assert duplicate.status_code == 409
    invalid = await client.post(
        "/api/auth/login", json={"username": "asha", "password": "wrong-pass"}
    )
    assert invalid.status_code == 401

    logged_in = await client.post(
        "/api/auth/login",
        json={"username": "asha", "password": REGISTRATION["password"]},
    )
    assert logged_in.status_code == 200
    assert publisher.events[-1]["event_type"] == "user.logged_in"

    original_refresh = logged_in.json()["refresh_token"]
    refreshed = await client.post("/api/auth/refresh", json={"refresh_token": original_refresh})
    assert refreshed.status_code == 200
    reused = await client.post("/api/auth/refresh", json={"refresh_token": original_refresh})
    assert reused.status_code == 401

    access = refreshed.json()["access_token"]
    logout = await client.post("/api/auth/logout", headers={"Authorization": f"Bearer {access}"})
    assert logout.status_code == 204
    after_logout = await client.post(
        "/api/auth/refresh", json={"refresh_token": refreshed.json()["refresh_token"]}
    )
    assert after_logout.status_code == 401

    async with sessions() as session:
        user = await session.scalar(select(User).where(User.username == "asha"))
        assert user is not None
        assert bcrypt.checkpw(REGISTRATION["password"].encode(), user.password_hash.encode())


@pytest.mark.asyncio
async def test_phone_registration_can_resume_profile_completion(api_context) -> None:
    client, _, _ = api_context

    registered = await client.post(
        "/api/auth/register",
        json={
            "username": "phone_9876543210",
            "password": "generated-secret",
            "phone": "+919876543210",
        },
    )
    assert registered.status_code == 201
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    partial = await client.get("/api/auth/me", headers=headers)
    assert partial.status_code == 200
    assert partial.json()["phone"] == "+919876543210"
    assert partial.json()["name"] is None

    completed = await client.patch(
        "/api/auth/me",
        headers=headers,
        json={
            "name": "Asha Rao",
            "date_of_birth": "1990-04-12",
            "city": "Bengaluru",
            "state": "Karnataka",
        },
    )
    assert completed.status_code == 200
    assert completed.json()["name"] == "Asha Rao"
    assert completed.json()["date_of_birth"] == "1990-04-12"


@pytest.mark.asyncio
async def test_phone_otp_registers_and_then_logs_in(api_context) -> None:
    client, publisher, _ = api_context
    phone = "+919876543210"

    requested = await client.post(
        "/api/auth/phone/request", json={"phone": phone, "intent": "register"}
    )
    assert requested.status_code == 200
    assert requested.json()["demo_code"] == "123456"

    invalid = await client.post(
        "/api/auth/phone/verify",
        json={"phone": phone, "intent": "register", "code": "000000"},
    )
    assert invalid.status_code == 401

    registered = await client.post(
        "/api/auth/phone/verify",
        json={"phone": phone, "intent": "register", "code": "123456"},
    )
    assert registered.status_code == 200
    assert registered.json()["is_new_user"] is True
    assert publisher.events[-1]["event_type"] == "user.registered"

    duplicate = await client.post(
        "/api/auth/phone/request", json={"phone": phone, "intent": "register"}
    )
    assert duplicate.status_code == 200
    logged_in = await client.post(
        "/api/auth/phone/verify",
        json={"phone": phone, "intent": "login", "code": "123456"},
    )
    assert logged_in.status_code == 200
    assert logged_in.json()["is_new_user"] is False
    assert publisher.events[-1]["event_type"] == "user.logged_in"


@pytest.mark.asyncio
async def test_progressive_profile_enrichment_and_provenance(api_context) -> None:
    client, publisher, _ = api_context
    registered = await client.post("/api/auth/register", json=REGISTRATION)
    user_id = registered.json()["user_id"]
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    profile = await client.get("/api/auth/me/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["completeness_percent"] == 40
    assert "annual_income" in profile.json()["missing_fields"]
    assert profile.json()["enrichment_suggestions"][0]["reason"].startswith("Required for")

    updated = await client.patch(
        "/api/auth/me/profile",
        headers=headers,
        json={"field_name": "annual_income", "value": 350000},
    )
    assert updated.status_code == 200
    assert updated.json()["profile"]["annual_income"] == 350000
    assert updated.json()["completeness_percent"] == 50
    assert publisher.events[-1]["changed_fields"] == ["annual_income"]

    history = await client.get("/api/auth/me/profile/annual_income/provenance", headers=headers)
    assert history.status_code == 200
    assert history.json()["history"][0]["source_type"] == "user_input"
    assert history.json()["history"][0]["confirmed_by_user"] is True

    unauthorized = await client.post(
        f"/api/auth/users/{user_id}/enrich",
        json={
            "fields": [
                {
                    "name": "occupation",
                    "value": "Teacher",
                    "source_type": "document_extracted",
                }
            ]
        },
    )
    assert unauthorized.status_code == 401
    enriched = await client.post(
        f"/api/auth/users/{user_id}/enrich",
        headers={"X-Internal-Service-Token": "test-internal-token"},
        json={
            "fields": [
                {
                    "name": "occupation",
                    "value": "Teacher",
                    "source_type": "document_extracted",
                    "source_reference": "Employment Certificate 2026",
                    "verified": True,
                }
            ]
        },
    )
    assert enriched.status_code == 200
    history = await client.get("/api/auth/me/profile/occupation/provenance", headers=headers)
    record = history.json()["history"][0]
    assert record["source_reference"] == "Employment Certificate 2026"
    assert record["confirmed_by_user"] is False

    disputed = await client.patch(
        f"/api/auth/me/profile/occupation/provenance/{record['id']}",
        headers=headers,
        json={"confirmed": False},
    )
    assert disputed.status_code == 200
    assert disputed.json()["disputed_at"] is not None

    parsed = fields_from_event(
        {
            "event_type": "document.verified",
            "owner_user_id": user_id,
            "document_type": "income_certificate",
            "extracted_fields": {"income": 425000},
        }
    )
    assert parsed is not None
    assert parsed[1][0].name == "annual_income"


@pytest.mark.asyncio
async def test_login_rate_limit(api_context) -> None:
    client, _, _ = api_context
    await login_limiter.clear("missing")
    for _ in range(5):
        response = await client.post(
            "/api/auth/login", json={"username": "missing", "password": "not-correct"}
        )
        assert response.status_code == 401
    limited = await client.post(
        "/api/auth/login", json={"username": "missing", "password": "not-correct"}
    )
    assert limited.status_code == 429
    await login_limiter.clear("missing")


@pytest.mark.asyncio
async def test_family_member_lifecycle_is_user_scoped(api_context) -> None:
    client, _, _ = api_context
    registered = await client.post("/api/auth/register", json=REGISTRATION)
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    created = await client.post(
        "/api/auth/me/family",
        headers=headers,
        json={"name": "Kamala Devi", "relationship": "mother", "source": "manual"},
    )
    assert created.status_code == 201, created.text
    member_id = created.json()["id"]
    assert (await client.get("/api/auth/me/family", headers=headers)).json()[0]["name"] == (
        "Kamala Devi"
    )

    updated = await client.patch(
        f"/api/auth/me/family/{member_id}",
        headers=headers,
        json={"date_of_birth": "1960-02-03"},
    )
    assert updated.json()["date_of_birth"] == "1960-02-03"
    assert (
        await client.delete(f"/api/auth/me/family/{member_id}", headers=headers)
    ).status_code == (204)
    assert (await client.get("/api/auth/me/family", headers=headers)).json() == []


@pytest.mark.asyncio
async def test_data_export_and_deletion_cooling_off(api_context) -> None:
    client, publisher, _ = api_context
    registered = await client.post("/api/auth/register", json=REGISTRATION)
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    created = await client.post("/api/auth/me/export", headers=headers)
    assert created.status_code == 202
    export_id = created.json()["export_id"]
    status_response = await client.get(f"/api/auth/me/export/{export_id}", headers=headers)
    assert status_response.json()["status"] == "ready"
    downloaded = await client.get(f"/api/auth/me/export/{export_id}/download", headers=headers)
    assert downloaded.json()["profile"]["username"] == "asha"

    invalid = await client.post(
        "/api/auth/me/delete",
        headers=headers,
        json={"confirmation": "DELETE MY ACCOUNT", "password": "wrong-pass"},
    )
    assert invalid.status_code == 401
    scheduled = await client.post(
        "/api/auth/me/delete",
        headers=headers,
        json={
            "confirmation": "DELETE MY ACCOUNT",
            "password": REGISTRATION["password"],
        },
    )
    assert scheduled.json()["status"] == "cooling_off"
    assert publisher.events[-1]["event_type"] == "user.deletion_scheduled"
    assert (await client.post("/api/auth/me/delete/cancel", headers=headers)).json() == {
        "cancelled": True,
        "account_active": True,
    }


class AbortContext:
    async def abort(self, code, detail) -> None:
        raise RuntimeError((code, detail))


@pytest.mark.asyncio
async def test_grpc_validates_access_token(api_context) -> None:
    client, _, sessions = api_context
    registered = await client.post("/api/auth/register", json=REGISTRATION)
    servicer = AuthServicer(sessions, tokens)

    valid = await servicer.ValidateToken(
        auth_pb2.ValidateTokenRequest(token=registered.json()["access_token"]),
        AbortContext(),
    )
    invalid = await servicer.ValidateToken(
        auth_pb2.ValidateTokenRequest(token="invalid"), AbortContext()
    )
    user = await servicer.GetUser(
        auth_pb2.GetUserRequest(user_id=registered.json()["user_id"]), AbortContext()
    )

    assert valid.valid is True
    assert valid.username == "asha"
    assert invalid.valid is False
    assert user.name == "Asha Rao"
