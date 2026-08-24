import grpc

from . import auth_pb2 as auth__pb2


class AuthServiceStub:
    def __init__(self, channel: grpc.Channel) -> None:
        self.ValidateToken = channel.unary_unary(
            "/citizen_bridge.auth.v1.AuthService/ValidateToken",
            request_serializer=auth__pb2.ValidateTokenRequest.SerializeToString,
            response_deserializer=auth__pb2.ValidateTokenResponse.FromString,
        )
        self.GetUser = channel.unary_unary(
            "/citizen_bridge.auth.v1.AuthService/GetUser",
            request_serializer=auth__pb2.GetUserRequest.SerializeToString,
            response_deserializer=auth__pb2.UserResponse.FromString,
        )
        self.GetUsers = channel.unary_unary(
            "/citizen_bridge.auth.v1.AuthService/GetUsers",
            request_serializer=auth__pb2.GetUsersRequest.SerializeToString,
            response_deserializer=auth__pb2.UsersResponse.FromString,
        )


class AuthServiceServicer:
    async def ValidateToken(self, request, context):  # noqa: N802
        raise NotImplementedError

    async def GetUser(self, request, context):  # noqa: N802
        raise NotImplementedError

    async def GetUsers(self, request, context):  # noqa: N802
        raise NotImplementedError


def add_AuthServiceServicer_to_server(servicer: AuthServiceServicer, server) -> None:
    handlers = {
        "ValidateToken": grpc.unary_unary_rpc_method_handler(
            servicer.ValidateToken,
            request_deserializer=auth__pb2.ValidateTokenRequest.FromString,
            response_serializer=auth__pb2.ValidateTokenResponse.SerializeToString,
        ),
        "GetUser": grpc.unary_unary_rpc_method_handler(
            servicer.GetUser,
            request_deserializer=auth__pb2.GetUserRequest.FromString,
            response_serializer=auth__pb2.UserResponse.SerializeToString,
        ),
        "GetUsers": grpc.unary_unary_rpc_method_handler(
            servicer.GetUsers,
            request_deserializer=auth__pb2.GetUsersRequest.FromString,
            response_serializer=auth__pb2.UsersResponse.SerializeToString,
        ),
    }
    server.add_generic_rpc_handlers(
        (grpc.method_handlers_generic_handler("citizen_bridge.auth.v1.AuthService", handlers),)
    )
