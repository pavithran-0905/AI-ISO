"""Integration tests for background workers, against real PostgreSQL.

Uses real wall-clock time (``datetime.now(UTC)``) throughout, matching
every worker's own internal ``now = datetime.now(UTC)`` -- a fixed
historical constant would fall outside a worker's real query window and
produce tests that pass without the loop body ever executing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models.api_management import ApiKey
from app.models.enums import (
    ApiKeyStatus,
    JobPriority,
    JobStatus,
    MaintenanceKind,
    MaintenanceStatus,
    OrganizationStatus,
    TenantStatus,
)
from app.models.jobs import SystemJob
from app.models.maintenance import MaintenanceWindow
from app.models.tenants import Organization, Tenant
from app.workers.api_key_expiry_sweep import ApiKeyExpirySweepWorker
from app.workers.health_sweep import HealthSweepWorker
from app.workers.job_retry_sweep import JobRetrySweepWorker
from app.workers.maintenance_sweep import MaintenanceSweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker


def now() -> datetime:
    return datetime.now(UTC)


async def _noop_publish(event: object) -> None:
    pass


def _organization(organization_id: UUID, **kwargs: object) -> Organization:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "name": "Acme",
        "status": OrganizationStatus.ACTIVE,
    }
    defaults.update(kwargs)
    return Organization(**defaults)


def _tenant(organization_id: UUID, organization_ref_id: UUID, **kwargs: object) -> Tenant:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "organization_ref_id": organization_ref_id,
        "name": "Tenant A",
        "status": TenantStatus.ACTIVE,
    }
    defaults.update(kwargs)
    return Tenant(**defaults)


class TestHealthSweepWorker:
    async def test_tick_records_diagnostics_and_health_checks(
        self, db_session_factory, pg_engine, cache_framework, repos, organization_id: UUID
    ) -> None:
        org = await repos.organizations.create(_organization(organization_id))
        await repos.tenants.create(_tenant(organization_id, org.id))

        worker = HealthSweepWorker(
            db_session_factory,
            db_engine=pg_engine,
            redis_client=cache_framework.client,
            publish_event=_noop_publish,
            warning_ms=200.0,
            critical_ms=2_000.0,
        )
        checked = await worker.tick()
        assert checked == 1

        checks = await repos.health_checks.list_all(organization_id)
        components = {c.component for c in checks}
        assert components == {"database", "cache"}

    async def test_tick_no_organizations_checks_nothing(
        self, db_session_factory, pg_engine, cache_framework
    ) -> None:
        worker = HealthSweepWorker(
            db_session_factory,
            db_engine=pg_engine,
            redis_client=cache_framework.client,
            publish_event=_noop_publish,
            warning_ms=200.0,
            critical_ms=2_000.0,
        )
        assert await worker.tick() == 0


class TestMaintenanceSweepWorker:
    async def test_tick_starts_due_approved_window(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        window = await repos.maintenance_windows.create(
            MaintenanceWindow(
                organization_id=organization_id,
                title="Upgrade",
                kind=MaintenanceKind.ROUTINE,
                status=MaintenanceStatus.APPROVED,
                starts_at=now() - timedelta(minutes=1),
                ends_at=now() + timedelta(hours=1),
            )
        )
        worker = MaintenanceSweepWorker(db_session_factory, publish_event=_noop_publish)
        transitioned = await worker.tick()
        assert transitioned == 1

        await db_session.refresh(window)
        assert window.status == MaintenanceStatus.IN_PROGRESS

    async def test_tick_completes_due_in_progress_window(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        window = await repos.maintenance_windows.create(
            MaintenanceWindow(
                organization_id=organization_id,
                title="Upgrade",
                kind=MaintenanceKind.ROUTINE,
                status=MaintenanceStatus.IN_PROGRESS,
                starts_at=now() - timedelta(hours=2),
                ends_at=now() - timedelta(minutes=1),
            )
        )
        worker = MaintenanceSweepWorker(db_session_factory, publish_event=_noop_publish)
        await worker.tick()

        await db_session.refresh(window)
        assert window.status == MaintenanceStatus.COMPLETED

    async def test_tick_leaves_not_yet_due_window_alone(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        window = await repos.maintenance_windows.create(
            MaintenanceWindow(
                organization_id=organization_id,
                title="Upgrade",
                kind=MaintenanceKind.ROUTINE,
                status=MaintenanceStatus.APPROVED,
                starts_at=now() + timedelta(hours=1),
                ends_at=now() + timedelta(hours=2),
            )
        )
        worker = MaintenanceSweepWorker(db_session_factory, publish_event=_noop_publish)
        assert await worker.tick() == 0
        await db_session.refresh(window)
        assert window.status == MaintenanceStatus.APPROVED

    async def test_tick_no_organizations_transitions_nothing(self, db_session_factory) -> None:
        worker = MaintenanceSweepWorker(db_session_factory, publish_event=_noop_publish)
        assert await worker.tick() == 0


class TestJobRetrySweepWorker:
    async def test_tick_retries_failed_job_past_backoff(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        job = await repos.jobs.create(
            SystemJob(
                organization_id=organization_id,
                job_key="sync",
                status=JobStatus.FAILED,
                priority=JobPriority.NORMAL,
                queued_at=now() - timedelta(minutes=5),
                completed_at=now() - timedelta(minutes=5),
                attempt_count=1,
                max_attempts=3,
            )
        )
        worker = JobRetrySweepWorker(db_session_factory, backoff_base_seconds=1)
        retried = await worker.tick()
        assert retried == 1

        await db_session.refresh(job)
        assert job.status == JobStatus.RETRYING
        assert job.attempt_count == 2

    async def test_tick_dead_letters_exhausted_job(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        job = await repos.jobs.create(
            SystemJob(
                organization_id=organization_id,
                job_key="sync",
                status=JobStatus.FAILED,
                priority=JobPriority.NORMAL,
                queued_at=now() - timedelta(minutes=5),
                completed_at=now() - timedelta(minutes=5),
                attempt_count=3,
                max_attempts=3,
            )
        )
        worker = JobRetrySweepWorker(db_session_factory, backoff_base_seconds=1)
        await worker.tick()

        await db_session.refresh(job)
        assert job.status == JobStatus.DEAD_LETTER

    async def test_tick_leaves_job_within_backoff_window_alone(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        job = await repos.jobs.create(
            SystemJob(
                organization_id=organization_id,
                job_key="sync",
                status=JobStatus.FAILED,
                priority=JobPriority.NORMAL,
                queued_at=now(),
                completed_at=now(),
                attempt_count=1,
                max_attempts=3,
            )
        )
        worker = JobRetrySweepWorker(db_session_factory, backoff_base_seconds=3_600)
        assert await worker.tick() == 0
        await db_session.refresh(job)
        assert job.status == JobStatus.FAILED

    async def test_tick_no_organizations_retries_nothing(self, db_session_factory) -> None:
        worker = JobRetrySweepWorker(db_session_factory, backoff_base_seconds=60)
        assert await worker.tick() == 0


class TestApiKeyExpirySweepWorker:
    async def test_tick_expires_key_past_expiry(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        key = await repos.api_keys.create(
            ApiKey(
                organization_id=organization_id,
                name="ci-key",
                key_hash="hash-1",
                status=ApiKeyStatus.ACTIVE,
                expires_at=now() - timedelta(days=1),
            )
        )
        worker = ApiKeyExpirySweepWorker(db_session_factory)
        expired = await worker.tick()
        assert expired == 1

        await db_session.refresh(key)
        assert key.status == ApiKeyStatus.EXPIRED

    async def test_tick_leaves_unexpired_key_alone(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        key = await repos.api_keys.create(
            ApiKey(
                organization_id=organization_id,
                name="ci-key",
                key_hash="hash-2",
                status=ApiKeyStatus.ACTIVE,
                expires_at=now() + timedelta(days=365),
            )
        )
        worker = ApiKeyExpirySweepWorker(db_session_factory)
        await worker.tick()
        await db_session.refresh(key)
        assert key.status == ApiKeyStatus.ACTIVE

    async def test_tick_no_organizations_expires_nothing(self, db_session_factory) -> None:
        worker = ApiKeyExpirySweepWorker(db_session_factory)
        assert await worker.tick() == 0


class TestStatisticsRollupWorker:
    async def test_tick_rolls_up_current_window_idempotently(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        org = await repos.organizations.create(_organization(organization_id))
        await repos.tenants.create(_tenant(organization_id, org.id))

        worker = StatisticsRollupWorker(db_session_factory)
        rolled_first = await worker.tick()
        rolled_second = await worker.tick()
        assert rolled_first == rolled_second == 1

        window_end = now().replace(minute=0, second=0, microsecond=0)
        window_start = window_end - timedelta(hours=1)
        statistic = await repos.statistics.find_window(organization_id, window_start=window_start)
        assert statistic is not None
        assert statistic.tenant_count == 1

    async def test_tick_no_organizations_rolls_up_nothing(self, db_session_factory) -> None:
        worker = StatisticsRollupWorker(db_session_factory)
        assert await worker.tick() == 0
