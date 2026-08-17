"""Integration tests for every worker, against real PostgreSQL.

Each worker is exercised by calling its own ``tick()`` directly --
never through the scheduler -- matching every other service's own
worker test shape in this codebase.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.certificates import CertificateInventoryEntry
from app.models.certification import ProductionCertification
from app.models.compliance import ComplianceResult
from app.models.enums import (
    CertificationStatus,
    CheckResultStatus,
    CisBenchmark,
    ComplianceFramework,
    HardeningRunStatus,
    HardeningTargetType,
)
from app.models.hardening_definitions import HardeningProfile
from app.models.hardening_execution import HardeningResult, HardeningRun
from app.services.bundle import Repositories, build_repositories
from app.services.notifications import HardeningNotifier
from app.workers.certificate_expiry_sweep import CertificateExpirySweepWorker
from app.workers.certification_expiry_sweep import CertificationExpirySweepWorker
from app.workers.hardening_run_timeout_sweep import HardeningRunTimeoutSweepWorker
from app.workers.production_readiness_sweep import ProductionReadinessSweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from tests.conftest import RecordingNotifier, RecordingPublisher, hours_ago, utcnow


class TestHardeningRunTimeoutSweepWorkerBehaviour:
    async def test_fails_stuck_run_on_next_tick(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
    ) -> None:
        profile = await repos.hardening_profiles.create(
            HardeningProfile(
                organization_id=organization_id,
                name="worker-profile",
                target_type=HardeningTargetType.OS,
                benchmark=CisBenchmark.LINUX_CIS,
            )
        )
        stuck_run = await repos.hardening_runs.create(
            HardeningRun(
                organization_id=organization_id,
                hardening_profile_id=profile.id,
                status=HardeningRunStatus.RUNNING,
                started_at=hours_ago(5),
            )
        )
        fresh_run = await repos.hardening_runs.create(
            HardeningRun(
                organization_id=organization_id,
                hardening_profile_id=profile.id,
                status=HardeningRunStatus.RUNNING,
                started_at=utcnow(),
            )
        )
        await db_session.commit()

        worker = HardeningRunTimeoutSweepWorker(db_session_factory, max_age_hours=4)
        failed = await worker.tick()
        assert failed == 1

        async with db_session_factory() as session:
            check_repos = build_repositories(session)
            reread_stuck = await check_repos.hardening_runs.require_by_id(stuck_run.id)
            reread_fresh = await check_repos.hardening_runs.require_by_id(fresh_run.id)
        assert reread_stuck.status == "failed"
        assert reread_fresh.status == "running"


class TestCertificateExpirySweepWorkerBehaviour:
    async def test_notifies_once_for_newly_expiring_certificate(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        certificate = await repos.certificate_inventory.create(
            CertificateInventoryEntry(
                organization_id=organization_id,
                subject="api.example.com",
                expires_at=hours_ago(-24 * 10),
            )
        )
        await db_session.commit()

        worker = CertificateExpirySweepWorker(  # type: ignore[arg-type]
            db_session_factory, notifier=notifier, warning_days=30
        )
        first_tick = await worker.tick()
        assert first_tick == 1
        assert any(call[0] == "notify_certificate_expiring" for call in notifier.calls)

        notifier.calls.clear()
        second_tick = await worker.tick()
        assert second_tick == 0
        assert notifier.calls == []

        async with db_session_factory() as session:
            check_repos = build_repositories(session)
            reread = await check_repos.certificate_inventory.require_by_id(certificate.id)
        assert reread.is_expiring is True

    async def test_no_notification_when_not_expiring_soon(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        await repos.certificate_inventory.create(
            CertificateInventoryEntry(
                organization_id=organization_id,
                subject="far-future.example.com",
                expires_at=hours_ago(-24 * 365),
            )
        )
        await db_session.commit()

        worker = CertificateExpirySweepWorker(  # type: ignore[arg-type]
            db_session_factory, notifier=notifier, warning_days=30
        )
        notified = await worker.tick()
        assert notified == 0
        assert notifier.calls == []


class TestCertificationExpirySweepWorkerBehaviour:
    async def test_expires_overdue_certification_and_notifies(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        certification = await repos.production_certifications.create(
            ProductionCertification(
                organization_id=organization_id,
                name="core-platform",
                status=CertificationStatus.GRANTED,
                granted_at=hours_ago(24 * 400),
                expires_at=hours_ago(1),
            )
        )
        await db_session.commit()

        worker = CertificationExpirySweepWorker(db_session_factory, notifier=notifier)  # type: ignore[arg-type]
        expired = await worker.tick()
        assert expired == 1
        assert any(call[0] == "notify_certification_expired" for call in notifier.calls)

        async with db_session_factory() as session:
            check_repos = build_repositories(session)
            reread = await check_repos.production_certifications.require_by_id(certification.id)
        assert reread.status == "expired"

        notifier.calls.clear()
        second_tick = await worker.tick()
        assert second_tick == 0
        assert notifier.calls == []

    async def test_no_expiry_for_future_certification(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        await repos.production_certifications.create(
            ProductionCertification(
                organization_id=organization_id,
                name="future-cert",
                status=CertificationStatus.GRANTED,
                granted_at=utcnow(),
                expires_at=hours_ago(-24 * 300),
            )
        )
        await db_session.commit()

        worker = CertificationExpirySweepWorker(db_session_factory, notifier=notifier)  # type: ignore[arg-type]
        expired = await worker.tick()
        assert expired == 0


class TestProductionReadinessSweepWorkerBehaviour:
    async def test_publishes_ready_when_signals_are_recent_and_perfect(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
    ) -> None:
        profile = await repos.hardening_profiles.create(
            HardeningProfile(
                organization_id=organization_id,
                name="readiness-profile",
                target_type=HardeningTargetType.OS,
                benchmark=CisBenchmark.LINUX_CIS,
            )
        )
        run = await repos.hardening_runs.create(
            HardeningRun(organization_id=organization_id, hardening_profile_id=profile.id)
        )
        for _ in range(4):
            await repos.hardening_results.create(
                HardeningResult(
                    organization_id=organization_id,
                    hardening_run_id=run.id,
                    check_name="cis-1.1.1",
                    status=CheckResultStatus.PASSED,
                )
            )
        for _ in range(4):
            await repos.compliance_results.create(
                ComplianceResult(
                    organization_id=organization_id,
                    framework=ComplianceFramework.SOC2,
                    control_id="CC6.1",
                    is_compliant=True,
                    evaluated_at=utcnow(),
                )
            )
        await db_session.commit()

        worker = ProductionReadinessSweepWorker(
            db_session_factory, publish=publisher, threshold=0.3, lookback_seconds=3600  # type: ignore[arg-type]
        )
        ready_count = await worker.tick()
        assert ready_count == 1
        assert "ProductionReady" in publisher.names()

    async def test_no_evaluation_when_nothing_recent(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
    ) -> None:
        profile = await repos.hardening_profiles.create(
            HardeningProfile(
                organization_id=organization_id,
                name="stale-profile",
                target_type=HardeningTargetType.OS,
                benchmark=CisBenchmark.LINUX_CIS,
            )
        )
        run = await repos.hardening_runs.create(
            HardeningRun(organization_id=organization_id, hardening_profile_id=profile.id)
        )
        result = HardeningResult(
            organization_id=organization_id,
            hardening_run_id=run.id,
            check_name="cis-1.1.1",
            status=CheckResultStatus.PASSED,
        )
        result.created_at = hours_ago(5)
        await repos.hardening_results.create(result)
        await db_session.commit()

        worker = ProductionReadinessSweepWorker(
            db_session_factory, publish=publisher, threshold=0.3, lookback_seconds=3600  # type: ignore[arg-type]
        )
        ready_count = await worker.tick()
        assert ready_count == 0
        assert publisher.events == []


class TestStatisticsRollupWorkerBehaviour:
    async def test_rolls_up_completed_window(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        repos: Repositories,
        organization_id: uuid.UUID,
    ) -> None:
        profile = await repos.hardening_profiles.create(
            HardeningProfile(
                organization_id=organization_id,
                name="rollup-profile",
                target_type=HardeningTargetType.OS,
                benchmark=CisBenchmark.LINUX_CIS,
            )
        )
        run = HardeningRun(
            organization_id=organization_id,
            hardening_profile_id=profile.id,
            status=HardeningRunStatus.SUCCEEDED,
            started_at=hours_ago(2),
        )
        await repos.hardening_runs.create(run)
        await db_session.commit()

        worker = StatisticsRollupWorker(db_session_factory, window_hours=3)
        rolled = await worker.tick()
        assert rolled >= 1

        async with db_session_factory() as session:
            check_repos = build_repositories(session)
            rows = await check_repos.statistics.list_range(organization_id, since=hours_ago(4))
        assert len(rows) == 1
        assert rows[0].hardening_run_count == 1


class TestNotifierSanity:
    def test_notifier_class_importable(self) -> None:
        assert HardeningNotifier is not None
