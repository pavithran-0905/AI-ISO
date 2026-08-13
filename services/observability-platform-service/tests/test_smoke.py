"""Smoke tests: the app boots, the DB session works, health responds."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_db_session_works(db_session: AsyncSession) -> None:
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_readiness_endpoint(client: AsyncClient) -> None:
    response = await client.get("/readiness")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_liveness_endpoint(client: AsyncClient) -> None:
    response = await client.get("/liveness")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_unauthenticated_route_rejected(client: AsyncClient) -> None:
    response = await client.get(
        "/observability/topology?organization_id=00000000-0000-0000-0000-000000000001"
    )
    assert response.status_code == 401
