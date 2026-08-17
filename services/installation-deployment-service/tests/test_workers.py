"""Integration tests for every worker's ``tick()``, against real
PostgreSQL, exercised directly rather than through the scheduler."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.deployment import DeploymentJob, DeploymentProfile
from app.models.enums import (
    DeploymentEngine,
    DeploymentJobStatus,
    DeploymentJobType,
    DeploymentStrategy,
    DeploymentTargetType,
    InstallationMode,
    InstallationSessionStatus,
    TlsCertificateStatus,
)
from app.models.installation import InstallationSession
from app.models.secrets_tls import TlsCertificate
from app.services.bundle import build_repositories
from app.workers.certificate_expiry_sweep import CertificateExpirySweepWorker
from app.workers.deployment_job_timeout_sweep import DeploymentJobTimeoutSweepWorker
from app.workers.installation_session_expiry_sweep import InstallationSessionExpirySweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from app.workers.upgrade_availability_sweep import UpgradeAvailabilitySweepWorker
from tests.conftest import RecordingNotifier, hours_ago, utcnow


class TestInstallationSessionExpirySweepWorker:
    async def test_fails_only_timed_out_sessions(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        repos = build_repositories(db_session)
        stuck = await repos.installation_sessions.create(
            InstallationSession(
                organization_id=organization_id,
                mode=InstallationMode.CLI,
                status=InstallationSessionStatus.RUNNING,
                started_at=hours_ago(10),
            )
        )
        fresh = await repos.installation_sessions.create(
            InstallationSession(
                organization_id=organization_id,
                mode=InstallationMode.CLI,
                status=InstallationSessionStatus.RUNNING,
                started_at=utcnow(),
            )
        )
        await db_session.flush()

        worker = InstallationSessionExpirySweepWorker(
            db_session_factory, notifier=notifier, max_age_hours=6  # type: ignore[arg-type]
        )
        failed = await worker.tick()
        assert failed >= 1

        await db_session.refresh(stuck)
        await db_session.refresh(fresh)
        assert stuck.status == "failed"
        assert fresh.status == "running"
        assert any(call[0] == "notify_installation_failed" for call in notifier.calls)


class TestDeploymentJobTimeoutSweepWorker:
    async def test_fails_only_stuck_jobs(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        repos = build_repositories(db_session)
        profile = await repos.profiles.create(
            DeploymentProfile(
                organization_id=organization_id,
                name="p1",
                target_type=DeploymentTargetType.DOCKER_COMPOSE,
                installation_mode=InstallationMode.CLI,
                engine=DeploymentEngine.DOCKER_COMPOSE,
                strategy=DeploymentStrategy.ROLLING,
            )
        )
        stuck = await repos.jobs.create(
            DeploymentJob(
                organization_id=organization_id,
                deployment_profile_id=profile.id,
                job_type=DeploymentJobType.DEPLOY,
                status=DeploymentJobStatus.RUNNING,
                started_at=hours_ago(10),
            )
        )
        fresh = await repos.jobs.create(
            DeploymentJob(
                organization_id=organization_id,
                deployment_profile_id=profile.id,
                job_type=DeploymentJobType.DEPLOY,
                status=DeploymentJobStatus.RUNNING,
                started_at=utcnow(),
            )
        )
        await db_session.flush()

        worker = DeploymentJobTimeoutSweepWorker(
            db_session_factory, notifier=notifier, max_age_hours=4  # type: ignore[arg-type]
        )
        failed = await worker.tick()
        assert failed >= 1

        await db_session.refresh(stuck)
        await db_session.refresh(fresh)
        assert stuck.status == "failed"
        assert fresh.status == "running"
        assert any(call[0] == "notify_deployment_failed" for call in notifier.calls)


class TestCertificateExpirySweepWorker:
    async def test_notifies_only_on_transition_to_expiring(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        repos = build_repositories(db_session)
        await repos.tls_certificates.create(
            TlsCertificate(
                organization_id=organization_id,
                common_name="soon-to-expire.local",
                not_before=hours_ago(24),
                not_after=hours_ago(-24),  # 1 day from now -- inside a 30-day warning window
                status=TlsCertificateStatus.VALID,
            )
        )
        await db_session.flush()

        worker = CertificateExpirySweepWorker(
            db_session_factory, notifier=notifier, warning_days=30  # type: ignore[arg-type]
        )
        first_tick = await worker.tick()
        assert first_tick == 1
        assert len([c for c in notifier.calls if c[0] == "notify_certificate_expiring"]) == 1

        second_tick = await worker.tick()
        assert second_tick == 0
        assert len([c for c in notifier.calls if c[0] == "notify_certificate_expiring"]) == 1


class TestStatisticsRollupWorker:
    async def test_rolls_up_and_is_idempotent(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> None:
        repos = build_repositories(db_session)
        await repos.installation_sessions.create(
            InstallationSession(
                organization_id=organization_id, mode=InstallationMode.CLI, started_at=hours_ago(1)
            )
        )
        await db_session.flush()

        worker = StatisticsRollupWorker(db_session_factory, window_hours=3)
        first_rolled = await worker.tick()
        assert first_rolled >= 1
        second_rolled = await worker.tick()
        assert second_rolled >= 1

        stats = await repos.statistics.list_range(organization_id, since=hours_ago(72))
        assert len(stats) == 1
        assert stats[0].installation_count == 1

    async def test_deployment_and_failure_counts_reflect_real_activity(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> None:
        repos = build_repositories(db_session)
        profile = await repos.profiles.create(
            DeploymentProfile(
                organization_id=organization_id,
                name="p2",
                target_type=DeploymentTargetType.DOCKER_COMPOSE,
                installation_mode=InstallationMode.CLI,
                engine=DeploymentEngine.DOCKER_COMPOSE,
                strategy=DeploymentStrategy.ROLLING,
            )
        )
        await repos.jobs.create(
            DeploymentJob(
                organization_id=organization_id,
                deployment_profile_id=profile.id,
                job_type=DeploymentJobType.DEPLOY,
                status=DeploymentJobStatus.SUCCEEDED,
                started_at=hours_ago(1),
                completed_at=hours_ago(1),
            )
        )
        await repos.jobs.create(
            DeploymentJob(
                organization_id=organization_id,
                deployment_profile_id=profile.id,
                job_type=DeploymentJobType.DEPLOY,
                status=DeploymentJobStatus.FAILED,
                started_at=hours_ago(1),
                completed_at=hours_ago(1),
            )
        )
        await db_session.flush()

        worker = StatisticsRollupWorker(db_session_factory, window_hours=3)
        await worker.tick()

        stats = await repos.statistics.list_range(organization_id, since=hours_ago(72))
        assert stats[0].deployment_count == 2
        assert stats[0].success_count == 1
        assert stats[0].failure_count == 1


class TestUpgradeAvailabilitySweepWorker:
    async def test_notifies_when_newer_version_recently_released(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        from app.models.deployment import DeploymentVersion

        repos = build_repositories(db_session)
        await repos.versions.create(
            DeploymentVersion(
                organization_id=organization_id,
                version_label="1.0.0",
                released_at=hours_ago(48),
                is_current=True,
            )
        )
        await repos.versions.create(
            DeploymentVersion(
                organization_id=organization_id, version_label="1.1.0", released_at=hours_ago(0.1)
            )
        )
        await db_session.flush()

        worker = UpgradeAvailabilitySweepWorker(
            db_session_factory, notifier=notifier, lookback_seconds=3600  # type: ignore[arg-type]
        )
        notified = await worker.tick()
        assert notified == 1
        assert ("notify_upgrade_available", {"version": "1.1.0"}) in notifier.calls

    async def test_does_not_notify_once_outside_lookback_window(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        from app.models.deployment import DeploymentVersion

        repos = build_repositories(db_session)
        await repos.versions.create(
            DeploymentVersion(
                organization_id=organization_id,
                version_label="1.0.0",
                released_at=hours_ago(48),
                is_current=True,
            )
        )
        await repos.versions.create(
            DeploymentVersion(
                organization_id=organization_id, version_label="1.1.0", released_at=hours_ago(10)
            )
        )
        await db_session.flush()

        worker = UpgradeAvailabilitySweepWorker(
            db_session_factory, notifier=notifier, lookback_seconds=3600  # type: ignore[arg-type]
        )
        notified = await worker.tick()
        assert notified == 0
        assert notifier.calls == []

    async def test_run_job_entry_point_matches_scheduler_signature(
        self, db_session_factory: async_sessionmaker[AsyncSession], notifier: RecordingNotifier
    ) -> None:
        worker = UpgradeAvailabilitySweepWorker(
            db_session_factory, notifier=notifier, lookback_seconds=3600  # type: ignore[arg-type]
        )
        await worker.run_job(object())
