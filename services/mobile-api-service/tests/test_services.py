"""Integration tests for every service class, against real PostgreSQL
(and Redis, for :class:`~app.services.qr.QrService`)."""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import (
    AnalyticsMetricType,
    ConflictResolutionStrategy,
    DeviceTrustStatus,
    MobileAuditAction,
    MobileAuthMethod,
    MobilePlatform,
    NotificationDeliveryStatus,
    PushPlatform,
    QrPurpose,
    ReportKind,
    SyncQueueStatus,
    SyncType,
    TelemetryMetricType,
)
from app.services.audit import AuditService
from app.services.bundle import Repositories
from app.services.configuration import ConfigurationService
from app.services.devices import DeviceService, TransitionRefusedError
from app.services.push import PushService
from app.services.qr import QrService
from app.services.reports import ReportService
from app.services.sessions import LoginRefusalReason, LoginRefusedError, SessionService
from app.services.statistics import StatisticsService
from app.services.sync import JobTransitionRefusedError, SyncItemInput, SyncService
from app.services.telemetry import AnalyticsService, TelemetryService
from app.services.tokens import MobileTokenService
from app.services.versions import AppVersionService
from tests.conftest import RecordingNotifier, RecordingPublisher, hours_ago, hours_ahead, utcnow

pytestmark = pytest.mark.asyncio


