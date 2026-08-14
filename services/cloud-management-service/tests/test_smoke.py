"""Smoke test: conftest fixtures build against real infrastructure, and
core routes are wired correctly."""

from __future__ import annotations

from uuid import UUID

from httpx import AsyncClient

from tests.conftest import HTTP_OK, AuthHeadersFn


async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == HTTP_OK


async def test_providers_route_resolves(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    response = await client.get("/cloud/providers", headers=headers)
    assert response.status_code == HTTP_OK
    assert "providers" in response.json()["data"]
