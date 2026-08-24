import grpc

from . import authority_pb2 as authority__pb2


class AuthorityServiceStub:
    def __init__(self, channel: grpc.Channel) -> None:
        service = "/citizen_bridge.authority.v1.AuthorityService/"
        self.CheckAccess = channel.unary_unary(
            service + "CheckAccess",
            request_serializer=authority__pb2.CheckAccessRequest.SerializeToString,
            response_deserializer=authority__pb2.CheckAccessResponse.FromString,
        )
        self.GetUserCases = channel.unary_unary(
            service + "GetUserCases",
            request_serializer=authority__pb2.GetUserCasesRequest.SerializeToString,
            response_deserializer=authority__pb2.CaseAccessList.FromString,
        )
        self.GrantAccess = channel.unary_unary(
            service + "GrantAccess",
            request_serializer=authority__pb2.GrantAccessRequest.SerializeToString,
            response_deserializer=authority__pb2.GrantResponse.FromString,
        )
        self.RevokeAccess = channel.unary_unary(
            service + "RevokeAccess",
            request_serializer=authority__pb2.RevokeAccessRequest.SerializeToString,
            response_deserializer=authority__pb2.RevokeResponse.FromString,
        )
        self.RegisterCaseOwner = channel.unary_unary(
            service + "RegisterCaseOwner",
            request_serializer=authority__pb2.RegisterCaseOwnerRequest.SerializeToString,
            response_deserializer=authority__pb2.GrantResponse.FromString,
        )


class AuthorityServiceServicer:
    async def CheckAccess(self, request, context):
        raise NotImplementedError

    async def GetUserCases(self, request, context):
        raise NotImplementedError

    async def GrantAccess(self, request, context):
        raise NotImplementedError

    async def RevokeAccess(self, request, context):
        raise NotImplementedError

    async def RegisterCaseOwner(self, request, context):
        raise NotImplementedError


def add_AuthorityServiceServicer_to_server(
    servicer: AuthorityServiceServicer, server
) -> None:
    handlers = {
        name: grpc.unary_unary_rpc_method_handler(
            getattr(servicer, name),
            request_deserializer=getattr(authority__pb2, request_type).FromString,
            response_serializer=getattr(
                authority__pb2, response_type
            ).SerializeToString,
        )
        for name, request_type, response_type in (
            ("CheckAccess", "CheckAccessRequest", "CheckAccessResponse"),
            ("GetUserCases", "GetUserCasesRequest", "CaseAccessList"),
            ("GrantAccess", "GrantAccessRequest", "GrantResponse"),
            ("RevokeAccess", "RevokeAccessRequest", "RevokeResponse"),
            ("RegisterCaseOwner", "RegisterCaseOwnerRequest", "GrantResponse"),
        )
    }
    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "citizen_bridge.authority.v1.AuthorityService", handlers
            ),
        )
    )
