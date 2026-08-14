"""Smoke test: conftest fixtures build against real infrastructure, and
literal-path routes resolve ahead of the parameterized detail route."""

from __future__ import annotations

from uuid import UUID

from httpx import AsyncClient

from tests.conftest import HTTP_OK, AuthHeadersFn


async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == HTTP_OK


async def test_fleet_health_route_not_swallowed_by_detail_route(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
) -> None:
    """``GET /clusters/health`` must resolve to the fleet-health route,
    not be parsed as ``GET /clusters/{cluster_id}`` with
    ``cluster_id="health"`` (which would 422 on UUID validation)."""
    headers = auth_headers(organization_id=organization_id)
    response = await client.get("/clusters/health", headers=headers)
    assert response.status_code == HTTP_OK
    assert "clusters" in response.json()["data"]
