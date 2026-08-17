"""API integration tests for all 10 REST routes, exercised through the
real FastAPI app (real DB session, real JWT verification)."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compatibility import CompatibilityMatrixEntry
from app.models.enums import (
    CheckResultStatus,
    CompatibilityType,
    ReleaseChannelType,
    ReportFormat,
    ReportStatus,
    UpgradeReportKind,
    UpgradeStrategy,
    UpgradeTargetType,
)
from app.models.releases import ReleaseChannel, ReleaseVersion
from app.models.reporting import UpgradeReport, UpgradeStatistic
from app.models.upgrade import UpgradePlan
from app.services.bundle import build_repositories
from tests.conftest import (
    HTTP_FORBIDDEN,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    AuthHeadersFn,
    hours_ago,
    utcnow,
)


async def _seed_plan(db_session: AsyncSession, organization_id: uuid.UUID) -> UpgradePlan:
    repos = build_repositories(db_session)
    return await repos.plans.create(
        UpgradePlan(
            organization_id=organization_id,
            name="api-plan",
            target_type=UpgradeTargetType.PLATFORM_SERVICE,
            strategy=UpgradeStrategy.ROLLING,
            from_version="1.0.0",
            to_version="1.1.0",
        )
    )


class TestReleasesAndChannelsRoutes:
    async def test_list_channels_and_releases(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        repos = build_repositories(db_session)
        channel = await repos.channels.create(
            ReleaseChannel(
                organization_id=organization_id,
                name="stable",
                channel_type=ReleaseChannelType.STABLE,
            )
        )
        await repos.versions.create(
            ReleaseVersion(
                organization_id=organization_id,
                release_channel_id=channel.id,
                version_label="1.0.0",
                released_at=utcnow(),
            )
        )
        await db_session.flush()
        headers = auth_headers("tester", organization_id=organization_id)

        channels_response = await client.get("/channels", headers=headers)
        assert channels_response.status_code == HTTP_OK
        assert channels_response.json()["data"]["total"] == 1

        releases_response = await client.get("/releases", headers=headers)
        assert releases_response.status_code == HTTP_OK
        assert releases_response.json()["data"]["total"] == 1

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.get("/channels")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_requires_administrator(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("tester", organization_id=organization_id, roles=["developer"])
        response = await client.get("/channels", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN


class TestUpgradeRoutes:
    async def test_start_upgrade_then_list_jobs_and_history(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        plan = await _seed_plan(db_session, organization_id)
        headers = auth_headers("tester", organization_id=organization_id)
        started = await client.post(
            "/upgrade",
            headers=headers,
            json={"upgrade_plan_id": str(plan.id), "plan_name": "api-plan"},
        )
        assert started.status_code == HTTP_OK
        assert started.json()["data"]["status"] == "running"

        jobs_response = await client.get("/upgrade/jobs", headers=headers)
        assert jobs_response.status_code == HTTP_OK
        assert jobs_response.json()["data"]["total"] == 1

        history_response = await client.get("/upgrade/history", headers=headers)
        assert history_response.status_code == HTTP_OK
        assert history_response.json()["data"]["total"] >= 1


class TestUpgradeSimulateRoute:
    async def test_simulate_returns_risk_and_duration(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        response = await client.post(
            "/upgrade/simulate",
            headers=auth_headers("tester", organization_id=organization_id),
            json={
                "compatibility_results": ["passed"],
                "dependency_results": ["warning"],
                "target_count": 4,
                "seconds_per_target": 10.0,
            },
        )
        assert response.status_code == HTTP_OK
        data = response.json()["data"]
        assert data["risk_level"] == "medium"
        assert data["estimated_duration_seconds"] == 40.0


class TestRollbackRoute:
    async def test_rollback_initiates(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        plan = await _seed_plan(db_session, organization_id)
        repos = build_repositories(db_session)
        channel = await repos.channels.create(
            ReleaseChannel(
                organization_id=organization_id,
                name="stable-rb",
                channel_type=ReleaseChannelType.STABLE,
            )
        )
        await repos.versions.create(
            ReleaseVersion(
                organization_id=organization_id,
                release_channel_id=channel.id,
                version_label="1.0.0",
                released_at=hours_ago(2),
            )
        )
        await repos.versions.create(
            ReleaseVersion(
                organization_id=organization_id,
                release_channel_id=channel.id,
                version_label="2.0.0",
                released_at=hours_ago(1),
            )
        )
        await db_session.flush()

        response = await client.post(
            "/rollback",
            headers=auth_headers("tester", organization_id=organization_id),
            json={
                "upgrade_plan_id": str(plan.id),
                "current_version": "2.0.0",
                "target_version": "1.0.0",
                "reason": "bad release",
            },
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["to_version"] == "1.0.0"


class TestCompatibilityRoute:
    async def test_lists_entries(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        repos = build_repositories(db_session)
        await repos.compatibility.create(
            CompatibilityMatrixEntry(
                organization_id=organization_id,
                from_version="1.0.0",
                to_version="1.1.0",
                compatibility_type=CompatibilityType.API,
                status=CheckResultStatus.PASSED,
            )
        )
        await db_session.flush()

        response = await client.get(
            "/compatibility", headers=auth_headers("tester", organization_id=organization_id)
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1


class TestReportsAndStatisticsRoutes:
    async def test_reports_lists_recent(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        repos = build_repositories(db_session)
        await repos.reports.create(
            UpgradeReport(
                organization_id=organization_id,
                kind=UpgradeReportKind.UPGRADE,
                report_format=ReportFormat.JSON,
                title="Upgrade report",
                status=ReportStatus.COMPLETED,
                period_start=hours_ago(1),
                period_end=utcnow(),
            )
        )
        await db_session.flush()

        response = await client.get(
            "/reports", headers=auth_headers("tester", organization_id=organization_id)
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1

    async def test_statistics_lists_range(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        repos = build_repositories(db_session)
        await repos.statistics.create(
            UpgradeStatistic(
                organization_id=organization_id, window_start=hours_ago(1), window_end=utcnow()
            )
        )
        await db_session.flush()

        response = await client.get(
            "/statistics", headers=auth_headers("tester", organization_id=organization_id)
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1
