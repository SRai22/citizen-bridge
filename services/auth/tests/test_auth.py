import bcrypt
import pytest
from contracts.generated import auth_pb2
from sqlalchemy import select

from app.api import login_limiter, tokens
from app.grpc.server import AuthServicer
from app.models import User

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
