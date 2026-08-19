"""Deterministic mock adapter for BESCOM account name transfers."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AdapterStatus, StatusResult, SubmissionResult
from app.models import Document, ExternalApplication, Task

REQUIRED_APPLICATION_FIELDS = (
    "consumer_number",
    "current_holder_name",
    "proposed_holder_name",
    "property_address",
)
REQUIRED_DOCUMENT_TYPES = ("death_certificate", "legal_heir_certificate")
REJECTION_MESSAGE = (
    "Supporting documentation establishing the proposed transferee's relationship or "
    "succession rights is insufficient. A Legal Heir Certificate or Succession Certificate "
    "issued by a competent authority is required."
)


class BescomTransferAdapter:
    """Approve transfers only when the case has proof of legal succession."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def submit_application(self, application: ExternalApplication) -> SubmissionResult:
        payload = application.request_payload
        missing = [
            field
            for field in REQUIRED_APPLICATION_FIELDS
            if not isinstance(payload.get(field), str) or not str(payload[field]).strip()
        ]
        if missing:
            return SubmissionResult(
                status=AdapterStatus.ERROR,
                message=f"Missing required application fields: {', '.join(missing)}.",
            )

        task = await self.session.get(Task, application.task_id)
        if task is None:
            return SubmissionResult(
                status=AdapterStatus.ERROR,
                message="The application references a task that does not exist.",
            )

        reference_id = self._reference_id(payload, application.created_at)
        has_legal_heir_certificate = await self.session.scalar(
            select(Document.id).where(
                Document.case_id == task.case_id,
                Document.document_type == "legal_heir_certificate",
            )
        )
        if has_legal_heir_certificate is None:
            return SubmissionResult(
                reference_id=reference_id,
                status=AdapterStatus.REJECTED,
                message=REJECTION_MESSAGE,
                response_data={
                    "rejection_code": "INSUFFICIENT_SUCCESSION_DOCS",
                    "required_document": "legal_heir_certificate",
                },
            )

        effective_at = application.submitted_at or application.created_at
        return SubmissionResult(
            reference_id=reference_id,
            status=AdapterStatus.APPROVED,
            message="BESCOM account name transfer approved.",
            response_data={
                "new_account_holder_name": payload["proposed_holder_name"],
                "effective_date": effective_at.date().isoformat(),
                "updated_consumer_number": payload["consumer_number"],
            },
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
                message="No BESCOM submission was found for this reference.",
            )
        response = application.response_payload
        return StatusResult(
            reference_id=reference_id,
            status=AdapterStatus(application.status.value),
            message=str(response.get("message") or "BESCOM submission status retrieved."),
            response_data=dict(response.get("data") or {}),
        )

    async def get_requirements(self) -> list[str]:
        return list(REQUIRED_DOCUMENT_TYPES)

    @staticmethod
    def _reference_id(payload: dict[str, Any], created_at: datetime) -> str:
        canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = sha256(canonical_payload.encode("utf-8")).hexdigest().upper()
        year = created_at.astimezone(UTC).year if created_at.tzinfo else created_at.year
        return f"BESCOM/NT/{year}/{digest[:8]}"
