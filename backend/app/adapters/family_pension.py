"""Deterministic mock adapter for Karnataka family pension transfers."""

import json
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AdapterStatus, StatusResult, SubmissionResult
from app.models import Document, ExternalApplication, Task, VerificationStatus

REQUIRED_APPLICATION_FIELDS = ("spouse_name", "ppo_number", "bank_account_number")
REQUIRED_DOCUMENT_TYPES = ("death_certificate", "pension_payment_order")
ISSUER = "Accountant General Karnataka and Karnataka Treasury"


class FamilyPensionAdapter:
    """Approve complete family pension applications with deterministic mock data."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def submit_application(self, application: ExternalApplication) -> SubmissionResult:
        payload = application.request_payload
        missing_fields = [
            field
            for field in REQUIRED_APPLICATION_FIELDS
            if not isinstance(payload.get(field), str) or not str(payload[field]).strip()
        ]
        if missing_fields:
            return SubmissionResult(
                status=AdapterStatus.ERROR,
                message=f"Missing required application fields: {', '.join(missing_fields)}.",
            )

        task = await self.session.get(Task, application.task_id)
        if task is None:
            return SubmissionResult(
                status=AdapterStatus.ERROR,
                message="The application references a task that does not exist.",
            )

        documents = list(
            (
                await self.session.scalars(
                    select(Document).where(
                        Document.case_id == task.case_id,
                        Document.document_type.in_(REQUIRED_DOCUMENT_TYPES),
                        Document.verification_status != VerificationStatus.REJECTED,
                    )
                )
            ).all()
        )
        available_types = {document.document_type for document in documents}
        missing_documents = sorted(set(REQUIRED_DOCUMENT_TYPES) - available_types)
        if missing_documents:
            return SubmissionResult(
                status=AdapterStatus.ERROR,
                message=f"Missing required documents: {', '.join(missing_documents)}.",
            )

        effective_at = application.submitted_at or application.created_at
        death_certificate = next(
            document for document in documents if document.document_type == "death_certificate"
        )
        effective_date = self._effective_date(death_certificate, effective_at.date())
        revised_ppo = self._revised_ppo(payload, effective_at)
        sanction = {
            "provisional_pension_amount": 25_000,
            "effective_date": effective_date.isoformat(),
            "ppo_number": revised_ppo,
            "treasury_code": "BLR-SOUTH",
        }
        await self._create_sanction(task, str(payload["spouse_name"]), sanction, effective_at)
        return SubmissionResult(
            reference_id=revised_ppo,
            status=AdapterStatus.APPROVED,
            message="Family pension transfer approved provisionally.",
            response_data=sanction,
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
                message="No family pension submission was found for this reference.",
            )
        response = application.response_payload
        return StatusResult(
            reference_id=reference_id,
            status=AdapterStatus(application.status.value),
            message=str(response.get("message") or "Family pension status retrieved."),
            response_data=dict(response.get("data") or {}),
        )

    async def get_requirements(self) -> list[str]:
        return list(REQUIRED_DOCUMENT_TYPES)

    async def _create_sanction(
        self,
        task: Task,
        owner_name: str,
        sanction: dict[str, Any],
        issued_at: datetime,
    ) -> None:
        existing = await self.session.scalar(
            select(Document).where(
                Document.produced_by_task_id == task.id,
                Document.document_type == "family_pension_sanction",
            )
        )
        if existing is None:
            self.session.add(
                Document(
                    case_id=task.case_id,
                    produced_by_task_id=task.id,
                    document_type="family_pension_sanction",
                    owner_name=owner_name,
                    issuer=ISSUER,
                    issued_at=issued_at,
                    verification_status=VerificationStatus.VERIFIED,
                    extracted_fields=sanction,
                    metadata_={"source": "mock_family_pension_adapter"},
                )
            )
        await self.session.flush()

    @staticmethod
    def _effective_date(document: Document, fallback: date) -> date:
        raw_date = document.extracted_fields.get("date_of_death")
        try:
            return date.fromisoformat(str(raw_date)) + timedelta(days=1)
        except ValueError:
            return fallback

    @staticmethod
    def _revised_ppo(payload: dict[str, Any], effective_at: datetime) -> str:
        canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = sha256(canonical_payload.encode("utf-8")).hexdigest().upper()
        year = effective_at.astimezone(UTC).year if effective_at.tzinfo else effective_at.year
        return f"KAR/FP/{year}/{digest[:8]}"
