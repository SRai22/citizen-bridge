import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime

HealthCheck = Callable[[], Awaitable[None]]


async def run_checks(checks: Mapping[str, HealthCheck]) -> dict[str, str]:
    async def run(check: HealthCheck) -> str:
        try:
            await check()
        except Exception:  # noqa: BLE001 - dependency failures are health results
            return "error"
        return "ok"

    results = await asyncio.gather(*(run(check) for check in checks.values()))
    return dict(zip(checks, results, strict=True))


def build_health(
    service: str,
    version: str,
    started_at: datetime,
    checks: Mapping[str, str],
) -> dict[str, object]:
    return {
        "service": service,
        "status": "healthy"
        if all(result == "ok" for result in checks.values())
        else "unhealthy",
        "version": version,
        "uptime_seconds": max(0, int((datetime.now(UTC) - started_at).total_seconds())),
        "checks": dict(checks),
    }
