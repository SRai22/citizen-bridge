from datetime import date
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BenefitDiscovery


class DiscoveryPublisher(Protocol):
    async def publish(self, topic: str, event: dict[str, Any]) -> None: ...


def evaluate(benefit: dict, profile: dict, provenance: dict | None = None) -> dict:
    results = []
    missing = []
    for rule in benefit["eligibility_rules"]:
        field = rule["field"]
        value = profile.get(field)
        if value in (None, ""):
            status = "unknown"
            missing.append(field)
        else:
            status = "satisfied" if _matches(value, rule) else "failed"
        results.append(
            {
                "field": field,
                "operator": rule["operator"],
                "expected": rule.get("values") or rule.get("value"),
                "actual": value,
                "status": status,
                "source": (provenance or {}).get(field),
            }
        )
    state = (
        "ineligible"
        if any(item["status"] == "failed" for item in results)
        else "partially_eligible"
        if missing
        else "eligible"
    )
    return {"status": state, "rule_results": results, "missing_profile_fields": missing}


def readiness(benefit: dict, evaluation: dict, documents: dict) -> dict:
    rules = evaluation["rule_results"]
    required_documents = benefit.get("required_documents", [])
    complete_fields = sum(item["status"] == "satisfied" for item in rules)
    available = set(documents.get("available", []))
    total = len(rules) + len(required_documents)
    ready = complete_fields + sum(item in available for item in required_documents)
    missing_documents = [item for item in required_documents if item not in available]
    return {
        "percentage": round(100 * ready / total) if total else 100,
        "profile": {
            "complete": complete_fields,
            "total": len(rules),
            "missing": evaluation["missing_profile_fields"],
        },
        "documents": {
            "available": sorted(available.intersection(required_documents)),
            "total": len(required_documents),
            "missing": missing_documents,
        },
    }


def _matches(actual: Any, rule: dict) -> bool:
    operator = rule["operator"]
    expected = rule.get("value")
    if operator == "in":
        values = rule.get("values", [])
        return _normal(actual) in {_normal(value) for value in values}
    if operator == "age_gte":
        born = date.fromisoformat(str(actual))
        today = date.today()
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        return age >= int(expected)
    if operator == "eq":
        return _normal(actual) == _normal(expected)
    try:
        left, right = float(actual), float(expected)
    except (TypeError, ValueError):
        return False
    return {
        "lt": left < right,
        "lte": left <= right,
        "gt": left > right,
        "gte": left >= right,
    }[operator]


def _normal(value: Any) -> Any:
    return value.casefold() if isinstance(value, str) else value


async def discover(
    session: AsyncSession,
    publisher: DiscoveryPublisher,
    auth,
    catalog,
    documents,
    event: dict,
) -> None:
    user_id = str(event.get("user_id") or "")
    if not user_id:
        return
    profile = (await auth.profile_by_user(user_id))["profile"]
    changed = set(event.get("changed_fields") or [])
    for benefit in await catalog.benefits():
        fields = {rule["field"] for rule in benefit["eligibility_rules"]}
        if changed and fields.isdisjoint(changed):
            continue
        result = evaluate(benefit, profile)
        if result["status"] != "eligible":
            continue
        exists = await session.scalar(
            select(BenefitDiscovery.id).where(
                BenefitDiscovery.user_id == UUID(user_id),
                BenefitDiscovery.benefit_id == benefit["id"],
            )
        )
        if exists:
            continue
        document_state = await documents.check_requirements(
            user_id, benefit.get("required_documents", [])
        )
        session.add(BenefitDiscovery(user_id=UUID(user_id), benefit_id=benefit["id"]))
        await session.commit()
        await publisher.publish(
            "benefits",
            {
                "event_type": "benefit.discovered",
                "user_id": user_id,
                "benefit_id": benefit["id"],
                "name": benefit["name"],
                "amount": benefit["amount"],
                "readiness": readiness(benefit, result, document_state)["percentage"],
            },
        )
