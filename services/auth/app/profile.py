from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProfileFieldProvenance, User
from app.schemas import EnrichmentField, ProfileResponse

PROFILE_FIELDS = (
    "name",
    "date_of_birth",
    "city",
    "state",
    "gender",
    "caste_category",
    "annual_income",
    "occupation",
    "education_level",
    "marital_status",
)
PROGRESSIVE_FIELDS = set(PROFILE_FIELDS)
SOURCE_TYPES = {
    "user_input",
    "document_extracted",
    "intake_conversation",
    "government_verified",
}
FIELD_ALIASES = {"dob": "date_of_birth", "income": "annual_income"}
FIELD_ACTIONS = {
    "annual_income": "Upload an income certificate",
    "date_of_birth": "Add your date of birth",
    "caste_category": "Add your category or upload a certificate",
}


def profile_payload(user: User) -> dict[str, Any]:
    return ProfileResponse.model_validate(
        {field: getattr(user, field) for field in (*PROFILE_FIELDS, "last_enriched_at")}
    ).model_dump()


def missing_fields(user: User) -> list[str]:
    return [field for field in PROFILE_FIELDS if getattr(user, field) in (None, "")]


def completeness(user: User) -> int:
    return round(100 * (len(PROFILE_FIELDS) - len(missing_fields(user))) / len(PROFILE_FIELDS))


def suggestions(missing: list[str], requirements: dict[str, int]) -> list[dict[str, Any]]:
    return [
        {
            "field": field,
            "reason": f"Required for {requirements[field]} benefit schemes",
            "action": FIELD_ACTIONS.get(field, f"Add your {field.replace('_', ' ')}"),
        }
        for field in missing
        if requirements.get(field, 0)
    ]


async def enrich_profile(
    session: AsyncSession, user: User, fields: list[EnrichmentField]
) -> list[str]:
    changed: list[str] = []
    now = datetime.now(UTC)
    for item in fields:
        name = FIELD_ALIASES.get(item.name, item.name)
        if name not in PROGRESSIVE_FIELDS:
            raise ValueError(f"Unsupported profile field: {item.name}")
        value = _coerce(name, item.value)
        setattr(user, name, value)
        session.add(
            ProfileFieldProvenance(
                user_id=user.id,
                field_name=name,
                value=value.isoformat() if isinstance(value, date) else str(value),
                source_type=item.source_type,
                source_reference=item.source_reference,
                verified=item.verified or item.source_type == "government_verified",
                confirmed_by_user=item.source_type == "user_input",
                confirmed_at=now if item.source_type == "user_input" else None,
                valid_from=item.valid_from,
                valid_until=item.valid_until,
            )
        )
        changed.append(name)
    user.last_enriched_at = now
    await session.flush()
    return changed


def fields_from_event(event: dict[str, Any]) -> tuple[str, list[EnrichmentField]] | None:
    event_type = str(event.get("event_type", ""))
    if event_type == "document.verified":
        raw = event.get("extracted_fields") or {}
        source = str(event.get("title") or event.get("document_type") or "Verified document")
        source_type = "document_extracted"
        verified = True
    elif event_type == "ai.profile_extracted":
        raw = event.get("profile_fields") or event.get("profile_summary") or {}
        source = f"Intake conversation {event.get('conversation_id')}"
        source_type = "intake_conversation"
        verified = False
    else:
        return None
    fields = [
        EnrichmentField(
            name=FIELD_ALIASES.get(name, name),
            value=value,
            source_type=source_type,
            source_reference=source,
            verified=verified,
        )
        for name, value in raw.items()
        if FIELD_ALIASES.get(name, name) in PROGRESSIVE_FIELDS and value not in (None, "")
    ]
    user_id = event.get("owner_user_id") or event.get("user_id")
    return (str(user_id), fields) if user_id and fields else None


def _coerce(field: str, value: Any) -> Any:
    if value is None or value == "":
        return None
    if field == "date_of_birth":
        try:
            parsed = value if isinstance(value, date) else date.fromisoformat(str(value))
        except ValueError as exc:
            raise ValueError("date_of_birth must use YYYY-MM-DD") from exc
        if parsed > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return parsed
    if field == "annual_income":
        if isinstance(value, bool):
            raise ValueError("annual_income must be a non-negative integer")
        try:
            parsed_income = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("annual_income must be a non-negative integer") from exc
        if parsed_income < 0:
            raise ValueError("annual_income must be a non-negative integer")
        return parsed_income
    text = str(value).strip()
    if not text or len(text) > 120:
        raise ValueError(f"{field} must contain 1 to 120 characters")
    if field == "caste_category" and text.casefold() not in {"general", "sc", "st", "obc"}:
        raise ValueError("caste_category must be general, sc, st, or obc")
    return text.casefold() if field == "caste_category" else text
