"""End-to-end API tests against the real FastAPI app (real Postgres/Redis)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from httpx import AsyncClient

from app.models.enums import ClusterType
from app.models.fleet import Cluster
from tests.conftest import (
    HTTP_CONFLICT,
    HTTP_CREATED,
    HTTP_FORBIDDEN,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    AuthHeadersFn,
)

NOW = datetime(2026, 6, 1, tzinfo=UTC)


class TestHealthEndpoints:
    async def test_health(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] == "healthy"

    async def test_liveness(self, client: AsyncClient) -> None:
        response = await client.get("/liveness")
        assert response.status_code == HTTP_OK

    async def test_readiness(self, client: AsyncClient) -> None:
        response = await client.get("/readiness")
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] in ("ready", "not_ready")

    async def test_metrics(self, client: AsyncClient) -> None:
        response = await client.get("/metrics")
        assert response.status_code == HTTP_OK


class TestAuth:
    async def test_missing_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get("/clusters")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_non_admin_cannot_register_cluster(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id, roles=["viewer"])
        response = await client.post(
            "/clusters",
            json={"name": "c1", "cluster_type": "kubernetes"},
            headers=headers,
        )
        assert response.status_code == HTTP_FORBIDDEN


async def _create_cluster(repos, organization_id: UUID, **kwargs: object) -> Cluster:
    defaults = {
        "organization_id": organization_id,
        "name": "c1",
        "cluster_type": ClusterType.KUBERNETES,
    }
    defaults.update(kwargs)
    return await repos.clusters.create(Cluster(**defaults))


class TestClusterCrudRoutes:
    async def test_list_clusters_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/clusters", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["clusters"] == []

    async def test_create_and_get_cluster(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/clusters",
            json={"name": "prod-1", "cluster_type": "kubernetes", "environment": "production"},
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        cluster_id = response.json()["data"]["id"]

        get_response = await client.get(f"/clusters/{cluster_id}", headers=headers)
        assert get_response.status_code == HTTP_OK
        assert get_response.json()["data"]["name"] == "prod-1"

    async def test_get_missing_cluster_404(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get(f"/clusters/{uuid4()}", headers=headers)
        assert response.status_code >= HTTP_FORBIDDEN

    async def test_update_cluster(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        cluster = await _create_cluster(repos, organization_id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.put(
            f"/clusters/{cluster.id}",
            json={"description": "updated description"},
            headers=headers,
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["id"] == str(cluster.id)

    async def test_delete_cluster_starts_decommissioning(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        cluster = await _create_cluster(repos, organization_id, lifecycle_state="active")
        headers = auth_headers(organization_id=organization_id)
        response = await client.delete(f"/clusters/{cluster.id}", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["lifecycle_state"] == "decommissioning"

    async def test_delete_cluster_invalid_transition_is_conflict(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        """A freshly-discovered cluster cannot jump straight to
        decommissioning -- the route must surface that refusal as a
        clear 409, not an unhandled 500."""
        cluster = await _create_cluster(repos, organization_id, lifecycle_state="discovered")
        headers = auth_headers(organization_id=organization_id)
        response = await client.delete(f"/clusters/{cluster.id}", headers=headers)
        assert response.status_code == HTTP_CONFLICT


class TestValidateRoute:
    async def test_validate_no_credential(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        cluster = await _create_cluster(repos, organization_id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(f"/clusters/{cluster.id}/validate", headers=headers)
        assert response.status_code == HTTP_OK
        assert not response.json()["data"]["is_valid"]


class TestUpgradeRoute:
    async def test_upgrade_refused_without_catalog_entries(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        cluster = await _create_cluster(repos, organization_id, kubernetes_version="1.28.0")
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            f"/clusters/{cluster.id}/upgrade",
            json={"to_version": "1.29.0", "strategy": "rolling"},
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        data = response.json()["data"]
        assert data["upgrade_id"] is None
        assert data["refusal"] == "same_version"


class TestCordonUncordonDrainRoutes:
    async def test_cordon_and_uncordon(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        cluster = await _create_cluster(repos, organization_id)
        headers = auth_headers(organization_id=organization_id)
        cordon_response = await client.post(f"/clusters/{cluster.id}/cordon", headers=headers)
        assert cordon_response.status_code == HTTP_OK
        assert not cordon_response.json()["data"]["is_schedulable"]

        uncordon_response = await client.post(f"/clusters/{cluster.id}/uncordon", headers=headers)
        assert uncordon_response.status_code == HTTP_OK
        assert uncordon_response.json()["data"]["is_schedulable"]

    async def test_drain_no_workloads(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        cluster = await _create_cluster(repos, organization_id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(f"/clusters/{cluster.id}/drain", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["workloads_marked"] == 0


class TestFleetWideRoutes:
    async def test_fleet_health(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        await _create_cluster(repos, organization_id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/clusters/health", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1

    async def test_fleet_capacity_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/clusters/capacity", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["readings"] == []

    async def test_fleet_compliance_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/clusters/compliance", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["assessments"] == []

    async def test_fleet_statistics_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/clusters/statistics", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["windows"] == []

    async def test_fleet_reports_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/clusters/reports", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["reports"] == []
