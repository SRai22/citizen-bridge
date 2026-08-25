import grpc

from . import ai_pb2 as ai__pb2


class AIServiceStub:
    def __init__(self, channel: grpc.Channel) -> None:
        service = "/citizen_bridge.ai.v1.AIService/"
        self.StartIntake = channel.unary_unary(
            service + "StartIntake",
            request_serializer=ai__pb2.StartIntakeRequest.SerializeToString,
            response_deserializer=ai__pb2.IntakeResponse.FromString,
        )
        self.SendMessage = channel.unary_unary(
            service + "SendMessage",
            request_serializer=ai__pb2.SendMessageRequest.SerializeToString,
            response_deserializer=ai__pb2.IntakeResponse.FromString,
        )
        self.InterpretRejection = channel.unary_unary(
            service + "InterpretRejection",
            request_serializer=ai__pb2.InterpretRejectionRequest.SerializeToString,
            response_deserializer=ai__pb2.InterpretRejectionResponse.FromString,
        )


class AIServiceServicer:
    async def StartIntake(self, request, context):
        raise NotImplementedError

    async def SendMessage(self, request, context):
        raise NotImplementedError

    async def InterpretRejection(self, request, context):
        raise NotImplementedError


def add_AIServiceServicer_to_server(servicer: AIServiceServicer, server) -> None:
    handlers = {
        name: grpc.unary_unary_rpc_method_handler(
            getattr(servicer, name),
            request_deserializer=getattr(ai__pb2, request_type).FromString,
            response_serializer=getattr(ai__pb2, response_type).SerializeToString,
        )
        for name, request_type, response_type in (
            ("StartIntake", "StartIntakeRequest", "IntakeResponse"),
            ("SendMessage", "SendMessageRequest", "IntakeResponse"),
            (
                "InterpretRejection",
                "InterpretRejectionRequest",
                "InterpretRejectionResponse",
            ),
        )
    }
    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "citizen_bridge.ai.v1.AIService", handlers
            ),
        )
    )
