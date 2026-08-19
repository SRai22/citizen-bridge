"""Deterministic mock adapter for Karnataka ration card updates."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AdapterStatus, StatusResult, SubmissionResult
from app.models import Document, ExternalApplication, Task, VerificationStatus

REQUIRED_APPLICATION_FIELDS = ("ration_card_number", "deceased_name", "new_head_name")
REQUIRED_DOCUMENT_TYPES = ("death_certificate",)
ISSUER = "Karnataka Department of Food and Civil Supplies"


class RationCardAdapter:
    """Approve complete ration card changes with deterministic mock data."""

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
        has_death_certificate = await self.session.scalar(
            select(Document.id).where(
                Document.case_id == task.case_id,
                Document.document_type == "death_certificate",
                Document.verification_status != VerificationStatus.REJECTED,
            )
        )
        if has_death_certificate is None:
            return SubmissionResult(
                status=AdapterStatus.ERROR,
                message="Missing required documents: death_certificate.",
            )

        effective_at = application.submitted_at or application.created_at
        updated_card_number = self._updated_card_number(payload, effective_at)
        update = {
            "updated_card_number": updated_card_number,
            "new_head_of_family": str(payload["new_head_name"]),
            "modification_type": "member_deletion + head_change",
        }
        await self._create_acknowledgment(
            task,
            str(payload["new_head_name"]),
            update,
            effective_at,
        )
        return SubmissionResult(
            reference_id=updated_card_number,
            status=AdapterStatus.APPROVED,
            message="Ration card household update approved.",
            response_data=update,
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
                message="No ration card submission was found for this reference.",
            )
        response = application.response_payload
        return StatusResult(
            reference_id=reference_id,
            status=AdapterStatus(application.status.value),
            message=str(response.get("message") or "Ration card status retrieved."),
            response_data=dict(response.get("data") or {}),
        )

    async def get_requirements(self) -> list[str]:
        return list(REQUIRED_DOCUMENT_TYPES)

    async def _create_acknowledgment(
        self,
        task: Task,
        owner_name: str,
        update: dict[str, Any],
        issued_at: datetime,
    ) -> None:
        existing = await self.session.scalar(
            select(Document).where(
                Document.produced_by_task_id == task.id,
                Document.document_type == "updated_ration_card",
            )
        )
        if existing is None:
            self.session.add(
                Document(
                    case_id=task.case_id,
                    produced_by_task_id=task.id,
                    document_type="updated_ration_card",
                    owner_name=owner_name,
                    issuer=ISSUER,
                    issued_at=issued_at,
                    verification_status=VerificationStatus.VERIFIED,
                    extracted_fields=update,
                    metadata_={"source": "mock_ration_card_adapter"},
                )
            )
        await self.session.flush()

    @staticmethod
    def _updated_card_number(payload: dict[str, Any], effective_at: datetime) -> str:
        canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = sha256(canonical_payload.encode("utf-8")).hexdigest().upper()
        year = effective_at.astimezone(UTC).year if effective_at.tzinfo else effective_at.year
        return f"KA-BLR-{year}-{digest[:7]}"
