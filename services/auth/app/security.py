import asyncio
import hashlib
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import bcrypt
import jwt


class InvalidTokenError(ValueError):
    pass


class TokenManager:
    def __init__(self, secret: str, access_minutes: int = 15, refresh_days: int = 7) -> None:
        self.secret = secret
        self.access_delta = timedelta(minutes=access_minutes)
        self.refresh_delta = timedelta(days=refresh_days)

    def issue_pair(self, user_id: UUID, username: str) -> tuple[str, str, datetime]:
        now = datetime.now(UTC)
        access = self._encode(user_id, username, "access", now, now + self.access_delta)
        refresh_expires = now + self.refresh_delta
        refresh = self._encode(user_id, username, "refresh", now, refresh_expires)
        return access, refresh, refresh_expires

    def decode(self, token: str, expected_type: str) -> dict[str, Any]:
        try:
            claims = jwt.decode(token, self.secret, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise InvalidTokenError("Invalid or expired token") from exc
        if claims.get("type") != expected_type or not claims.get("sub"):
            raise InvalidTokenError("Invalid token type")
        return claims

    def _encode(
        self,
        user_id: UUID,
        username: str,
        token_type: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> str:
        return jwt.encode(
            {
                "sub": str(user_id),
                "username": username,
                "iat": issued_at,
                "exp": expires_at,
                "type": token_type,
                "jti": str(uuid4()),
            },
            self.secret,
            algorithm="HS256",
        )


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class LoginRateLimiter:
    """Per-process failed-login limiter required by the MVP ticket."""

    def __init__(self, attempts: int = 5, window: timedelta = timedelta(minutes=5)) -> None:
        self.attempts = attempts
        self.window = window
        self._failures: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def is_limited(self, username: str) -> bool:
        async with self._lock:
            failures = self._recent(username)
            return len(failures) >= self.attempts

    async def record_failure(self, username: str) -> None:
        async with self._lock:
            failures = self._recent(username)
            failures.append(datetime.now(UTC))
            self._failures[username] = failures

    async def clear(self, username: str) -> None:
        async with self._lock:
            self._failures.pop(username, None)

    def _recent(self, username: str) -> deque[datetime]:
        failures = self._failures.get(username, deque())
        cutoff = datetime.now(UTC) - self.window
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if failures:
            self._failures[username] = failures
        else:
            self._failures.pop(username, None)
        return failures
