"""Deterministic mock adapter for BBMP death registration."""

import json
from datetime import UTC, date, datetime, time
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AdapterStatus, StatusResult, SubmissionResult
from app.models import Document, ExternalApplication, Task, VerificationStatus

REQUIRED_APPLICATION_FIELDS = (
    "deceased_name",
    "date_of_death",
    "place_of_death",
    "cause_of_death",
)
REQUIRED_DOCUMENT_TYPES = (
    "medical_certificate_cause_of_death",
    "deceased_identity",
    "informant_identity",
)
REGISTRAR_NAME = "Registrar of Births and Deaths, BBMP South Zone"


class DeathCertificateAdapter:
    """Issue predictable mock certificates while exercising production boundaries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def submit_application(self, application: ExternalApplication) -> SubmissionResult:
        payload = application.request_payload
        validation_error = self._validate_payload(payload)
        if validation_error is not None:
            return self._error_result(validation_error)

        task = await self.session.get(Task, application.task_id)
        if task is None:
            return self._error_result("The application references a task that does not exist.")

        certificate = self._build_certificate(payload)
        reference_id = str(certificate["registration_number"])
        existing_document = await self.session.scalar(
            select(Document).where(
                Document.produced_by_task_id == task.id,
                Document.document_type == "death_certificate",
            )
        )
        issue_date = date.fromisoformat(str(certificate["date_of_issue"]))
        if existing_document is None:
            self.session.add(
                Document(
                    case_id=task.case_id,
                    produced_by_task_id=task.id,
                    document_type="death_certificate",
                    owner_name=str(payload["deceased_name"]),
                    issuer=REGISTRAR_NAME,
                    issued_at=datetime.combine(issue_date, time.min, tzinfo=UTC),
                    verification_status=VerificationStatus.VERIFIED,
                    extracted_fields=certificate,
                    metadata_={
                        "source": "mock_death_certificate_adapter",
                        "reference_id": reference_id,
                    },
                )
            )
        elif existing_document.metadata_.get("reference_id") != reference_id:
            existing_document.owner_name = str(payload["deceased_name"])
            existing_document.issuer = REGISTRAR_NAME
            existing_document.issued_at = datetime.combine(issue_date, time.min, tzinfo=UTC)
            existing_document.verification_status = VerificationStatus.VERIFIED
            existing_document.extracted_fields = certificate
            existing_document.metadata_ = {
                "source": "mock_death_certificate_adapter",
                "reference_id": reference_id,
            }
        await self.session.flush()

        return SubmissionResult(
            reference_id=reference_id,
            status=AdapterStatus.APPROVED,
            message="Death registration approved and certificate issued.",
            response_data=certificate,
        )

    async def check_status(self, reference_id: str) -> StatusResult:
        documents = await self.session.scalars(
            select(Document).where(Document.document_type == "death_certificate")
        )
        document = next(
            (
                candidate
                for candidate in documents.all()
                if candidate.metadata_.get("reference_id") == reference_id
            ),
            None,
        )
        if document is None:
            return StatusResult(
                reference_id=reference_id,
                status=AdapterStatus.ERROR,
                message="No death certificate submission was found for this reference.",
            )
        return StatusResult(
            reference_id=reference_id,
            status=AdapterStatus.APPROVED,
            message="Death certificate issued.",
            response_data=dict(document.extracted_fields),
        )

    async def get_requirements(self) -> list[str]:
        return list(REQUIRED_DOCUMENT_TYPES)

    @staticmethod
    def _validate_payload(payload: dict[str, Any]) -> str | None:
        missing = [
            field
            for field in REQUIRED_APPLICATION_FIELDS
            if not isinstance(payload.get(field), str) or not str(payload[field]).strip()
        ]
        if missing:
            return f"Missing required application fields: {', '.join(missing)}."
        try:
            date.fromisoformat(str(payload["date_of_death"]))
        except ValueError:
            return "Field 'date_of_death' must be a valid ISO date (YYYY-MM-DD)."
        for optional_date_field in ("date_of_registration", "date_of_issue"):
            if optional_date_field not in payload:
                continue
            try:
                date.fromisoformat(str(payload[optional_date_field]))
            except ValueError:
                return f"Field '{optional_date_field}' must be a valid ISO date (YYYY-MM-DD)."
        return None

    @staticmethod
    def _build_certificate(payload: dict[str, Any]) -> dict[str, Any]:
        canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = sha256(canonical_payload.encode("utf-8")).hexdigest().upper()
        date_of_death = str(payload["date_of_death"])
        registration_date = str(payload.get("date_of_registration") or date_of_death)
        issue_date = str(payload.get("date_of_issue") or registration_date)
        registration_number = f"BBMP/D/{date.fromisoformat(date_of_death).year}/{digest[:8]}"
        return {
            **payload,
            "registration_number": registration_number,
            "date_of_registration": registration_date,
            "date_of_issue": issue_date,
            "registrar_name": REGISTRAR_NAME,
            "registrar": REGISTRAR_NAME,
        }

    @staticmethod
    def _error_result(message: str) -> SubmissionResult:
        return SubmissionResult(
            status=AdapterStatus.ERROR,
            message=message,
            response_data={},
        )
