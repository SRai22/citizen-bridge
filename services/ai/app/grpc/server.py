from uuid import UUID

import grpc
from contracts.generated import ai_pb2, ai_pb2_grpc
from grpc import aio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.kafka import EventPublisher
from app.provider import AIProvider, AIUnavailableError
from app.service import interpret_rejection, send_intake_message, start_intake


class AIService(ai_pb2_grpc.AIServiceServicer):
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        provider: AIProvider,
        publisher: EventPublisher,
    ) -> None:
        self.sessions = sessions
        self.provider = provider
        self.publisher = publisher

    async def StartIntake(self, request, context):  # noqa: N802
        try:
            user_id = UUID(request.user_id)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid user ID")
        async with self.sessions() as session:
            response = await start_intake(
                session,
                self.publisher,
                user_id,
                "general",
                (
                    "mock"
                    if self.provider.settings.ai_mock_mode
                    else self.provider.settings.intake_model
                ),
            )
        return ai_pb2.IntakeResponse(
            conversation_id=str(response.conversation_id),
            message=response.message,
            ready_to_confirm=False,
        )

    async def SendMessage(self, request, context):  # noqa: N802
        try:
            conversation_id = UUID(request.conversation_id)
            async with self.sessions() as session:
                response = await send_intake_message(
                    session,
                    self.publisher,
                    self.provider,
                    conversation_id,
                    request.message,
                )
        except ValueError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        except LookupError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        except AIUnavailableError as exc:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(exc))
        return ai_pb2.IntakeResponse(
            conversation_id=str(response.conversation_id),
            message=response.message,
            ready_to_confirm=response.status == "complete",
        )

    async def InterpretRejection(self, request, context):  # noqa: N802
        try:
            async with self.sessions() as session:
                result = await interpret_rejection(
                    session,
                    self.provider,
                    request.rejection_text,
                    "unknown",
                    {"task_id": request.task_id},
                )
        except AIUnavailableError as exc:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(exc))
        return ai_pb2.InterpretRejectionResponse(
            reason=result.explanation,
            remediation_steps=[
                f"{result.remediation.action}:{result.remediation.workflow_id}:"
                f"{result.remediation.dependency_target}"
            ],
        )


def create_server(
    port: int,
    sessions: async_sessionmaker[AsyncSession],
    provider: AIProvider,
    publisher: EventPublisher,
) -> aio.Server:
    server = aio.server()
    ai_pb2_grpc.add_AIServiceServicer_to_server(
        AIService(sessions, provider, publisher), server
    )
    server.add_insecure_port(f"[::]:{port}")
    return server
