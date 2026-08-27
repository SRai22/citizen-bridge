import base64
import hashlib
import hmac
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID

from contracts.lib.observability import reset_user_id, set_user_id
from cryptography.fernet import Fernet, InvalidToken
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth_client import AuthClient
from app.config import settings
from app.db import get_session
from app.kafka import EventPublisher
from app.models import Document, DocumentAccessLog
from app.schemas import (
    AccessCreate,
    AccessResponse,
    Category,
    DocumentCreate,
    DocumentResponse,
    RequirementsRequest,
    SupersedeRequest,
    UploadCreate,
)
from app.service import (
    check_requirements,
    create_document,
    proof_category,
    record_access,
    supersede_document,
)

router = APIRouter(prefix="/api/docs", tags=["documents"])
internal_router = APIRouter(prefix="/internal", include_in_schema=False)
bearer = HTTPBearer(auto_error=False)
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def auth_client(request: Request) -> AuthClient:
    return request.app.state.auth_client


def publisher(request: Request) -> EventPublisher:
    return request.app.state.publisher


AuthDep = Annotated[AuthClient, Depends(auth_client)]
PublisherDep = Annotated[EventPublisher, Depends(publisher)]


async def current_user(credentials: CredentialsDep, auth: AuthDep) -> AsyncIterator[UUID]:
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    try:
        validation = await auth.validate(credentials.credentials)
    except ConnectionError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    if not validation.valid:
        raise _unauthorized("Invalid or expired token")
    try:
        user_id = UUID(validation.user_id)
    except ValueError as exc:
        raise _unauthorized("Invalid token subject") from exc
    token = set_user_id(str(user_id))
    try:
        yield user_id
    finally:
        reset_user_id(token)


UserDep = Annotated[UUID, Depends(current_user)]
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}


@router.get("")
async def documents(
    user_id: UserDep,
    session: SessionDep,
    category: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> dict:
    query = select(Document).where(
        Document.owner_user_id == user_id, Document.superseded_by_id.is_(None)
    )
    if category:
        query = query.where(Document.proof_category == category)
    if status_filter:
        query = query.where(Document.verification_status == status_filter)
    rows = (await session.scalars(query.order_by(Document.created_at.desc()))).all()
    grouped = {key: [] for key in ("identity", "certificates", "address", "income", "family")}
    for document in rows:
        grouped.setdefault(document.proof_category, []).append(
            DocumentResponse.model_validate(document).model_dump()
        )
    return {"documents_by_category": grouped}


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create(
    payload: DocumentCreate,
    user_id: UserDep,
    session: SessionDep,
    events: PublisherDep,
) -> Document:
    if payload.owner_user_id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot create another user's document")
    return await create_document(session, events, payload)


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload(
    payload: UploadCreate,
    user_id: UserDep,
    session: SessionDep,
    events: PublisherDep,
) -> Document:
    values = payload.model_dump()
    category = values.pop("proof_category") or proof_category(payload.document_type)
    return await create_document(
        session,
        events,
        DocumentCreate(
            owner_user_id=user_id,
            proof_category=category,
            provenance_type="user_uploaded",
            provenance_source="Uploaded by user",
            **values,
        ),
    )


@router.post("/upload-file", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    user_id: UserDep,
    session: SessionDep,
    events: PublisherDep,
    file: Annotated[UploadFile, File()],
    document_type: Annotated[str, Form(min_length=1, max_length=100)],
    title: Annotated[str, Form(min_length=1, max_length=250)],
    proof_category_value: Annotated[Category | None, Form(alias="proof_category")] = None,
    issuer: Annotated[str | None, Form()] = None,
    valid_until: Annotated[datetime | None, Form()] = None,
    source: Annotated[Literal["local", "google_drive"], Form()] = "local",
) -> Document:
    if file.content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Upload a PDF, JPEG, PNG, or WebP image"
        )
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Documents must be 10 MB or smaller"
        )
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The selected file is empty")
    if not _has_valid_signature(file.content_type, content):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "The file contents do not match the selected file type",
        )
    document = await create_document(
        session,
        events,
        DocumentCreate(
            owner_user_id=user_id,
            document_type=document_type,
            proof_category=proof_category_value or proof_category(document_type),
            title=title,
            issuer=issuer or None,
            valid_until=valid_until,
            provenance_type="user_uploaded",
            provenance_source=(
                "Imported from Google Drive"
                if source == "google_drive"
                else "Uploaded from this device"
            ),
            metadata={"upload_source": source},
        ),
    )
    document.file_name = (file.filename or title)[:255]
    document.mime_type = file.content_type
    document.file_size = len(content)
    document.file_content = _cipher().encrypt(content)
    await session.commit()
    await session.refresh(document)
    return document


