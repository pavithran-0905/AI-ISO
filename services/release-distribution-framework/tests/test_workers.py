"""Integration tests for every background worker, against real PostgreSQL.

Workers are exercised by calling ``tick()`` directly -- fast and
deterministic, never through the scheduler. Every assertion re-reads
state through a **separate** session from the one the worker used to
write it, since trusting the writer's own session already hid a real
bug in a prior service (a worker that created a row but never
committed).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.builds import ReleaseBuild
from app.models.channels import ReleaseChannelConfig
from app.models.downloads import DownloadStatistic
from app.models.enums import (
    ArtifactType,
    BuildStatus,
    PackageFormat,
    PromotionStatus,
    ReleaseChannelType,
)
from app.models.lifecycle import EolSchedule, LtsVersion
from app.models.packages import ReleaseArtifact, ReleasePackage
from app.models.promotions import ReleasePromotion
from app.models.releases import ReleaseVersion
from app.services.bundle import Repositories, build_repositories
from app.services.promotions import ReleasePromotionService
from app.workers.build_timeout_sweep import ReleaseBuildTimeoutSweepWorker
from app.workers.eol_schedule_sweep import EolScheduleSweepWorker
from app.workers.lts_support_expiry_sweep import LtsSupportExpirySweepWorker
from app.workers.promotion_approval_timeout_sweep import PromotionApprovalTimeoutSweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from tests.conftest import RecordingNotifier, RecordingPublisher, days_ahead, hours_ago


async def _make_channel(
    repos: Repositories, organization_id: uuid.UUID, name: str = "c1"
) -> ReleaseChannelConfig:
    return await repos.release_channels.create(
        ReleaseChannelConfig(
            organization_id=organization_id, name=name, channel_type=ReleaseChannelType.STABLE
        )
    )


async def _make_version(
    repos: Repositories, organization_id: uuid.UUID, *, channel_name: str, label: str
) -> ReleaseVersion:
    channel = await _make_channel(repos, organization_id, name=channel_name)
    return await repos.release_versions.create(
        ReleaseVersion(
            organization_id=organization_id, version_label=label, release_channel_id=channel.id
        )
    )


class TestReleaseBuildTimeoutSweepWorker:
    async def test_fails_stuck_running_build_and_notifies(
        self,
        repos: Repositories,
        db_session_factory: async_sessionmaker[AsyncSession],
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="w1", label="1.0.0")
        build = await repos.release_builds.create(
            ReleaseBuild(
                organization_id=organization_id,
                release_version_id=version.id,
                status=BuildStatus.RUNNING,
                started_at=hours_ago(10),
            )
        )

        worker = ReleaseBuildTimeoutSweepWorker(
            db_session_factory, notifier=notifier, max_age_hours=4
        )
        failed = await worker.tick()
        assert failed == 1

        async with db_session_factory() as session:
            reloaded = await build_repositories(session).release_builds.require_by_id(build.id)
            assert reloaded.status == "failed"
        assert any(call[0] == "notify_release_failure" for call in notifier.calls)

    async def test_does_not_fail_recent_running_build(
        self,
        repos: Repositories,
        db_session_factory: async_sessionmaker[AsyncSession],
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="w2", label="1.0.1")
        build = await repos.release_builds.create(
            ReleaseBuild(
                organization_id=organization_id,
                release_version_id=version.id,
                status=BuildStatus.RUNNING,
                started_at=hours_ago(1),
            )
        )

        worker = ReleaseBuildTimeoutSweepWorker(
            db_session_factory, notifier=notifier, max_age_hours=4
        )
        failed = await worker.tick()
        assert failed == 0

        async with db_session_factory() as session:
            reloaded = await build_repositories(session).release_builds.require_by_id(build.id)
            assert reloaded.status == "running"


class TestPromotionApprovalTimeoutSweepWorker:
    async def test_rejects_stale_pending_promotion(
        self,
        repos: Repositories,
        db_session_factory: async_sessionmaker[AsyncSession],
        organization_id: uuid.UUID,
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="w3", label="2.0.0")
        service = ReleasePromotionService(repos.release_promotions)
        promotion = await service.create(
            organization_id,
            release_version_id=version.id,
            from_channel_type=ReleaseChannelType.CANARY,
            to_channel_type=ReleaseChannelType.STABLE,
        )
        promotion.created_at = hours_ago(72)
        await repos.release_promotions.update(promotion)

        worker = PromotionApprovalTimeoutSweepWorker(db_session_factory, max_age_hours=48)
        rejected = await worker.tick()
        assert rejected == 1

        async with db_session_factory() as session:
            reloaded = await build_repositories(session).release_promotions.require_by_id(
                promotion.id
            )
            assert reloaded.status == "rejected"

    async def test_does_not_reject_fresh_pending_promotion(
        self,
        repos: Repositories,
        db_session_factory: async_sessionmaker[AsyncSession],
        organization_id: uuid.UUID,
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="w4", label="2.0.1")
        service = ReleasePromotionService(repos.release_promotions)
        promotion = await service.create(
            organization_id,
            release_version_id=version.id,
            from_channel_type=ReleaseChannelType.CANARY,
            to_channel_type=ReleaseChannelType.STABLE,
        )

        worker = PromotionApprovalTimeoutSweepWorker(db_session_factory, max_age_hours=48)
        rejected = await worker.tick()
        assert rejected == 0

        async with db_session_factory() as session:
            reloaded = await build_repositories(session).release_promotions.require_by_id(
                promotion.id
            )
            assert reloaded.status == "pending"

    async def test_promote_path_leaves_nothing_pending_to_time_out(
        self,
        repos: Repositories,
        db_session_factory: async_sessionmaker[AsyncSession],
        organization_id: uuid.UUID,
    ) -> None:
        """``promote()`` always resolves synchronously (completed or
        rejected), so the timeout sweep never finds anything from it --
        only rows left by the lower-level ``create()`` are reachable."""
        version = await _make_version(repos, organization_id, channel_name="w5", label="2.0.2")
        service = ReleasePromotionService(repos.release_promotions)
        promotion = await service.promote(
            organization_id,
            release_version_id=version.id,
            version_label="2.0.2",
            from_channel_type=ReleaseChannelType.CANARY,
            to_channel_type=ReleaseChannelType.STABLE,
            approved_by="qa-lead",
            now=hours_ago(72),
        )
        promotion.created_at = hours_ago(72)
        await repos.release_promotions.update(promotion)

        worker = PromotionApprovalTimeoutSweepWorker(db_session_factory, max_age_hours=48)
        rejected = await worker.tick()
        assert rejected == 0


class TestLtsSupportExpirySweepWorker:
    async def test_notifies_once_on_entering_warning_window(
        self,
        repos: Repositories,
        db_session_factory: async_sessionmaker[AsyncSession],
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="w6", label="3.0.0")
        lts_version = await repos.lts_versions.create(
            LtsVersion(
                organization_id=organization_id,
                release_version_id=version.id,
                support_ends_at=days_ahead(10),
            )
        )

        worker = LtsSupportExpirySweepWorker(db_session_factory, notifier=notifier, warning_days=30)
        notified = await worker.tick()
        assert notified == 1
        assert any(call[0] == "notify_eol_warning" for call in notifier.calls)

        async with db_session_factory() as session:
            reloaded = await build_repositories(session).lts_versions.require_by_id(lts_version.id)
            assert reloaded.support_expiry_notice_sent is True

        notifier.calls.clear()
        notified_again = await worker.tick()
        assert notified_again == 0
        assert notifier.calls == []

    async def test_does_not_notify_outside_warning_window(
        self,
        repos: Repositories,
        db_session_factory: async_sessionmaker[AsyncSession],
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="w7", label="3.0.1")
        await repos.lts_versions.create(
            LtsVersion(
                organization_id=organization_id,
                release_version_id=version.id,
                support_ends_at=days_ahead(365),
            )
        )

        worker = LtsSupportExpirySweepWorker(db_session_factory, notifier=notifier, warning_days=30)
        notified = await worker.tick()
        assert notified == 0


class TestEolScheduleSweepWorker:
    async def test_announces_and_notifies_once_on_entering_warning_window(
        self,
        repos: Repositories,
        db_session_factory: async_sessionmaker[AsyncSession],
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="w8", label="4.0.0")
        schedule = await repos.eol_schedule.create(
            EolSchedule(
                organization_id=organization_id,
                release_version_id=version.id,
                eol_date=days_ahead(20),
            )
        )

        worker = EolScheduleSweepWorker(
            db_session_factory, publish=publisher, notifier=notifier, warning_days=180
        )
        notified = await worker.tick()
        assert notified == 1
        assert "EOLAnnounced" in publisher.names()
        assert any(call[0] == "notify_eol_warning" for call in notifier.calls)

        async with db_session_factory() as session:
            reloaded = await build_repositories(session).eol_schedule.require_by_id(schedule.id)
            assert reloaded.deprecation_notice_sent is True

        publisher.events.clear()
        notifier.calls.clear()
        notified_again = await worker.tick()
        assert notified_again == 0
        assert publisher.events == []
        assert notifier.calls == []

    async def test_does_not_announce_outside_warning_window(
        self,
        repos: Repositories,
        db_session_factory: async_sessionmaker[AsyncSession],
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="w9", label="4.0.1")
        await repos.eol_schedule.create(
            EolSchedule(
                organization_id=organization_id,
                release_version_id=version.id,
                eol_date=days_ahead(400),
            )
        )

        worker = EolScheduleSweepWorker(
            db_session_factory, publish=publisher, notifier=notifier, warning_days=180
        )
        notified = await worker.tick()
        assert notified == 0


class TestStatisticsRollupWorker:
    async def test_rolls_up_last_completed_window(
        self,
        repos: Repositories,
        db_session_factory: async_sessionmaker[AsyncSession],
        organization_id: uuid.UUID,
    ) -> None:
        window_end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        window_start = window_end - timedelta(hours=1)
        midpoint = window_start + (window_end - window_start) / 2

        version = await _make_version(repos, organization_id, channel_name="w10", label="5.0.0")
        version.created_at = midpoint
        await repos.release_versions.update(version)

        build = await repos.release_builds.create(
            ReleaseBuild(
                organization_id=organization_id,
                release_version_id=version.id,
                status=BuildStatus.SUCCEEDED,
            )
        )
        build.created_at = midpoint
        await repos.release_builds.update(build)

        promotion = await repos.release_promotions.create(
            ReleasePromotion(
                organization_id=organization_id,
                release_version_id=version.id,
                from_channel_type=ReleaseChannelType.CANARY,
                to_channel_type=ReleaseChannelType.STABLE,
                status=PromotionStatus.COMPLETED,
            )
        )
        promotion.created_at = midpoint
        await repos.release_promotions.update(promotion)

        package = await repos.release_packages.create(
            ReleasePackage(
                organization_id=organization_id,
                release_version_id=version.id,
                artifact_type=ArtifactType.CLI,
                package_format=PackageFormat.ZIP,
                name="cli-bundle",
            )
        )
        artifact = await repos.release_artifacts.create(
            ReleaseArtifact(
                organization_id=organization_id,
                release_package_id=package.id,
                artifact_name="cli.zip",
            )
        )
        await repos.download_statistics.create(
            DownloadStatistic(
                organization_id=organization_id,
                release_artifact_id=artifact.id,
                downloaded_at=midpoint,
            )
        )

        worker = StatisticsRollupWorker(db_session_factory)
        rolled = await worker.tick()
        assert rolled >= 1

        async with db_session_factory() as session:
            fresh_repos = build_repositories(session)
            rows = await fresh_repos.statistics.list_range(
                organization_id, since=window_start - timedelta(hours=1)
            )
            assert len(rows) == 1
            row = rows[0]
            assert row.release_count == 1
            assert row.promotion_count == 1
            assert row.download_count == 1
            assert row.avg_release_success_rate == 1.0

    async def test_idempotent_upsert_same_window(
        self,
        repos: Repositories,
        db_session_factory: async_sessionmaker[AsyncSession],
        organization_id: uuid.UUID,
    ) -> None:
        window_end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        window_start = window_end - timedelta(hours=1)
        midpoint = window_start + (window_end - window_start) / 2

        version = await _make_version(repos, organization_id, channel_name="w11", label="5.0.1")
        version.created_at = midpoint
        await repos.release_versions.update(version)

        worker = StatisticsRollupWorker(db_session_factory)
        await worker.tick()
        await worker.tick()

        async with db_session_factory() as session:
            fresh_repos = build_repositories(session)
            rows = await fresh_repos.statistics.list_range(
                organization_id, since=window_start - timedelta(hours=1)
            )
            assert len(rows) == 1
