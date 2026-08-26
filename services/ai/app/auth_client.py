import grpc
from contracts.generated import auth_pb2, auth_pb2_grpc


class AuthClient:
    def __init__(self, target: str) -> None:
        self.channel = grpc.aio.insecure_channel(target)
        self.stub = auth_pb2_grpc.AuthServiceStub(self.channel)

    async def validate(self, token: str):
        try:
            return await self.stub.ValidateToken(auth_pb2.ValidateTokenRequest(token=token))
        except grpc.aio.AioRpcError as exc:
            raise ConnectionError("Auth service unavailable") from exc

    async def get_user(self, user_id: str):
        try:
            return await self.stub.GetUser(auth_pb2.GetUserRequest(user_id=user_id))
        except grpc.aio.AioRpcError as exc:
            raise ConnectionError("Auth service unavailable") from exc

    async def check(self) -> None:
        await self.channel.channel_ready()

    async def close(self) -> None:
        await self.channel.close()
