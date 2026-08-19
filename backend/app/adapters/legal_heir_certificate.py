"""Deterministic mock adapter for Karnataka legal heir certificates."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AdapterStatus, StatusResult, SubmissionResult
from app.models import Document, ExternalApplication, Task, VerificationStatus

REQUIRED_DOCUMENT_TYPES = ("death_certificate", "aadhaar")
ISSUING_AUTHORITY = "Tahsildar, Bengaluru South"


class LegalHeirCertificateAdapter:
    """Issue a deterministic legal heir certificate for a complete application."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def submit_application(self, application: ExternalApplication) -> SubmissionResult:
        payload = application.request_payload
        deceased_name = payload.get("deceased_name")
        legal_heirs = payload.get("legal_heirs")
        if not isinstance(deceased_name, str) or not deceased_name.strip():
            return self._error_result("Missing required application field: deceased_name.")
        if not self._valid_legal_heirs(legal_heirs):
            return self._error_result("Field 'legal_heirs' must contain names and relationships.")
        heirs = cast(list[dict[str, str]], legal_heirs)

        task = await self.session.get(Task, application.task_id)
        if task is None:
            return self._error_result("The application references a task that does not exist.")

        issued_at = application.submitted_at or application.created_at
        certificate_number = self._certificate_number(payload, issued_at)
        certificate = {
            "certificate_number": certificate_number,
            "issuing_authority": ISSUING_AUTHORITY,
            "deceased_name": deceased_name,
            "legal_heirs": heirs,
            "date_of_issue": issued_at.date().isoformat(),
        }
        await self._create_certificate(
            task,
            heirs[0]["name"],
            certificate,
            issued_at,
        )
        return SubmissionResult(
            reference_id=certificate_number,
            status=AdapterStatus.APPROVED,
            message="Legal heir certificate approved and issued.",
            response_data=certificate,
        )

    async def check_status(self, reference_id: str) -> StatusResult:
        application = await self.session.scalar(
            select(ExternalApplication).where(
                ExternalApplication.external_reference_id == reference_id
            )
        )
        if application is None:
            return StatusResult(
                reference_id=reference_id,
                status=AdapterStatus.ERROR,
                message="No legal heir certificate submission was found for this reference.",
            )
        response = application.response_payload
        return StatusResult(
            reference_id=reference_id,
            status=AdapterStatus(application.status.value),
            message=str(response.get("message") or "Legal heir certificate status retrieved."),
            response_data=dict(response.get("data") or {}),
        )

    async def get_requirements(self) -> list[str]:
        return list(REQUIRED_DOCUMENT_TYPES)

    async def _create_certificate(
        self,
        task: Task,
        owner_name: str,
        certificate: dict[str, Any],
        issued_at: datetime,
    ) -> None:
        existing = await self.session.scalar(
            select(Document).where(
                Document.produced_by_task_id == task.id,
                Document.document_type == "legal_heir_certificate",
            )
        )
        if existing is None:
            self.session.add(
                Document(
                    case_id=task.case_id,
                    produced_by_task_id=task.id,
                    document_type="legal_heir_certificate",
                    owner_name=owner_name,
                    issuer=ISSUING_AUTHORITY,
                    issued_at=issued_at,
                    verification_status=VerificationStatus.VERIFIED,
                    extracted_fields=certificate,
                    metadata_={
                        "source": "mock_legal_heir_certificate_adapter",
                        "reference_id": certificate["certificate_number"],
                    },
                )
            )
        await self.session.flush()

    @staticmethod
    def _valid_legal_heirs(value: object) -> bool:
        return (
            isinstance(value, list)
            and bool(value)
            and all(
                isinstance(heir, dict)
                and isinstance(heir.get("name"), str)
                and bool(heir["name"].strip())
                and isinstance(heir.get("relationship"), str)
                and bool(heir["relationship"].strip())
                for heir in value
            )
        )

    @staticmethod
    def _certificate_number(payload: dict[str, Any], issued_at: datetime) -> str:
        canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = sha256(canonical_payload.encode("utf-8")).hexdigest().upper()
        year = issued_at.astimezone(UTC).year if issued_at.tzinfo else issued_at.year
        return f"REV/LHC/{year}/{digest[:8]}"

    @staticmethod
    def _error_result(message: str) -> SubmissionResult:
        return SubmissionResult(status=AdapterStatus.ERROR, message=message)
