import asyncio

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


class DataServicesClient:
    def __init__(self, urls: dict[str, str], token: str) -> None:
        self.clients = {
            name: httpx.AsyncClient(
                base_url=url,
                timeout=10,
                headers={"X-Internal-Service-Token": token},
            )
            for name, url in urls.items()
        }

    async def export(self, user_id: str) -> dict[str, object]:
        responses = await asyncio.gather(
            *(client.get(f"/internal/users/{user_id}/export") for client in self.clients.values())
        )
        result: dict[str, object] = {}
        for response in responses:
            response.raise_for_status()
            result.update(response.json())
        return result

    async def close(self) -> None:
        await asyncio.gather(*(client.aclose() for client in self.clients.values()))
