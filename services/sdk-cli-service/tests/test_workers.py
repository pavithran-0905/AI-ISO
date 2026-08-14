"""Integration tests for background workers, against real PostgreSQL.

Uses real wall-clock time (``datetime.now(UTC)``) throughout, matching
every worker's own internal ``now = datetime.now(UTC)`` -- a fixed
historical constant would fall outside a worker's real query window and
produce tests that pass without the loop body ever executing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models.cli import CliPlugin, CliProfile, CliSession, CliUpdate, CliUsage, CliVersion
from app.models.enums import CliAuthMethod, CliUpdateStatus, PluginStatus, SdkLanguage
from app.models.sdk import SdkDownload, SdkVersion
from app.workers.cli_update_check_sweep import CliUpdateCheckSweepWorker
from app.workers.plugin_update_sweep import PluginUpdateSweepWorker
from app.workers.session_expiry_sweep import SessionExpirySweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from app.workers.version_compatibility_sweep import VersionCompatibilitySweepWorker


def now() -> datetime:
    return datetime.now(UTC)


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def broadcast(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


async def _noop_publish(event: object) -> None:
    pass


class TestVersionCompatibilitySweepWorker:
    async def test_tick_notifies_within_warning_window(
        self, db_session_factory, repos, organization_id: UUID, notifier
    ) -> None:
        await repos.sdk_versions.create(
            SdkVersion(
                organization_id=organization_id,
                language=SdkLanguage.PYTHON,
                version_label="1.0.0",
                api_compatibility_version="1.0.0",
                deprecated_at=now() + timedelta(days=10),
            )
        )
        worker = VersionCompatibilitySweepWorker(
            db_session_factory,
            notifier=notifier,
            sdk_warning_days_before=30,
            cli_warning_days_before=30,
        )
        checked = await worker.tick()
        assert checked == 1
        assert any(name == "notify_deprecation_notice" for name, _ in notifier.calls)

    async def test_tick_disables_version_past_deprecation(
        self, db_session_factory, db_session, repos, organization_id: UUID, notifier
    ) -> None:
        version = await repos.sdk_versions.create(
            SdkVersion(
                organization_id=organization_id,
                language=SdkLanguage.PYTHON,
                version_label="1.0.0",
                api_compatibility_version="1.0.0",
                deprecated_at=now() - timedelta(days=1),
            )
        )
        worker = VersionCompatibilitySweepWorker(
            db_session_factory,
            notifier=notifier,
            sdk_warning_days_before=30,
            cli_warning_days_before=30,
        )
        await worker.tick()

        await db_session.refresh(version)
        assert version.is_enabled is False

    async def test_tick_leaves_version_outside_warning_window_alone(
        self, db_session_factory, repos, organization_id: UUID, notifier
    ) -> None:
        await repos.cli_versions.create(
            CliVersion(
                organization_id=organization_id,
                version_label="1.0.0",
                api_compatibility_version="1.0.0",
                deprecated_at=now() + timedelta(days=365),
            )
        )
        worker = VersionCompatibilitySweepWorker(
            db_session_factory,
            notifier=notifier,
            sdk_warning_days_before=30,
            cli_warning_days_before=30,
        )
        await worker.tick()
        assert notifier.calls == []

    async def test_tick_no_organizations_checks_nothing(self, db_session_factory, notifier) -> None:
        worker = VersionCompatibilitySweepWorker(
            db_session_factory,
            notifier=notifier,
            sdk_warning_days_before=30,
            cli_warning_days_before=30,
        )
        assert await worker.tick() == 0


class TestCliUpdateCheckSweepWorker:
    async def test_tick_notifies_for_outdated_version(
        self, db_session_factory, repos, organization_id: UUID, notifier
    ) -> None:
        await repos.cli_versions.create(
            CliVersion(
                organization_id=organization_id,
                version_label="1.0.0",
                api_compatibility_version="1.0.0",
            )
        )
        await repos.cli_versions.create(
            CliVersion(
                organization_id=organization_id,
                version_label="2.0.0",
                api_compatibility_version="2.0.0",
            )
        )
        worker = CliUpdateCheckSweepWorker(db_session_factory, notifier=notifier)
        notified = await worker.tick()
        assert notified == 1
        assert any(name == "notify_cli_update_available" for name, _ in notifier.calls)

    async def test_tick_no_versions_notifies_nothing(self, db_session_factory, notifier) -> None:
        worker = CliUpdateCheckSweepWorker(db_session_factory, notifier=notifier)
        assert await worker.tick() == 0


class TestPluginUpdateSweepWorker:
    async def test_tick_notifies_for_installed_plugin_with_newer_available(
        self, db_session_factory, repos, organization_id: UUID, notifier
    ) -> None:
        await repos.cli_plugins.create(
            CliPlugin(
                organization_id=organization_id,
                name="observability",
                version_label="1.0.0",
                status=PluginStatus.INSTALLED,
                checksum_sha256="abc",
            )
        )
        await repos.cli_plugins.create(
            CliPlugin(
                organization_id=organization_id,
                name="observability",
                version_label="2.0.0",
                status=PluginStatus.AVAILABLE,
                checksum_sha256="def",
            )
        )
        worker = PluginUpdateSweepWorker(db_session_factory, notifier=notifier)
        notified = await worker.tick()
        assert notified == 1
        assert any(name == "notify_plugin_update_available" for name, _ in notifier.calls)

    async def test_tick_no_newer_version_notifies_nothing(
        self, db_session_factory, repos, organization_id: UUID, notifier
    ) -> None:
        await repos.cli_plugins.create(
            CliPlugin(
                organization_id=organization_id,
                name="observability",
                version_label="1.0.0",
                status=PluginStatus.INSTALLED,
                checksum_sha256="abc",
            )
        )
        worker = PluginUpdateSweepWorker(db_session_factory, notifier=notifier)
        assert await worker.tick() == 0


class TestSessionExpirySweepWorker:
    async def test_tick_disables_expired_session(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        profile = await repos.cli_profiles.create(
            CliProfile(
                organization_id=organization_id,
                profile_name="default",
                auth_method=CliAuthMethod.API_KEY,
            )
        )
        session = await repos.cli_sessions.create(
            CliSession(
                organization_id=organization_id,
                profile_id=profile.id,
                auth_method=CliAuthMethod.API_KEY,
                started_at=now() - timedelta(hours=2),
                expires_at=now() - timedelta(hours=1),
            )
        )
        worker = SessionExpirySweepWorker(db_session_factory)
        expired = await worker.tick()
        assert expired == 1

        await db_session.refresh(session)
        assert session.is_enabled is False

    async def test_tick_leaves_unexpired_session_alone(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        profile = await repos.cli_profiles.create(
            CliProfile(
                organization_id=organization_id,
                profile_name="default",
                auth_method=CliAuthMethod.API_KEY,
            )
        )
        session = await repos.cli_sessions.create(
            CliSession(
                organization_id=organization_id,
                profile_id=profile.id,
                auth_method=CliAuthMethod.API_KEY,
                started_at=now(),
                expires_at=now() + timedelta(hours=1),
            )
        )
        worker = SessionExpirySweepWorker(db_session_factory)
        await worker.tick()
        await db_session.refresh(session)
        assert session.is_enabled is True

    async def test_tick_no_organizations_expires_nothing(self, db_session_factory) -> None:
        worker = SessionExpirySweepWorker(db_session_factory)
        assert await worker.tick() == 0


class TestStatisticsRollupWorker:
    async def test_tick_rolls_up_current_window_idempotently(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        # The worker rolls up the *last completed* hour, so every event
        # below is timestamped inside that window explicitly -- an event
        # timestamped "now" would fall in the current, still-open hour
        # and correctly not appear until the next rollup, exactly the
        # window-boundary behavior this test is proving.
        window_end = now().replace(minute=0, second=0, microsecond=0)
        window_start = window_end - timedelta(hours=1)
        inside_window = window_start + timedelta(minutes=5)

        version = await repos.sdk_versions.create(
            SdkVersion(
                organization_id=organization_id,
                language=SdkLanguage.PYTHON,
                version_label="1.0.0",
                api_compatibility_version="1.0.0",
            )
        )
        await repos.sdk_downloads.create(
            SdkDownload(
                organization_id=organization_id,
                sdk_version_id=version.id,
                downloaded_at=inside_window,
            )
        )
        await repos.cli_updates.create(
            CliUpdate(
                organization_id=organization_id,
                from_version="1.0.0",
                to_version="1.1.0",
                status=CliUpdateStatus.APPLIED,
                checked_at=inside_window,
                applied_at=inside_window,
            )
        )
        await repos.cli_usage.create(
            CliUsage(
                organization_id=organization_id,
                session_id=None,
                command_group="auth",
                command="login",
                executed_at=inside_window,
            )
        )

        worker = StatisticsRollupWorker(db_session_factory)
        rolled_first = await worker.tick()
        rolled_second = await worker.tick()
        assert rolled_first == rolled_second == 1

        statistic = await repos.statistics.find_window(organization_id, window_start=window_start)
        assert statistic is not None
        assert statistic.sdk_download_count == 1
        assert statistic.cli_download_count == 1
        assert statistic.command_execution_count == 1
        assert statistic.auth_failure_count == 0

    async def test_tick_no_organizations_rolls_up_nothing(self, db_session_factory) -> None:
        worker = StatisticsRollupWorker(db_session_factory)
        assert await worker.tick() == 0
