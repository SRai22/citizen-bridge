import grpc

from . import cases_pb2 as cases__pb2


class CaseServiceStub:
    def __init__(self, channel: grpc.Channel) -> None:
        service = "/citizen_bridge.cases.v1.CaseService/"
        self.GetCase = channel.unary_unary(
            service + "GetCase",
            request_serializer=cases__pb2.GetCaseRequest.SerializeToString,
            response_deserializer=cases__pb2.CaseResponse.FromString,
        )
        self.ListCases = channel.unary_unary(
            service + "ListCases",
            request_serializer=cases__pb2.ListCasesRequest.SerializeToString,
            response_deserializer=cases__pb2.CaseList.FromString,
        )


class CaseServiceServicer:
    async def GetCase(self, request, context):
        raise NotImplementedError

    async def ListCases(self, request, context):
        raise NotImplementedError


def add_CaseServiceServicer_to_server(servicer: CaseServiceServicer, server) -> None:
    handlers = {
        name: grpc.unary_unary_rpc_method_handler(
            getattr(servicer, name),
            request_deserializer=getattr(cases__pb2, request_type).FromString,
            response_serializer=getattr(cases__pb2, response_type).SerializeToString,
        )
        for name, request_type, response_type in (
            ("GetCase", "GetCaseRequest", "CaseResponse"),
            ("ListCases", "ListCasesRequest", "CaseList"),
        )
    }
    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "citizen_bridge.cases.v1.CaseService", handlers
            ),
        )
    )
