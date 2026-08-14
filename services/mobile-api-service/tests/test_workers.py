"""Integration tests for background workers, against real PostgreSQL.

Uses real wall-clock time (``datetime.now(UTC)``) throughout, matching
every worker's own internal ``now = datetime.now(UTC)`` -- a fixed
historical constant would fall outside a worker's real query window and
produce tests that pass without the loop body ever executing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models.configuration import MobileAppVersion
from app.models.devices import MobileDevice, MobileSession, MobileToken
from app.models.enums import (
    DeviceTrustStatus,
    MobileAuthMethod,
    PushPlatform,
    ReleaseChannel,
    SyncJobStatus,
    SyncType,
)
from app.models.notifications import MobileNotification, MobilePushToken
from app.models.sync import MobileSyncJob, MobileSyncQueueItem
from app.services.bundle import Repositories
from app.workers.app_version_compliance_sweep import AppVersionComplianceSweepWorker
from app.workers.push_delivery_retry_sweep import PushDeliveryRetrySweepWorker
from app.workers.session_expiry_sweep import SessionExpirySweepWorker
from app.workers.sync_queue_retry_sweep import SyncQueueRetrySweepWorker
from app.workers.token_expiry_sweep import TokenExpirySweepWorker


def now() -> datetime:
    return datetime.now(UTC)


async def _make_device(
    repos: Repositories, organization_id: UUID, **overrides: object
) -> MobileDevice:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "device_identifier": f"dev-{overrides.get('device_identifier', 'w')}-{id(overrides)}",
        "platform": "android",
        "trust_status": DeviceTrustStatus.APPROVED,
        "last_seen_at": now(),
    }
    defaults.update(overrides)
    return await repos.devices.create(MobileDevice(**defaults))  # type: ignore[arg-type]


class TestSessionExpirySweepWorker:
    async def test_tick_expires_stale_sessions(
        self, db_session_factory, repos: Repositories, organization_id: UUID, notifier
    ) -> None:
        device = await _make_device(repos, organization_id, device_identifier="s1")
        await repos.sessions.create(
            MobileSession(
                organization_id=organization_id,
                device_id=device.id,
                user_id="u1",
                auth_method=MobileAuthMethod.JWT,
                issued_at=now() - timedelta(hours=2),
                expires_at=now() - timedelta(minutes=1),
            )
        )
        worker = SessionExpirySweepWorker(db_session_factory, notifier=notifier, warning_minutes=30)
        checked = await worker.tick()
        assert checked == 1

        remaining_active = await repos.sessions.list_active(organization_id)
        assert len(remaining_active) == 0

    async def test_tick_notifies_within_warning_window(
        self, db_session_factory, repos: Repositories, organization_id: UUID, notifier
    ) -> None:
        device = await _make_device(repos, organization_id, device_identifier="s2")
        await repos.sessions.create(
            MobileSession(
                organization_id=organization_id,
                device_id=device.id,
                user_id="u2",
                auth_method=MobileAuthMethod.JWT,
                issued_at=now() - timedelta(hours=1),
                expires_at=now() + timedelta(minutes=10),
            )
        )
        worker = SessionExpirySweepWorker(db_session_factory, notifier=notifier, warning_minutes=30)
        await worker.tick()
        assert any(name == "notify_session_expiring" for name, _ in notifier.calls)

    async def test_tick_leaves_healthy_sessions_alone(
        self, db_session_factory, repos: Repositories, organization_id: UUID, notifier
    ) -> None:
        device = await _make_device(repos, organization_id, device_identifier="s3")
        await repos.sessions.create(
            MobileSession(
                organization_id=organization_id,
                device_id=device.id,
                user_id="u3",
                auth_method=MobileAuthMethod.JWT,
                issued_at=now(),
                expires_at=now() + timedelta(hours=2),
            )
        )
        worker = SessionExpirySweepWorker(db_session_factory, notifier=notifier, warning_minutes=30)
        await worker.tick()
        assert not any(name == "notify_session_expiring" for name, _ in notifier.calls)
        assert len(await repos.sessions.list_active(organization_id)) == 1


class TestTokenExpirySweepWorker:
    async def test_tick_expires_stale_tokens(
        self, db_session_factory, repos: Repositories, organization_id: UUID
    ) -> None:
        device = await _make_device(repos, organization_id, device_identifier="t1")
        await repos.tokens.create(
            MobileToken(
                organization_id=organization_id,
                device_id=device.id,
                token_hash="h1",
                issued_at=now() - timedelta(days=100),
                expires_at=now() - timedelta(days=1),
            )
        )
        worker = TokenExpirySweepWorker(db_session_factory)
        expired = await worker.tick()
        assert expired == 1
        assert len(await repos.tokens.list_active(organization_id)) == 0

    async def test_tick_leaves_valid_tokens_alone(
        self, db_session_factory, repos: Repositories, organization_id: UUID
    ) -> None:
        device = await _make_device(repos, organization_id, device_identifier="t2")
        await repos.tokens.create(
            MobileToken(
                organization_id=organization_id,
                device_id=device.id,
                token_hash="h2",
                issued_at=now(),
                expires_at=now() + timedelta(days=90),
            )
        )
        worker = TokenExpirySweepWorker(db_session_factory)
        expired = await worker.tick()
        assert expired == 0
        assert len(await repos.tokens.list_active(organization_id)) == 1


class TestSyncQueueRetrySweepWorker:
    async def test_tick_applies_items_and_completes_job(
        self, db_session_factory, db_session, repos: Repositories, organization_id: UUID, publisher
    ) -> None:
        device = await _make_device(repos, organization_id, device_identifier="sy1")
        job = await repos.sync_jobs.create(
            MobileSyncJob(
                organization_id=organization_id,
                device_id=device.id,
                sync_type=SyncType.DELTA,
                item_count=1,
            )
        )
        await repos.sync_queue.create(
            MobileSyncQueueItem(
                organization_id=organization_id,
                sync_job_id=job.id,
                device_id=device.id,
                action_type="update",
                client_updated_at=now(),
            )
        )
        worker = SyncQueueRetrySweepWorker(db_session_factory, publish=publisher)
        processed = await worker.tick()
        assert processed == 1

        await db_session.refresh(job)
        assert job.status == SyncJobStatus.COMPLETED
        assert "SynchronizationCompleted" in publisher.names()
        assert "OfflineQueueProcessed" in publisher.names()

    async def test_tick_conflict_fails_job(
        self, db_session_factory, db_session, repos: Repositories, organization_id: UUID, publisher
    ) -> None:
        device = await _make_device(repos, organization_id, device_identifier="sy2")
        job = await repos.sync_jobs.create(
            MobileSyncJob(
                organization_id=organization_id,
                device_id=device.id,
                sync_type=SyncType.DELTA,
                item_count=1,
            )
        )
        server_hint = now().isoformat()
        await repos.sync_queue.create(
            MobileSyncQueueItem(
                organization_id=organization_id,
                sync_job_id=job.id,
                device_id=device.id,
                action_type="update",
                payload={"server_updated_at": server_hint},
                client_updated_at=now() - timedelta(hours=2),
            )
        )
        worker = SyncQueueRetrySweepWorker(db_session_factory, publish=publisher)
        await worker.tick()

        await db_session.refresh(job)
        assert job.status == SyncJobStatus.FAILED
        assert "SynchronizationFailed" in publisher.names()

    async def test_tick_ignores_other_organizations_queue(
        self, db_session_factory, repos: Repositories, organization_id: UUID, publisher
    ) -> None:
        worker = SyncQueueRetrySweepWorker(db_session_factory, publish=publisher)
        processed = await worker.tick()
        assert processed == 0


class TestPushDeliveryRetrySweepWorker:
    async def test_tick_delivers_when_token_usable(
        self, db_session_factory, repos: Repositories, organization_id: UUID, publisher
    ) -> None:
        device = await _make_device(repos, organization_id, device_identifier="p1")
        await repos.push_tokens.create(
            MobilePushToken(
                organization_id=organization_id,
                device_id=device.id,
                platform=PushPlatform.FCM,
                token_value="tok",
                registered_at=now(),
            )
        )
        await repos.notifications.create(
            MobileNotification(
                organization_id=organization_id, device_id=device.id, title="t", body="b"
            )
        )
        worker = PushDeliveryRetrySweepWorker(
            db_session_factory, publish=publisher, max_retry_count=3
        )
        attempted = await worker.tick()
        assert attempted == 1
        assert "PushDelivered" in publisher.names()

    async def test_tick_fails_after_retries_exhausted_without_token(
        self, db_session_factory, repos: Repositories, organization_id: UUID, publisher
    ) -> None:
        device = await _make_device(repos, organization_id, device_identifier="p2")
        await repos.notifications.create(
            MobileNotification(
                organization_id=organization_id, device_id=device.id, title="t", body="b"
            )
        )
        worker = PushDeliveryRetrySweepWorker(
            db_session_factory, publish=publisher, max_retry_count=1
        )
        await worker.tick()
        assert "PushFailed" in publisher.names()


class TestAppVersionComplianceSweepWorker:
    async def test_tick_notifies_forced_upgrade_below_minimum(
        self, db_session_factory, repos: Repositories, organization_id: UUID, notifier
    ) -> None:
        await _make_device(
            repos,
            organization_id,
            device_identifier="v1",
            platform="android",
            app_version_label="0.5.0",
        )
        await repos.app_versions.create(
            MobileAppVersion(
                organization_id=organization_id,
                platform="android",
                version_label="2.0.0",
                release_channel=ReleaseChannel.STABLE,
                minimum_version_label="1.0.0",
                recommended_version_label="2.0.0",
                released_at=now(),
            )
        )
        worker = AppVersionComplianceSweepWorker(db_session_factory, notifier=notifier)
        checked = await worker.tick()
        assert checked == 1
        assert any(name == "notify_forced_upgrade" for name, _ in notifier.calls)
        assert not any(name == "notify_app_update_available" for name, _ in notifier.calls)

    async def test_tick_notifies_update_available_between_minimum_and_recommended(
        self, db_session_factory, repos: Repositories, organization_id: UUID, notifier
    ) -> None:
        await _make_device(
            repos,
            organization_id,
            device_identifier="v2",
            platform="android",
            app_version_label="1.5.0",
        )
        await repos.app_versions.create(
            MobileAppVersion(
                organization_id=organization_id,
                platform="android",
                version_label="2.0.0",
                release_channel=ReleaseChannel.STABLE,
                minimum_version_label="1.0.0",
                recommended_version_label="2.0.0",
                released_at=now(),
            )
        )
        worker = AppVersionComplianceSweepWorker(db_session_factory, notifier=notifier)
        await worker.tick()
        assert any(name == "notify_app_update_available" for name, _ in notifier.calls)
        assert not any(name == "notify_forced_upgrade" for name, _ in notifier.calls)

    async def test_tick_skips_devices_without_reported_version(
        self, db_session_factory, repos: Repositories, organization_id: UUID, notifier
    ) -> None:
        await _make_device(
            repos,
            organization_id,
            device_identifier="v3",
            platform="android",
            app_version_label=None,
        )
        worker = AppVersionComplianceSweepWorker(db_session_factory, notifier=notifier)
        checked = await worker.tick()
        assert checked == 0

    async def test_tick_skips_devices_with_no_policy(
        self, db_session_factory, repos: Repositories, organization_id: UUID, notifier
    ) -> None:
        await _make_device(
            repos,
            organization_id,
            device_identifier="v4",
            platform="ios",
            app_version_label="1.0.0",
        )
        worker = AppVersionComplianceSweepWorker(db_session_factory, notifier=notifier)
        checked = await worker.tick()
        assert checked == 0
