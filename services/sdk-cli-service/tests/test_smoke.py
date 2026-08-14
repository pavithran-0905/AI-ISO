"""One end-to-end smoke test: the app boots, hits real Postgres/Redis
through its actual lifespan, and answers health/readiness."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import HTTP_OK


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == HTTP_OK
    assert response.json()["data"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_readiness(client: AsyncClient) -> None:
    response = await client.get("/readiness")
    assert response.status_code == HTTP_OK
    assert response.json()["data"]["status"] == "ready"
