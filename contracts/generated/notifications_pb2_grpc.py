import grpc

from . import notifications_pb2 as notifications__pb2


class NotificationServiceStub:
    def __init__(self, channel: grpc.Channel) -> None:
        service = "/citizen_bridge.notifications.v1.NotificationService/"
        self.CreateNotification = channel.unary_unary(
            service + "CreateNotification",
            request_serializer=notifications__pb2.CreateNotificationRequest.SerializeToString,
            response_deserializer=notifications__pb2.NotificationResponse.FromString,
        )
        self.MarkRead = channel.unary_unary(
            service + "MarkRead",
            request_serializer=notifications__pb2.MarkReadRequest.SerializeToString,
            response_deserializer=notifications__pb2.NotificationResponse.FromString,
        )


class NotificationServiceServicer:
    async def CreateNotification(self, request, context):
        raise NotImplementedError

    async def MarkRead(self, request, context):
        raise NotImplementedError


def add_NotificationServiceServicer_to_server(servicer: NotificationServiceServicer, server) -> None:
    handlers = {
        name: grpc.unary_unary_rpc_method_handler(
            getattr(servicer, name),
            request_deserializer=getattr(notifications__pb2, request).FromString,
            response_serializer=notifications__pb2.NotificationResponse.SerializeToString,
        )
        for name, request in (
            ("CreateNotification", "CreateNotificationRequest"),
            ("MarkRead", "MarkReadRequest"),
        )
    }
    server.add_generic_rpc_handlers(
        (
            grpc.method_handlers_generic_handler(
                "citizen_bridge.notifications.v1.NotificationService", handlers
            ),
        )
    )
