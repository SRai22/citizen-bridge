import httpx

from app.profile import FIELD_ALIASES


class CatalogClient:
    def __init__(self, base_url: str) -> None:
        self.client = httpx.AsyncClient(base_url=base_url, timeout=3)

    async def benefit_requirements(self) -> dict[str, int]:
        try:
            response = await self.client.get(
                "/api/catalog/services", params={"category": "benefits"}
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return {}
        counts: dict[str, int] = {}
        for service in response.json().get("services", []):
            for field in service.get("required_profile_fields", []):
                name = FIELD_ALIASES.get(str(field), str(field))
                counts[name] = counts.get(name, 0) + 1
        return counts

    async def close(self) -> None:
        await self.client.aclose()
