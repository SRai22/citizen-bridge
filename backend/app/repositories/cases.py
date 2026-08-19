"""Persistence operations for cases."""

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Case, CaseStatus, HouseholdProfile, LifeEvent, Person, Task
from app.schemas import CaseCreate


def case_graph_query(case_id: UUID) -> Select[tuple[Case]]:
    """Build the consistently eager-loaded case query used by API responses."""
    return (
        select(Case)
        .where(Case.id == case_id)
        .options(
            selectinload(Case.life_event),
            selectinload(Case.household_profile).selectinload(HouseholdProfile.people),
            selectinload(Case.tasks).selectinload(Task.dependencies),
            selectinload(Case.tasks).selectinload(Task.external_applications),
            selectinload(Case.tasks).selectinload(Task.approval_requests),
            selectinload(Case.documents),
            selectinload(Case.audit_entries),
        )
    )


class CaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: CaseCreate) -> Case:
        event_values = payload.life_event.model_dump(exclude={"type", "occurred_at"})
        event_values["event_type"] = payload.life_event.type
        if payload.life_event.occurred_at is not None:
            event_values["occurred_at"] = payload.life_event.occurred_at

        household = None
        if payload.household_profile is not None:
            profile = payload.household_profile
            household = HouseholdProfile(
                location_city=profile.location_city,
                location_state=profile.location_state,
                people=[Person(**person.model_dump()) for person in profile.people],
            )

        case = Case(
            status=CaseStatus.INTAKE,
            life_event=LifeEvent(**event_values),
            household_profile=household,
        )
        self.session.add(case)
        await self.session.commit()
        loaded = await self.get(case.id)
        if loaded is None:  # pragma: no cover - the row was just committed
            raise RuntimeError("Created case disappeared")
        return loaded

    async def get(self, case_id: UUID) -> Case | None:
        cases = await self.session.scalars(case_graph_query(case_id))
        return cases.one_or_none()

    async def exists(self, case_id: UUID) -> bool:
        return await self.session.get(Case, case_id) is not None

    async def activate(self, case: Case) -> Case:
        case.status = CaseStatus.ACTIVE
        await self.session.commit()
        loaded = await self.get(case.id)
        if loaded is None:  # pragma: no cover - the row was just committed
            raise RuntimeError("Activated case disappeared")
        return loaded
