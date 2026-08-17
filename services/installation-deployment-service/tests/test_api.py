"""API integration tests for all 10 REST routes, exercised through the
real FastAPI app (real DB session, real JWT verification)."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import DeploymentJob, DeploymentProfile, DeploymentVersion
from app.models.enums import (
    CheckResultStatus,
    DeploymentEngine,
    DeploymentJobType,
    DeploymentReportKind,
    DeploymentStrategy,
    DeploymentTargetType,
    InstallationMode,
    ReportFormat,
    ReportStatus,
    VerificationCheckType,
)
from app.models.reporting import DeploymentReport, DeploymentStatistic
from app.models.verification import VerificationResult
from app.services.bundle import build_repositories
from tests.conftest import (
    HTTP_FORBIDDEN,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    AuthHeadersFn,
    hours_ago,
    utcnow,
)


async def _seed_profile(db_session: AsyncSession, organization_id: uuid.UUID) -> DeploymentProfile:
    repos = build_repositories(db_session)
    return await repos.profiles.create(
        DeploymentProfile(
            organization_id=organization_id,
            name="api-profile",
            target_type=DeploymentTargetType.DOCKER_COMPOSE,
            installation_mode=InstallationMode.CLI,
            engine=DeploymentEngine.DOCKER_COMPOSE,
            strategy=DeploymentStrategy.ROLLING,
        )
    )


class TestInstallRoutes:
    async def test_start_then_status(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("tester", organization_id=organization_id)
        started = await client.post("/install/start", headers=headers, json={"mode": "cli"})
        assert started.status_code == HTTP_OK
        session_id = started.json()["data"]["id"]
        assert started.json()["data"]["status"] == "running"

        status_response = await client.get(
            "/install/status", headers=headers, params={"installation_session_id": session_id}
        )
        assert status_response.status_code == HTTP_OK
        assert status_response.json()["data"]["id"] == session_id

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.post("/install/start", json={"mode": "cli"})
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_requires_administrator(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("tester", organization_id=organization_id, roles=["developer"])
        response = await client.post("/install/start", headers=headers, json={"mode": "cli"})
        assert response.status_code == HTTP_FORBIDDEN


class TestInstallValidateRoute:
    async def test_records_preflight_result(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        response = await client.post(
            "/install/validate",
            headers=auth_headers("tester", organization_id=organization_id),
            json={"check_type": "cpu", "status": "passed", "detail": "8 cores available"},
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] == "passed"


class TestDeployRoutes:
    async def test_deploy_then_status(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        profile = await _seed_profile(db_session, organization_id)
        headers = auth_headers("tester", organization_id=organization_id)
        deployed = await client.post(
            "/deploy",
            headers=headers,
            json={"deployment_profile_id": str(profile.id), "job_type": "deploy"},
        )
        assert deployed.status_code == HTTP_OK
        assert deployed.json()["data"]["status"] == "running"
        job_id = deployed.json()["data"]["id"]

        status_response = await client.get(
            "/deploy/status", headers=headers, params={"deployment_job_id": job_id}
        )
        assert status_response.status_code == HTTP_OK
        assert status_response.json()["data"]["id"] == job_id


class TestUpgradeRoute:
    async def test_upgrade_initiates(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        profile = await _seed_profile(db_session, organization_id)
        response = await client.post(
            "/upgrade",
            headers=auth_headers("tester", organization_id=organization_id),
            json={
                "deployment_profile_id": str(profile.id),
                "from_version": "1.0.0",
                "to_version": "1.1.0",
            },
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["to_version"] == "1.1.0"


class TestRollbackRoute:
    async def test_rollback_initiates(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        profile = await _seed_profile(db_session, organization_id)
        repos = build_repositories(db_session)
        await repos.versions.create(
            DeploymentVersion(
                organization_id=organization_id, version_label="1.0.0", released_at=hours_ago(2)
            )
        )
        await repos.versions.create(
            DeploymentVersion(
                organization_id=organization_id, version_label="2.0.0", released_at=hours_ago(1)
            )
        )
        await db_session.flush()

        response = await client.post(
            "/rollback",
            headers=auth_headers("tester", organization_id=organization_id),
            json={
                "deployment_profile_id": str(profile.id),
                "current_version": "2.0.0",
                "target_version": "1.0.0",
                "reason": "bad release",
            },
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["to_version"] == "1.0.0"


class TestVerificationRoute:
    async def test_lists_recent_results(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        profile = await _seed_profile(db_session, organization_id)
        repos = build_repositories(db_session)
        job = await repos.jobs.create(
            DeploymentJob(
                organization_id=organization_id,
                deployment_profile_id=profile.id,
                job_type=DeploymentJobType.DEPLOY,
            )
        )
        await repos.verification_results.create(
            VerificationResult(
                organization_id=organization_id,
                deployment_job_id=job.id,
                check_type=VerificationCheckType.HEALTH,
                status=CheckResultStatus.PASSED,
                verified_at=utcnow(),
            )
        )
        await db_session.flush()

        response = await client.get(
            "/verification", headers=auth_headers("tester", organization_id=organization_id)
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
            DeploymentReport(
                organization_id=organization_id,
                kind=DeploymentReportKind.DEPLOYMENT,
                report_format=ReportFormat.JSON,
                title="Deploy report",
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
            DeploymentStatistic(
                organization_id=organization_id, window_start=hours_ago(1), window_end=utcnow()
            )
        )
        await db_session.flush()

        response = await client.get(
            "/statistics", headers=auth_headers("tester", organization_id=organization_id)
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1
