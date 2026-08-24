import grpc
from contracts.generated import auth_pb2, auth_pb2_grpc
from contracts.lib.observability import grpc_metadata
from grpc import aio


class AuthClient:
    def __init__(self, target: str) -> None:
        self.channel = aio.insecure_channel(target)
        self.stub = auth_pb2_grpc.AuthServiceStub(self.channel)

    async def validate(self, token: str):
        try:
            return await self.stub.ValidateToken(
                auth_pb2.ValidateTokenRequest(token=token), metadata=grpc_metadata()
            )
        except grpc.RpcError as exc:
            raise ConnectionError("Auth service unavailable") from exc

    async def user_exists(self, user_id: str) -> bool:
        try:
            await self.stub.GetUser(
                auth_pb2.GetUserRequest(user_id=user_id), metadata=grpc_metadata()
            )
        except grpc.aio.AioRpcError as exc:
            if exc.code() == grpc.StatusCode.NOT_FOUND:
                return False
            raise ConnectionError("Auth service unavailable") from exc
        return True

    async def check(self) -> None:
        await self.validate("health-check-invalid-token")

    async def close(self) -> None:
        await self.channel.close()
