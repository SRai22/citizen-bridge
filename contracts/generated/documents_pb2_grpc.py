import grpc

from . import documents_pb2 as documents__pb2


class DocumentServiceStub:
    def __init__(self, channel: grpc.Channel) -> None:
        service = "/citizen_bridge.documents.v1.DocumentService/"
        for name, request, response in (
            ("CheckRequirements", "CheckRequirementsRequest", "CheckRequirementsResponse"),
            ("CreateDocument", "CreateDocumentRequest", "DocumentResponse"),
            ("GetDocument", "GetDocumentRequest", "DocumentResponse"),
            ("RecordAccess", "RecordAccessRequest", "Empty"),
            ("GetUserDocuments", "GetUserDocumentsRequest", "DocumentList"),
        ):
            setattr(
                self,
                name,
                channel.unary_unary(
                    service + name,
                    request_serializer=getattr(documents__pb2, request).SerializeToString,
                    response_deserializer=getattr(documents__pb2, response).FromString,
                ),
            )


class DocumentServiceServicer:
    async def CheckRequirements(self, request, context):
        raise NotImplementedError

    async def CreateDocument(self, request, context):
        raise NotImplementedError

    async def GetDocument(self, request, context):
        raise NotImplementedError

    async def RecordAccess(self, request, context):
        raise NotImplementedError

    async def GetUserDocuments(self, request, context):
        raise NotImplementedError


def add_DocumentServiceServicer_to_server(servicer: DocumentServiceServicer, server) -> None:
    handlers = {
        name: grpc.unary_unary_rpc_method_handler(
            getattr(servicer, name),
            request_deserializer=getattr(documents__pb2, request).FromString,
            response_serializer=getattr(documents__pb2, response).SerializeToString,
        )
        for name, request, response in (
            ("CheckRequirements", "CheckRequirementsRequest", "CheckRequirementsResponse"),
            ("CreateDocument", "CreateDocumentRequest", "DocumentResponse"),
            ("GetDocument", "GetDocumentRequest", "DocumentResponse"),
            ("RecordAccess", "RecordAccessRequest", "Empty"),
            ("GetUserDocuments", "GetUserDocumentsRequest", "DocumentList"),
        )
    }
    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "citizen_bridge.documents.v1.DocumentService", handlers
            ),
        )
    )
