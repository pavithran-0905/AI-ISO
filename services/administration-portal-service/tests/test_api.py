"""End-to-end API tests against the real FastAPI app (real Postgres/Redis)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from httpx import AsyncClient

from app.models.enums import OrganizationStatus, TenantStatus
from app.models.tenants import Organization, Tenant
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
        response = await client.get("/admin/tenants")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_non_admin_cannot_provision_tenant(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id, roles=["viewer"])
        response = await client.post(
            "/admin/tenants",
            json={"organization_ref_id": str(uuid4()), "name": "Tenant A"},
            headers=headers,
        )
        assert response.status_code == HTTP_FORBIDDEN


async def _create_organization(repos, organization_id: UUID, **kwargs: object) -> Organization:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "name": "Acme",
        "status": OrganizationStatus.ACTIVE,
    }
    defaults.update(kwargs)
    return await repos.organizations.create(Organization(**defaults))


class TestDashboardRoute:
    async def test_get_dashboard_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/admin/dashboard", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["tenant_count"] == 0


class TestSettingsRoutes:
    async def test_list_settings_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/admin/settings", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["settings"] == []

    async def test_put_settings_upserts(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.put(
            "/admin/settings",
            json={"key": "brand_name", "value": {"name": "AI-IOS"}},
            headers=headers,
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["key"] == "brand_name"


class TestTenantRoutes:
    async def test_list_tenants_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/admin/tenants", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["tenants"] == []

    async def test_create_tenant(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        org = await _create_organization(repos, organization_id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/admin/tenants",
            json={"organization_ref_id": str(org.id), "name": "Tenant A"},
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["status"] == "provisioning"

    async def test_update_tenant_transitions(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        org = await _create_organization(repos, organization_id)
        tenant = await repos.tenants.create(
            Tenant(organization_id=organization_id, organization_ref_id=org.id, name="Tenant A")
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.put(
            f"/admin/tenants/{tenant.id}", json={"target_status": "active"}, headers=headers
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] == "active"

    async def test_update_tenant_invalid_transition_is_conflict(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        org = await _create_organization(repos, organization_id)
        tenant = await repos.tenants.create(
            Tenant(organization_id=organization_id, organization_ref_id=org.id, name="Tenant A")
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.put(
            f"/admin/tenants/{tenant.id}", json={"target_status": "suspended"}, headers=headers
        )
        assert response.status_code == HTTP_CONFLICT

    async def test_delete_tenant_starts_deleting(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        org = await _create_organization(repos, organization_id)
        tenant = await repos.tenants.create(
            Tenant(
                organization_id=organization_id,
                organization_ref_id=org.id,
                name="Tenant A",
                status=TenantStatus.ACTIVE,
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.delete(f"/admin/tenants/{tenant.id}", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] == "deleting"


class TestFeatureFlagRoutes:
    async def test_list_feature_flags_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/admin/feature-flags", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["feature_flags"] == []

    async def test_create_and_update_feature_flag(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        create_response = await client.post(
            "/admin/feature-flags",
            json={"name": "new-ui", "scope": "global", "rollout_percentage": 50.0},
            headers=headers,
        )
        assert create_response.status_code == HTTP_CREATED
        flag_id = create_response.json()["data"]["id"]

        update_response = await client.put(
            f"/admin/feature-flags/{flag_id}", json={"is_killed": True}, headers=headers
        )
        assert update_response.status_code == HTTP_OK
        assert update_response.json()["data"]["is_killed"] is True


class TestJobRoutes:
    async def test_list_jobs_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/admin/jobs", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["jobs"] == []

    async def test_create_job(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/admin/jobs", json={"job_key": "sync", "priority": "high"}, headers=headers
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["status"] == "queued"


class TestDiagnosticsHealthStatisticsReportRoutes:
    async def test_get_diagnostics_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/admin/diagnostics", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["diagnostics"] == []

    async def test_get_health_unknown_with_no_checks(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/admin/health", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["overall_status"] == "unknown"

    async def test_get_statistics_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/admin/statistics", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["windows"] == []

    async def test_get_reports_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/admin/reports", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["reports"] == []
