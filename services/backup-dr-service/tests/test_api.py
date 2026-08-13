"""End-to-end API tests against the real FastAPI app (real Postgres/Redis)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from httpx import AsyncClient

from app.models.backup import BackupTarget
from app.models.enums import BackupTargetKind
from app.models.recovery import DrPlan
from tests.conftest import (
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
        assert response.json()["data"]["status"] == "alive"

    async def test_readiness(self, client: AsyncClient) -> None:
        response = await client.get("/readiness")
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] in ("ready", "not_ready")

    async def test_metrics(self, client: AsyncClient) -> None:
        response = await client.get("/metrics")
        assert response.status_code == HTTP_OK


class TestAuth:
    async def test_missing_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get("/backup/jobs")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_non_admin_cannot_create_job(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id, roles=["viewer"])
        response = await client.post(
            "/backup/jobs",
            json={"target_id": str(uuid4()), "backup_type": "full"},
            headers=headers,
        )
        assert response.status_code == HTTP_FORBIDDEN


async def _create_target(repos, organization_id: UUID) -> BackupTarget:
    return await repos.targets.create(
        BackupTarget(
            organization_id=organization_id, name="db-1", target_kind=BackupTargetKind.POSTGRESQL
        )
    )


class TestJobRoutes:
    async def test_list_jobs_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/backup/jobs", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["jobs"] == []

    async def test_create_and_list_job(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        target = await _create_target(repos, organization_id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/backup/jobs",
            json={"target_id": str(target.id), "backup_type": "full"},
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        job_id = response.json()["data"]["id"]

        list_response = await client.get("/backup/jobs", headers=headers)
        job_ids = [job["id"] for job in list_response.json()["data"]["jobs"]]
        assert job_id in job_ids

    async def test_create_job_unknown_target_404(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/backup/jobs",
            json={"target_id": str(uuid4()), "backup_type": "full"},
            headers=headers,
        )
        assert response.status_code >= HTTP_FORBIDDEN


class TestScheduleRoutes:
    async def test_list_schedules_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/backup/schedules", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["schedules"] == []

    async def test_create_schedule(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        target = await _create_target(repos, organization_id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/backup/schedules",
            json={
                "target_id": str(target.id),
                "backup_type": "full",
                "frequency": "daily",
                "retention_days": 30,
            },
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["frequency"] == "daily"


class TestSnapshotRoutes:
    async def test_list_snapshots_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/backup/snapshots", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["snapshots"] == []


class TestRestoreRoute:
    async def test_restore_no_points_available(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/backup/restore",
            json={
                "target_id": str(uuid4()),
                "restore_kind": "full",
                "requested_at": NOW.isoformat(),
            },
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        data = response.json()["data"]
        assert data["restore_job_id"] is None
        assert data["refusal"] == "no_points_available"

    async def test_restore_selects_point_and_starts_job(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        from app.models.recovery import RestorePoint

        target = await _create_target(repos, organization_id)
        await repos.restore_points.create(
            RestorePoint(
                organization_id=organization_id,
                target_id=target.id,
                point_kind="backup_completion",
                available_at=NOW - timedelta(hours=1),
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/backup/restore",
            json={
                "target_id": str(target.id),
                "restore_kind": "full",
                "requested_at": NOW.isoformat(),
                "is_preview": True,
            },
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        data = response.json()["data"]
        assert data["restore_job_id"] is not None


class TestFailoverRoutes:
    async def test_failover_unauthorized_without_health_checks(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/backup/failover",
            json={"kind": "automatic", "health_checks": []},
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        data = response.json()["data"]
        assert not data["is_authorized"]
        assert data["refusal"] == "no_health_checks_ran"

    async def test_failover_authorized_manual(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/backup/failover",
            json={"kind": "manual", "source_ref": "primary", "target_ref": "standby"},
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        data = response.json()["data"]
        assert data["is_authorized"]
        assert data["failover_event_id"] is not None

    async def test_failback_forces_failback_kind(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/backup/failback",
            json={"kind": "manual"},
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["is_authorized"]


class TestDrPlanAndTestRoutes:
    async def test_list_dr_plans_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/backup/dr-plans", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["plans"] == []

    async def test_create_dr_test(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        plan = await repos.dr_plans.create(
            DrPlan(
                organization_id=organization_id,
                name="plan-1",
                rpo_minutes=60,
                rto_minutes=120,
                is_active=True,
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/backup/dr-tests",
            json={
                "dr_plan_id": str(plan.id),
                "test_kind": "simulation",
                "achieved_rpo_minutes": 30.0,
                "achieved_rto_minutes": 90.0,
                "summary": "all good",
            },
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["status"] == "passed"


class TestStatisticsAndReportRoutes:
    async def test_get_statistics_default_window(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/backup/statistics", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["windows"] == []

    async def test_list_reports_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/backup/reports", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["reports"] == []
