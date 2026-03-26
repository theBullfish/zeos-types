"""ServiceEntry + RegistryClient — spine service discovery."""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field


class ServiceEntry(BaseModel):
    service_id: str
    kind: str = ""
    base_url: str = ""
    ws_url: str | None = None
    health_path: str = "/health"
    capabilities: list[str] = Field(default_factory=list)
    registered_at: float = 0.0
    last_heartbeat: float = 0.0
    metadata: dict = Field(default_factory=dict)


class RegistryClient:
    """Client for the Zeos Service Registry (spine)."""

    def __init__(self, registry_url: str = "http://localhost:8500"):
        self.url = registry_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=5.0)

    async def register(self, entry: ServiceEntry) -> dict:
        r = await self._client.post(f"{self.url}/register", json=entry.model_dump())
        r.raise_for_status()
        return r.json()

    async def deregister(self, service_id: str) -> dict:
        r = await self._client.delete(f"{self.url}/deregister/{service_id}")
        r.raise_for_status()
        return r.json()

    async def heartbeat(self, service_id: str) -> dict:
        r = await self._client.post(f"{self.url}/heartbeat/{service_id}")
        r.raise_for_status()
        return r.json()

    async def list_services(self) -> list[ServiceEntry]:
        r = await self._client.get(f"{self.url}/registry")
        r.raise_for_status()
        return [ServiceEntry(**s) for s in r.json()]

    async def find_service(self, service_id: str) -> ServiceEntry | None:
        r = await self._client.get(f"{self.url}/registry/{service_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return ServiceEntry(**r.json())

    async def close(self):
        await self._client.aclose()
