from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Document, DocumentAccessLog
from app.schemas import AccessCreate, DocumentCreate, Requirement, RequirementResult, UploadCreate

TYPE_CATEGORIES = {
    "aadhaar": "identity",
    "pan_card": "identity",
    "voter_id": "identity",
    "passport": "identity",
    "electricity_bill": "address",
    "water_bill": "address",
    "rental_agreement": "address",
    "property_tax": "address",
    "salary_slip": "income",
    "income_certificate": "income",
    "form_16": "income",
    "bank_statement": "income",
    "ration_card": "family",
    "marriage_certificate": "family",
}
TASK_OUTPUTS = {
    "death_registration": ["death_certificate"],
    "birth_registration": ["birth_certificate"],
    "legal_heir_application": ["legal_heir_certificate"],
    "ration_card_modification": ["ration_card"],
}


class Publisher(Protocol):
    async def publish(self, event: dict[str, Any]) -> None: ...


def proof_category(document_type: str) -> str:
    return TYPE_CATEGORIES.get(document_type, "certificates")


async def create_document(
    session: AsyncSession, publisher: Publisher, payload: DocumentCreate
) -> Document:
    document = Document(**payload.model_dump(exclude={"metadata"}), metadata_=payload.metadata)
    session.add(document)
    await session.commit()
    await session.refresh(document)
    await publisher.publish(
        _event(
            "document.created",
            document_id=str(document.id),
            owner_user_id=str(document.owner_user_id),
            document_type=document.document_type,
            proof_category=document.proof_category,
            title=document.title,
            case_id=str(document.source_case_id) if document.source_case_id else None,
        )
    )
    if document.verification_status == "verified":
        await publisher.publish(
            _event(
                "document.verified",
                document_id=str(document.id),
                owner_user_id=str(document.owner_user_id),
                document_type=document.document_type,
                title=document.title,
                extracted_fields=document.extracted_fields,
            )
        )
    return document


async def record_access(
    session: AsyncSession,
    publisher: Publisher,
    document: Document,
    user_id: UUID,
    payload: AccessCreate,
    service: str | None = None,
) -> DocumentAccessLog:
    access = DocumentAccessLog(
        document_id=document.id,
        accessed_by_user_id=user_id,
        accessed_by_service=service,
        **payload.model_dump(),
    )
    session.add(access)
    await session.commit()
    await publisher.publish(
        _event(
            "document.accessed",
            document_id=str(document.id),
            owner_user_id=str(document.owner_user_id),
            action=access.action,
            purpose=access.purpose,
            recipient=access.recipient,
            document_title=document.title,
            case_id=str(access.case_id) if access.case_id else None,
            task_id=str(access.task_id) if access.task_id else None,
            data_fields_accessed=document.metadata_.get("data_fields_accessed", []),
        )
    )
    return access


async def check_requirements(
    session: AsyncSession, user_id: UUID, requirements: list[Requirement]
) -> list[RequirementResult]:
    documents = (
        await session.scalars(
            select(Document).where(
                Document.owner_user_id == user_id,
                Document.verification_status == "verified",
                Document.superseded_by_id.is_(None),
            )
        )
    ).all()
    results = []
    for requirement in requirements:
        match = next(
            (
                document
                for document in documents
                if document.document_type == requirement.type
                and (requirement.owner is None or document.subject_person_id == requirement.owner)
            ),
            None,
        )
        results.append(
            RequirementResult(
                type=requirement.type,
                status="satisfied" if match else "missing",
                document_id=match.id if match else None,
            )
        )
    return results


async def supersede_document(
    session: AsyncSession,
    publisher: Publisher,
    old: Document,
    payload: UploadCreate,
) -> Document:
    if old.superseded_by_id:
        raise ValueError("Document is already superseded")
    data = payload.model_dump()
    category = data.pop("proof_category") or proof_category(payload.document_type)
    new = await create_document(
        session,
        publisher,
        DocumentCreate(
            owner_user_id=old.owner_user_id,
            proof_category=category,
            provenance_type="user_uploaded",
            provenance_source=f"Supersedes document {old.id}",
            **data,
        ),
    )
    old.superseded_by_id = new.id
    await session.commit()
    await publisher.publish(
        _event(
            "document.superseded",
            document_id=str(old.id),
            owner_user_id=str(old.owner_user_id),
            superseded_by_id=str(new.id),
        )
    )
    return new


async def consume_task_completed(
    session: AsyncSession, publisher: Publisher, event: dict[str, Any]
) -> None:
    owner = event.get("owner_user_id") or event.get("changed_by")
    if not owner:
        return
    output = event.get("output_data") or {}
    produced = output.get("produced_documents") or event.get("produced_documents")
    produced = produced or TASK_OUTPUTS.get(str(event.get("task_type")), [])
    for item in produced:
        values = item if isinstance(item, dict) else {"type": str(item)}
        document_type = str(values["type"])
        existing = await session.scalar(
            select(Document).where(
                Document.source_task_id == UUID(str(event["task_id"])),
                Document.document_type == document_type,
            )
        )
        if existing:
            continue
        await create_document(
            session,
            publisher,
            DocumentCreate(
                owner_user_id=UUID(str(owner)),
                document_type=document_type,
                proof_category=values.get("proof_category") or proof_category(document_type),
                title=values.get("title") or document_type.replace("_", " ").title(),
                issuer=values.get("issuer"),
                verification_status="verified",
                provenance_type="platform_issued",
                provenance_source=f"Issued via task {event['task_id']}",
                source_case_id=UUID(str(event["case_id"])),
                source_task_id=UUID(str(event["task_id"])),
                extracted_fields=values.get("extracted_fields", {}),
                metadata=values.get("metadata", {}),
            ),
        )


async def expire_documents(
    sessions: async_sessionmaker[AsyncSession], publisher: Publisher
) -> None:
    async with sessions() as session:
        expired = (
            await session.scalars(
                select(Document).where(
                    Document.valid_until < datetime.now(UTC),
                    Document.verification_status.notin_(("expired", "rejected")),
                    Document.superseded_by_id.is_(None),
                )
            )
        ).all()
        for document in expired:
            document.verification_status = "expired"
        await session.commit()
        for document in expired:
            await publisher.publish(
                _event(
                    "document.expired",
                    document_id=str(document.id),
                    owner_user_id=str(document.owner_user_id),
                    document_type=document.document_type,
                )
            )


def _event(event_type: str, **fields: Any) -> dict[str, Any]:
    return {"event_type": event_type, "timestamp": datetime.now(UTC).isoformat(), **fields}


async def delete_user_data(session: AsyncSession, event: dict[str, Any]) -> None:
    await session.execute(
        delete(Document).where(Document.owner_user_id == UUID(str(event["user_id"])))
    )
    await session.commit()
