"""Smoke test: the app boots, the database and cache are reachable, and
health responds."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import HTTP_OK


class TestSmoke:
    async def test_health(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] == "healthy"

    async def test_readiness(self, client: AsyncClient) -> None:
        response = await client.get("/readiness")
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] == "ready"
