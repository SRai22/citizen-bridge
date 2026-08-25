import grpc

from . import catalog_pb2 as catalog__pb2


class CatalogServiceStub:
    def __init__(self, channel: grpc.Channel) -> None:
        service = "/citizen_bridge.catalog.v1.CatalogService/"
        self.GetWorkflowDefinition = channel.unary_unary(
            service + "GetWorkflowDefinition",
            request_serializer=catalog__pb2.WorkflowRequest.SerializeToString,
            response_deserializer=catalog__pb2.WorkflowDefinition.FromString,
        )
        self.GetServiceDefinition = channel.unary_unary(
            service + "GetServiceDefinition",
            request_serializer=catalog__pb2.ServiceRequest.SerializeToString,
            response_deserializer=catalog__pb2.ServiceDefinition.FromString,
        )
        self.ListApplicableWorkflows = channel.unary_unary(
            service + "ListApplicableWorkflows",
            request_serializer=catalog__pb2.ProfileContext.SerializeToString,
            response_deserializer=catalog__pb2.WorkflowList.FromString,
        )


class CatalogServiceServicer:
    async def GetWorkflowDefinition(self, request, context):
        raise NotImplementedError

    async def GetServiceDefinition(self, request, context):
        raise NotImplementedError

    async def ListApplicableWorkflows(self, request, context):
        raise NotImplementedError


def add_CatalogServiceServicer_to_server(
    servicer: CatalogServiceServicer, server
) -> None:
    handlers = {
        name: grpc.unary_unary_rpc_method_handler(
            getattr(servicer, name),
            request_deserializer=getattr(catalog__pb2, request_type).FromString,
            response_serializer=getattr(catalog__pb2, response_type).SerializeToString,
        )
        for name, request_type, response_type in (
            ("GetWorkflowDefinition", "WorkflowRequest", "WorkflowDefinition"),
            ("GetServiceDefinition", "ServiceRequest", "ServiceDefinition"),
            ("ListApplicableWorkflows", "ProfileContext", "WorkflowList"),
        )
    }
    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "citizen_bridge.catalog.v1.CatalogService", handlers
            ),
        )
    )
