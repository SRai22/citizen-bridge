from uuid import UUID

import grpc
from contracts.generated import auth_pb2, auth_pb2_grpc
from grpc import aio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import User
from app.security import InvalidTokenError, TokenManager


class AuthServicer(auth_pb2_grpc.AuthServiceServicer):
    def __init__(self, sessions: async_sessionmaker[AsyncSession], tokens: TokenManager) -> None:
        self.sessions = sessions
        self.tokens = tokens

    async def ValidateToken(self, request, context):  # noqa: N802
        try:
            claims = self.tokens.decode(request.token, "access")
            user_id = UUID(claims["sub"])
        except (InvalidTokenError, ValueError):
            return auth_pb2.ValidateTokenResponse(valid=False)
        async with self.sessions() as session:
            user = await session.get(User, user_id)
        if user is None or not user.is_active:
            return auth_pb2.ValidateTokenResponse(valid=False)
        return auth_pb2.ValidateTokenResponse(
            valid=True, user_id=str(user.id), username=user.username
        )

    async def GetUser(self, request, context):  # noqa: N802
        try:
            user_id = UUID(request.user_id)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid user ID")
        async with self.sessions() as session:
            user = await session.get(User, user_id)
        if user is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "User not found")
        return _user_response(user)

    async def GetUsers(self, request, context):  # noqa: N802
        try:
            user_ids = [UUID(value) for value in request.user_ids]
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid user ID")
        async with self.sessions() as session:
            users = (await session.scalars(select(User).where(User.id.in_(user_ids)))).all()
        by_id = {user.id: user for user in users}
        return auth_pb2.UsersResponse(
            users=[_user_response(by_id[user_id]) for user_id in user_ids if user_id in by_id]
        )


def _user_response(user: User):
    return auth_pb2.UserResponse(
        user_id=str(user.id), username=user.username, name=user.name or "", city=user.city or ""
    )


def create_server(
    port: int,
    sessions: async_sessionmaker[AsyncSession],
    tokens: TokenManager,
) -> aio.Server:
    server = aio.server()
    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthServicer(sessions, tokens), server)
    server.add_insecure_port(f"[::]:{port}")
    return server