@router.get("/{document_id}/download")
async def download(
    document_id: UUID,
    user_id: UserDep,
    session: SessionDep,
    events: PublisherDep,
) -> Response:
    document = await _owned_document(session, document_id, user_id)
    if document.file_content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This document has no uploaded file")
    filename = quote(document.file_name or document.title)
    try:
        content = _cipher().decrypt(document.file_content)
    except InvalidToken as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "The document file could not be decrypted",
        ) from exc
    await record_access(
        session,
        events,
        document,
        user_id,
        AccessCreate(action="downloaded", purpose="Downloaded document file"),
    )
    return Response(
        content,
        media_type=document.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/check-requirements")
async def requirements(payload: RequirementsRequest, user_id: UserDep, session: SessionDep) -> dict:
    if payload.user_id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot inspect another user's documents")
    results = await check_requirements(session, user_id, payload.requirements)
    return {"requirements": [result.model_dump() for result in results]}


@router.get("/shares")
async def active_shares(user_id: UserDep, session: SessionDep) -> dict:
    rows = (
        await session.execute(
            select(DocumentAccessLog, Document)
            .join(Document, Document.id == DocumentAccessLog.document_id)
            .where(
                Document.owner_user_id == user_id,
                DocumentAccessLog.action == "shared",
                DocumentAccessLog.revoked_at.is_(None),
            )
            .order_by(DocumentAccessLog.accessed_at.desc())
        )
    ).all()
    return {
        "active_shares": [
            {
                "share_id": share.id,
                "document_id": document.id,
                "document_title": document.title,
                "shared_with": share.recipient,
                "purpose": share.purpose,
                "shared_at": share.accessed_at,
                "case_id": share.case_id,
                "task_id": share.task_id,
            }
            for share, document in rows
        ]
    }


@router.post("/shares/{share_id}/revoke")
async def revoke_share(
    share_id: UUID, user_id: UserDep, session: SessionDep, events: PublisherDep
) -> dict:
    share = await session.scalar(
        select(DocumentAccessLog)
        .join(Document, Document.id == DocumentAccessLog.document_id)
        .where(
            DocumentAccessLog.id == share_id,
            DocumentAccessLog.action == "shared",
            Document.owner_user_id == user_id,
        )
    )
    if share is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Active share not found")
    if share.revoked_at is None:
        share.revoked_at = datetime.now(UTC)
        await session.commit()
        await events.publish(
            {
                "event_type": "document.share_revoked",
                "user_id": str(user_id),
                "share_id": str(share.id),
                "document_id": str(share.document_id),
                "timestamp": share.revoked_at.isoformat(),
            }
        )
    return {
        "revoked": True,
        "note": "This does not delete copies already received by the government body.",
    }


@router.get("/{document_id}")
async def detail(
    document_id: UUID,
    user_id: UserDep,
    session: SessionDep,
    events: PublisherDep,
) -> dict:
    document = await _owned_document(session, document_id, user_id, with_accesses=True)
    await record_access(
        session,
        events,
        document,
        user_id,
        AccessCreate(action="viewed", purpose="Viewed document details"),
    )
    await session.refresh(document, ["accesses"])
    return {
        **DocumentResponse.model_validate(document).model_dump(),
        "usage_history": [
            AccessResponse.model_validate(item).model_dump() for item in document.accesses
        ],
    }


@router.get("/{document_id}/access-log")
async def access_log(document_id: UUID, user_id: UserDep, session: SessionDep) -> dict:
    await _owned_document(session, document_id, user_id)
    rows = (
        await session.scalars(
            select(DocumentAccessLog)
            .where(DocumentAccessLog.document_id == document_id)
            .order_by(DocumentAccessLog.accessed_at.desc())
        )
    ).all()
    return {"accesses": [AccessResponse.model_validate(item).model_dump() for item in rows]}


@router.post("/{document_id}/access", status_code=status.HTTP_201_CREATED)
async def access(
    document_id: UUID,
    payload: AccessCreate,
    user_id: UserDep,
    session: SessionDep,
    events: PublisherDep,
) -> AccessResponse:
    document = await _owned_document(session, document_id, user_id)
    return AccessResponse.model_validate(
        await record_access(session, events, document, user_id, payload)
    )


@router.post(
    "/{document_id}/supersede",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def supersede(
    document_id: UUID,
    payload: SupersedeRequest,
    user_id: UserDep,
    session: SessionDep,
    events: PublisherDep,
) -> Document:
    document = await _owned_document(session, document_id, user_id)
    try:
        return await supersede_document(session, events, document, payload.new_document_data)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


async def _owned_document(
    session: AsyncSession, document_id: UUID, user_id: UUID, with_accesses: bool = False
) -> Document:
    query = select(Document).where(Document.id == document_id, Document.owner_user_id == user_id)
    if with_accesses:
        query = query.options(selectinload(Document.accesses))
    document = await session.scalar(query)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )


def _cipher() -> Fernet:
    secret = settings.document_encryption_key.get_secret_value().encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret).digest()))


def _has_valid_signature(mime_type: str, content: bytes) -> bool:
    signatures = {
        "application/pdf": (b"%PDF-",),
        "image/jpeg": (b"\xff\xd8\xff",),
        "image/png": (b"\x89PNG\r\n\x1a\n",),
        "image/webp": (b"RIFF",),
    }
    return content.startswith(signatures[mime_type]) and (
        mime_type != "image/webp" or content[8:12] == b"WEBP"
    )


@internal_router.get("/users/{user_id}/export")
async def internal_export(
    user_id: UUID,
    session: SessionDep,
    token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
) -> dict:
    _require_internal(token)
    rows = (
        await session.scalars(
            select(Document)
            .where(Document.owner_user_id == user_id)
            .options(selectinload(Document.accesses))
            .order_by(Document.created_at)
        )
    ).all()
    return {
        "documents": [DocumentResponse.model_validate(row).model_dump() for row in rows],
        "sharing_history": [
            AccessResponse.model_validate(access).model_dump()
            for row in rows
            for access in row.accesses
            if access.action == "shared"
        ],
    }


def _require_internal(token: str | None) -> None:
    expected = settings.internal_service_token.get_secret_value()
    if not expected or not token or not hmac.compare_digest(token, expected):
        raise _unauthorized("Invalid internal service token")
