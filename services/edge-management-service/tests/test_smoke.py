"""Smoke test: conftest fixtures build against real infrastructure, and
literal-path fleet routes resolve ahead of the parameterized device
detail route."""

from __future__ import annotations

from uuid import UUID

from httpx import AsyncClient

from tests.conftest import HTTP_OK, AuthHeadersFn


async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == HTTP_OK


async def test_fleet_health_route_not_swallowed_by_devices_prefix(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
) -> None:
    """``GET /edge/health`` must resolve to the fleet-health route, not be
    confused with anything under ``/edge/devices``."""
    headers = auth_headers(organization_id=organization_id)
    response = await client.get("/edge/health", headers=headers)
    assert response.status_code == HTTP_OK
    assert "devices" in response.json()["data"]
