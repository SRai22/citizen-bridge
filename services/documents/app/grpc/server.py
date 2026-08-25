import json
from uuid import UUID

import grpc
from contracts.generated import documents_pb2, documents_pb2_grpc
from grpc import aio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.kafka import EventPublisher
from app.models import Document
from app.schemas import AccessCreate, DocumentCreate, DocumentResponse, Requirement
from app.service import check_requirements, create_document, record_access


class DocumentServicer(documents_pb2_grpc.DocumentServiceServicer):
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], publisher: EventPublisher
    ) -> None:
        self.sessions = sessions
        self.publisher = publisher

    async def CheckRequirements(self, request, context):  # noqa: N802
        try:
            user_id = UUID(request.user_id)
            requirements = [
                Requirement(
                    type=item.document_type,
                    owner=UUID(item.subject_person_id) if item.subject_person_id else None,
                )
                for item in request.requirements
            ] or [Requirement(type=value) for value in request.document_types]
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid request")
        async with self.sessions() as session:
            results = await check_requirements(session, user_id, requirements)
        return documents_pb2.CheckRequirementsResponse(
            available_types=[item.type for item in results if item.status == "satisfied"],
            missing_types=[item.type for item in results if item.status == "missing"],
            requirements=[
                documents_pb2.RequirementResult(
                    document_type=item.type,
                    status=item.status,
                    document_id=str(item.document_id) if item.document_id else "",
                )
                for item in results
            ],
        )

    async def CreateDocument(self, request, context):  # noqa: N802
        try:
            data = json.loads(request.data_json or "{}")
            payload = DocumentCreate(
                owner_user_id=UUID(request.owner_user_id),
                document_type=request.document_type,
                proof_category=request.proof_category,
                title=request.title,
                issuer=request.issuer or None,
                provenance_type=request.provenance_type or "platform_issued",
                provenance_source=request.provenance_source or None,
                source_case_id=UUID(request.source_case_id) if request.source_case_id else None,
                source_task_id=UUID(request.source_task_id) if request.source_task_id else None,
                **data,
            )
        except (ValueError, json.JSONDecodeError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        async with self.sessions() as session:
            document = await create_document(session, self.publisher, payload)
        return _response(document)

    async def GetDocument(self, request, context):  # noqa: N802
        try:
            document_id = UUID(request.document_id)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid document ID")
        async with self.sessions() as session:
            document = await session.get(Document, document_id)
        if document is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "Document not found")
        return _response(document)

    async def RecordAccess(self, request, context):  # noqa: N802
        try:
            document_id = UUID(request.document_id)
            user_id = UUID(request.accessed_by_user_id)
            payload = AccessCreate(
                action=request.action,
                purpose=request.purpose,
                recipient=request.recipient or None,
                case_id=UUID(request.case_id) if request.case_id else None,
                task_id=UUID(request.task_id) if request.task_id else None,
            )
        except ValueError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        async with self.sessions() as session:
            document = await session.get(Document, document_id)
            if document is None:
                await context.abort(grpc.StatusCode.NOT_FOUND, "Document not found")
            await record_access(
                session,
                self.publisher,
                document,
                user_id,
                payload,
                request.accessed_by_service or None,
            )
        return documents_pb2.Empty()

    async def GetUserDocuments(self, request, context):  # noqa: N802
        try:
            user_id = UUID(request.user_id)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid user ID")
        async with self.sessions() as session:
            rows = (
                await session.scalars(
                    select(Document).where(
                        Document.owner_user_id == user_id,
                        Document.superseded_by_id.is_(None),
                    )
                )
            ).all()
        return documents_pb2.DocumentList(documents=[_response(row) for row in rows])


def _response(document: Document):
    return documents_pb2.DocumentResponse(
        document_id=str(document.id),
        owner_user_id=str(document.owner_user_id),
        document_type=document.document_type,
        verification_status=document.verification_status,
        proof_category=document.proof_category,
        title=document.title,
        document_json=DocumentResponse.model_validate(document).model_dump_json(),
    )


def create_server(
    port: int,
    sessions: async_sessionmaker[AsyncSession],
    publisher: EventPublisher,
) -> aio.Server:
    server = aio.server()
    documents_pb2_grpc.add_DocumentServiceServicer_to_server(
        DocumentServicer(sessions, publisher), server
    )
    server.add_insecure_port(f"[::]:{port}")
    return server