class TestAuditService:
    async def test_record_and_list(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = AuditService(repos.audit)
        await service.record(
            organization_id=organization_id,
            action=MobileAuditAction.DEVICE_REGISTRATION,
            entity_type="mobile_device",
            entity_id=uuid.uuid4(),
            summary="registered",
            occurred_at=utcnow(),
        )
        rows = await service.list_recent(organization_id)
        assert len(rows) == 1


class TestDeviceService:
    async def test_registers_new_device_and_publishes(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        audit = AuditService(repos.audit)
        service = DeviceService(repos.devices, publish=publisher, audit=audit)
        device, created = await service.find_or_register(
            organization_id,
            device_identifier="dev-1",
            platform=MobilePlatform.ANDROID,
            device_model="Pixel",
            os_version="14",
            app_version_label="1.0.0",
            now=utcnow(),
            actor_id="user-1",
        )
        assert created is True
        assert device.trust_status == DeviceTrustStatus.PENDING
        assert publisher.names() == ["MobileDeviceRegistered"]
        audit_rows = await audit.list_recent(organization_id)
        assert len(audit_rows) == 1

    async def test_find_or_register_idempotent_on_second_call(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = DeviceService(repos.devices, publish=publisher)
        device1, created1 = await service.find_or_register(
            organization_id,
            device_identifier="dev-2",
            platform=MobilePlatform.IOS,
            device_model=None,
            os_version=None,
            app_version_label="1.0.0",
            now=utcnow(),
        )
        device2, created2 = await service.find_or_register(
            organization_id,
            device_identifier="dev-2",
            platform=MobilePlatform.IOS,
            device_model=None,
            os_version=None,
            app_version_label="1.1.0",
            now=utcnow(),
        )
        assert created1 is True
        assert created2 is False
        assert device1.id == device2.id
        assert device2.app_version_label == "1.1.0"
        assert publisher.names() == ["MobileDeviceRegistered"]

    async def test_transition_approve_then_revoke_notifies(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        service = DeviceService(repos.devices, publish=publisher, notifier=notifier)
        device, _ = await service.find_or_register(
            organization_id,
            device_identifier="dev-3",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        device = await service.transition(device, target=DeviceTrustStatus.APPROVED, now=utcnow())
        assert device.approved_at is not None
        device = await service.transition(device, target=DeviceTrustStatus.REVOKED, now=utcnow())
        assert device.revoked_at is not None
        assert any(name == "notify_device_revoked" for name, _ in notifier.calls)

    async def test_transition_refused_from_terminal_state(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = DeviceService(repos.devices, publish=publisher)
        device, _ = await service.find_or_register(
            organization_id,
            device_identifier="dev-4",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        device = await service.transition(device, target=DeviceTrustStatus.REVOKED, now=utcnow())
        with pytest.raises(TransitionRefusedError):
            await service.transition(device, target=DeviceTrustStatus.APPROVED, now=utcnow())


class TestSessionService:
    async def test_login_success_publishes_and_audits(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
    ) -> None:
        device_service = DeviceService(repos.devices, publish=publisher)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-5",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        audit = AuditService(repos.audit)
        service = SessionService(repos.sessions, publish=publisher, audit=audit)
        session = await service.login(
            device,
            user_id="user-1",
            auth_method=MobileAuthMethod.JWT,
            now=utcnow(),
            session_max_age_minutes=60,
        )
        assert session.is_new_device is True
        assert "MobileLoginSucceeded" in publisher.names()
        assert len(await audit.list_recent(organization_id)) == 1

    async def test_login_refused_for_revoked_device(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        device_service = DeviceService(repos.devices, publish=publisher)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-6",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        device = await device_service.transition(
            device, target=DeviceTrustStatus.REVOKED, now=utcnow()
        )
        service = SessionService(repos.sessions, publish=publisher)
        with pytest.raises(LoginRefusedError) as exc_info:
            await service.login(
                device,
                user_id="u",
                auth_method=MobileAuthMethod.JWT,
                now=utcnow(),
                session_max_age_minutes=60,
            )
        assert exc_info.value.reason == LoginRefusalReason.DEVICE_REVOKED
        assert "MobileLoginFailed" in publisher.names()

    async def test_login_refused_for_failed_integrity(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        device_service = DeviceService(repos.devices, publish=publisher)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-7",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
            is_jailbroken=True,
            is_rooted=True,
        )
        service = SessionService(repos.sessions, publish=publisher, notifier=notifier)
        with pytest.raises(LoginRefusedError) as exc_info:
            await service.login(
                device,
                user_id="u",
                auth_method=MobileAuthMethod.JWT,
                now=utcnow(),
                session_max_age_minutes=60,
            )
        assert exc_info.value.reason == LoginRefusalReason.DEVICE_INTEGRITY
        assert any(name == "notify_security_alert" for name, _ in notifier.calls)

    async def test_logout_and_expire(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-8",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = SessionService(repos.sessions)
        session = await service.login(
            device,
            user_id="u",
            auth_method=MobileAuthMethod.JWT,
            now=utcnow(),
            session_max_age_minutes=60,
        )
        session = await service.logout(session, now=utcnow())
        assert session.revoked_at is not None

        session2 = await service.login(
            device,
            user_id="u2",
            auth_method=MobileAuthMethod.JWT,
            now=utcnow(),
            session_max_age_minutes=60,
        )
        session2 = await service.expire(session2)
        assert service.is_expired(session2, now=hours_ahead(1))


class TestMobileTokenService:
    async def test_issue_and_revoke(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-9",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = MobileTokenService(repos.tokens)
        token, raw = await service.issue(
            organization_id, device_id=device.id, now=utcnow(), max_age_days=90
        )
        assert len(raw) >= 32
        assert token.token_hash != raw
        token = await service.revoke(token, now=utcnow())
        assert token.revoked_at is not None


class TestProfileServiceViaBundle:
    async def test_get_or_create_then_update(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        from app.services.profiles import ProfileService

        service = ProfileService(repos.profiles)
        profile = await service.get_or_create(organization_id, user_id="u1")
        assert profile.display_name == ""
        again = await service.get_or_create(organization_id, user_id="u1")
        assert again.id == profile.id
        updated = await service.update(profile, display_name="Ada", preferences={"theme": "dark"})
        assert updated.display_name == "Ada"
        assert updated.preferences == {"theme": "dark"}


class TestSyncService:
    async def test_enqueue_creates_job_and_items(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-10",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = SyncService(repos.sync_jobs, repos.sync_queue)
        job = await service.enqueue(
            organization_id,
            device_id=device.id,
            sync_type=SyncType.DELTA,
            items=[SyncItemInput(action_type="update", client_updated_at=utcnow())],
        )
        assert job.item_count == 1
        items = await repos.sync_queue.list_for_job(job.id)
        assert len(items) == 1
        assert items[0].status == SyncQueueStatus.QUEUED

    async def test_start_job_on_already_running_job_refuses(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-11",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = SyncService(repos.sync_jobs, repos.sync_queue)
        job = await service.enqueue(
            organization_id, device_id=device.id, sync_type=SyncType.MANUAL, items=[]
        )
        job = await service.start_job(job, now=utcnow())
        assert (
            job.status.value == "running"
            if hasattr(job.status, "value")
            else job.status == "running"
        )
        # RUNNING's only allowed next states are COMPLETED/FAILED, so a
        # second start attempt (RUNNING -> RUNNING) is an invalid
        # transition, not a no-op.
        with pytest.raises(JobTransitionRefusedError):
            await service.start_job(job, now=utcnow())

    async def test_start_job_on_terminal_job_is_a_noop(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-11b",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = SyncService(repos.sync_jobs, repos.sync_queue, publish=publisher)
        job = await service.enqueue(
            organization_id, device_id=device.id, sync_type=SyncType.MANUAL, items=[]
        )
        job = await service.complete_job(job, applied_count=0, now=utcnow())
        # A terminal job re-entering start_job (e.g. a retried tick that
        # raced a prior completion) is a silent no-op, not an error.
        result = await service.start_job(job, now=utcnow())
        assert result.id == job.id

    async def test_apply_queue_item_no_conflict(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-12",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = SyncService(repos.sync_jobs, repos.sync_queue)
        job = await service.enqueue(
            organization_id,
            device_id=device.id,
            sync_type=SyncType.DELTA,
            items=[SyncItemInput(action_type="update", client_updated_at=utcnow())],
        )
        items = await repos.sync_queue.list_for_job(job.id)
        applied = await service.apply_queue_item(
            items[0],
            server_updated_at=None,
            strategy=ConflictResolutionStrategy.SERVER_WINS,
            now=utcnow(),
        )
        assert applied.status == SyncQueueStatus.APPLIED

    async def test_apply_queue_item_conflict_server_wins(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-13",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = SyncService(repos.sync_jobs, repos.sync_queue)
        job = await service.enqueue(
            organization_id,
            device_id=device.id,
            sync_type=SyncType.DELTA,
            items=[SyncItemInput(action_type="update", client_updated_at=hours_ago(2))],
        )
        items = await repos.sync_queue.list_for_job(job.id)
        conflicted = await service.apply_queue_item(
            items[0],
            server_updated_at=utcnow(),
            strategy=ConflictResolutionStrategy.SERVER_WINS,
            now=utcnow(),
        )
        assert conflicted.status == SyncQueueStatus.CONFLICT

    async def test_complete_job_publishes(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-14",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = SyncService(repos.sync_jobs, repos.sync_queue, publish=publisher)
        job = await service.enqueue(
            organization_id, device_id=device.id, sync_type=SyncType.MANUAL, items=[]
        )
        job = await service.complete_job(job, applied_count=0, now=utcnow())
        assert (
            job.status.value == "completed"
            if hasattr(job.status, "value")
            else job.status == "completed"
        )
        assert "SynchronizationCompleted" in publisher.names()

    async def test_fail_job_publishes(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-15",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = SyncService(repos.sync_jobs, repos.sync_queue, publish=publisher)
        job = await service.enqueue(
            organization_id, device_id=device.id, sync_type=SyncType.MANUAL, items=[]
        )
        job = await service.fail_job(
            job, conflict_count=1, reason="conflict", now=utcnow(), device_identifier="dev-15"
        )
        assert "SynchronizationFailed" in publisher.names()

    async def test_requeue_and_fail_queue_item(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-16",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = SyncService(repos.sync_jobs, repos.sync_queue)
        job = await service.enqueue(
            organization_id,
            device_id=device.id,
            sync_type=SyncType.MANUAL,
            items=[SyncItemInput(action_type="a", client_updated_at=utcnow())],
        )
        items = await repos.sync_queue.list_for_job(job.id)
        failed = await service.fail_queue_item(items[0], detail="boom")
        assert failed.status == SyncQueueStatus.FAILED
        assert failed.retry_count == 1
        requeued = await service.requeue_item(failed)
        assert requeued.status == SyncQueueStatus.QUEUED


class TestPushService:
    async def test_register_token_creates_then_updates(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-17",
            platform=MobilePlatform.IOS,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = PushService(repos.push_tokens, repos.notifications)
        token1 = await service.register_token(
            organization_id,
            device_id=device.id,
            platform=PushPlatform.APNS,
            token_value="a",
            now=utcnow(),
        )
        token2 = await service.register_token(
            organization_id,
            device_id=device.id,
            platform=PushPlatform.APNS,
            token_value="b",
            now=utcnow(),
        )
        assert token1.id == token2.id
        assert token2.token_value == "b"

    async def test_attempt_delivery_success(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-18",
            platform=MobilePlatform.IOS,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = PushService(repos.push_tokens, repos.notifications, publish=publisher)
        notification = await service.enqueue(
            organization_id, device_id=device.id, title="t", body="b"
        )
        delivered = await service.attempt_delivery(
            notification, "dev-18", token_usable=True, max_retry_count=3, now=utcnow()
        )
        assert delivered.status == NotificationDeliveryStatus.DELIVERED
        assert "PushDelivered" in publisher.names()

    async def test_attempt_delivery_retries_then_fails(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-19",
            platform=MobilePlatform.IOS,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = PushService(repos.push_tokens, repos.notifications, publish=publisher)
        notification = await service.enqueue(
            organization_id, device_id=device.id, title="t", body="b"
        )
        # max_retry_count=2: the 1st failed attempt (retry_count -> 1)
        # still has a retry left (1 < 2), so it stays PENDING; the 2nd
        # failed attempt (retry_count -> 2) exhausts the budget (2 < 2
        # is False) and transitions straight to FAILED.
        notification = await service.attempt_delivery(
            notification, "dev-19", token_usable=False, max_retry_count=2, now=utcnow()
        )
        assert notification.status == NotificationDeliveryStatus.PENDING
        assert notification.retry_count == 1

        notification = await service.attempt_delivery(
            notification, "dev-19", token_usable=False, max_retry_count=2, now=utcnow()
        )
        assert notification.status == NotificationDeliveryStatus.FAILED
        assert "PushFailed" in publisher.names()

    async def test_mark_read(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-20",
            platform=MobilePlatform.IOS,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = PushService(repos.push_tokens, repos.notifications)
        notification = await service.enqueue(
            organization_id, device_id=device.id, title="t", body="b"
        )
        notification = await service.attempt_delivery(
            notification, "dev-20", token_usable=True, max_retry_count=3, now=utcnow()
        )
        read = await service.mark_read(notification, now=utcnow())
        assert read.status == NotificationDeliveryStatus.READ


class TestAppVersionService:
    async def test_publish_version_publishes_event(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = AppVersionService(repos.app_versions, publish=publisher)
        version = await service.publish_version(
            organization_id,
            platform=MobilePlatform.ANDROID,
            version="2.0.0",
            minimum_version="1.0.0",
            recommended_version="2.0.0",
            is_forced_upgrade=False,
            now=utcnow(),
        )
        assert version.version_label == "2.0.0"
        assert "AppUpdated" in publisher.names()


class TestConfigurationService:
    async def test_create_entry_and_resolve(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = ConfigurationService(repos.configuration)
        await service.create_entry(organization_id, key="feature_x", value={"on": True})
        resolved = await service.resolve(
            organization_id, platform=MobilePlatform.ANDROID, environment="production"
        )
        assert resolved["feature_x"] == {"on": True}


class TestStatisticsService:
    async def test_compute_snapshot(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-21",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        analytics = AnalyticsService(repos.analytics)
        telemetry = TelemetryService(repos.telemetry)
        now = utcnow()
        await analytics.record(
            organization_id,
            device_id=device.id,
            user_id="u1",
            metric_type=AnalyticsMetricType.SESSION_DURATION,
            value=100.0,
            recorded_at=now,
        )
        await telemetry.record(
            organization_id,
            device_id=device.id,
            metric_type=TelemetryMetricType.CRASH,
            value=1.0,
            recorded_at=now,
        )
        service = StatisticsService(repos.analytics, repos.telemetry)
        snapshot = await service.compute(organization_id, since=hours_ago(1), until=hours_ahead(1))
        assert snapshot.daily_active_users == 1
        assert snapshot.session_count == 1
        assert snapshot.crash_count == 1


class TestReportService:
    async def test_generate(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = ReportService(repos.reports)
        report = await service.generate(
            organization_id,
            kind=ReportKind.DEVICE,
            title="Devices",
            period_start=hours_ago(1),
            period_end=utcnow(),
            row_count=5,
            now=utcnow(),
        )
        assert report.row_count == 5


class TestTelemetryAndAnalyticsServices:
    async def test_telemetry_record(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-22",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = TelemetryService(repos.telemetry)
        event = await service.record(
            organization_id,
            device_id=device.id,
            metric_type=TelemetryMetricType.BATTERY,
            value=80.0,
            recorded_at=utcnow(),
        )
        assert event.value == 80.0

    async def test_analytics_record(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        device_service = DeviceService(repos.devices)
        device, _ = await device_service.find_or_register(
            organization_id,
            device_identifier="dev-23",
            platform=MobilePlatform.ANDROID,
            device_model=None,
            os_version=None,
            app_version_label=None,
            now=utcnow(),
        )
        service = AnalyticsService(repos.analytics)
        event = await service.record(
            organization_id,
            device_id=device.id,
            user_id="u1",
            metric_type=AnalyticsMetricType.FEATURE_USAGE,
            value=1.0,
            recorded_at=utcnow(),
        )
        assert event.value == 1.0


class TestQrService:
    async def test_issue_and_redeem_once(
        self, organization_id: uuid.UUID, cache_framework: object
    ) -> None:
        service = QrService(cache_framework.manager)  # type: ignore[attr-defined]
        token = await service.issue(
            organization_id, purpose=QrPurpose.DEVICE_ENROLLMENT, ttl_minutes=15, now=utcnow()
        )
        payload = await service.redeem(token)
        assert payload is not None
        assert payload["organization_id"] == str(organization_id)
        assert payload["purpose"] == QrPurpose.DEVICE_ENROLLMENT.value

        second = await service.redeem(token)
        assert second is None

    async def test_redeem_unknown_token(self, cache_framework: object) -> None:
        service = QrService(cache_framework.manager)  # type: ignore[attr-defined]
        assert await service.redeem("does-not-exist") is None
