import grpc
from contracts.generated import auth_pb2, auth_pb2_grpc, authority_pb2, authority_pb2_grpc


class AuthClient:
    def __init__(self, target: str) -> None:
        self.channel = grpc.aio.insecure_channel(target)
        self.stub = auth_pb2_grpc.AuthServiceStub(self.channel)

    async def validate(self, token: str):
        try:
            return await self.stub.ValidateToken(auth_pb2.ValidateTokenRequest(token=token))
        except grpc.aio.AioRpcError as exc:
            raise ConnectionError("Auth service unavailable") from exc

    async def check(self) -> None:
        await self.channel.channel_ready()

    async def close(self) -> None:
        await self.channel.close()


class AuthorityClient:
    def __init__(self, target: str) -> None:
        self.channel = grpc.aio.insecure_channel(target)
        self.stub = authority_pb2_grpc.AuthorityServiceStub(self.channel)

    async def case_users(self, case_id: str) -> list[str]:
        try:
            response = await self.stub.GetCaseUsers(
                authority_pb2.GetCaseUsersRequest(case_id=case_id)
            )
        except grpc.aio.AioRpcError as exc:
            raise ConnectionError("Authority service unavailable") from exc
        return list(response.user_ids)

    async def check(self) -> None:
        await self.channel.channel_ready()

    async def close(self) -> None:
        await self.channel.close()
