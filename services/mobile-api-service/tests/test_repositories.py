"""Integration tests for every repository, against real PostgreSQL."""

from __future__ import annotations

import uuid

from app.models.configuration import MobileAppVersion, MobileConfiguration
from app.models.devices import MobileDevice, MobileProfile, MobileSession, MobileToken
from app.models.enums import (
    AnalyticsMetricType,
    DeviceTrustStatus,
    MobileAuditAction,
    MobileAuthMethod,
    MobilePlatform,
    NotificationDeliveryStatus,
    PushPlatform,
    ReleaseChannel,
    ReportFormat,
    ReportKind,
    ReportStatus,
    SessionStatus,
    SyncQueueStatus,
    SyncType,
    TelemetryMetricType,
    TokenStatus,
)
from app.models.notifications import MobileNotification, MobilePushToken
from app.models.reporting import MobileAudit, MobileReport
from app.models.sync import MobileSyncJob, MobileSyncQueueItem
from app.models.telemetry import MobileAnalyticsEvent, MobileTelemetryEvent
from app.services.bundle import Repositories
from tests.conftest import hours_ago, hours_ahead, utcnow


async def _make_device(
    repos: Repositories, organization_id: uuid.UUID, **overrides: object
) -> MobileDevice:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "device_identifier": f"dev-{uuid.uuid4()}",
        "platform": MobilePlatform.ANDROID,
        "last_seen_at": utcnow(),
    }
    defaults.update(overrides)
    return await repos.devices.create(MobileDevice(**defaults))  # type: ignore[arg-type]


class TestMobileDeviceRepository:
    async def test_find_by_identifier(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device = await _make_device(repos, organization_id, device_identifier="abc-123")
        found = await repos.devices.find_by_identifier(organization_id, device_identifier="abc-123")
        assert found is not None
        assert found.id == device.id

    async def test_find_by_identifier_missing(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        assert (
            await repos.devices.find_by_identifier(organization_id, device_identifier="nope")
            is None
        )

    async def test_tenant_isolation(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        other_org = uuid.uuid4()
        await _make_device(repos, other_org, device_identifier="shared-id")
        assert (
            await repos.devices.find_by_identifier(organization_id, device_identifier="shared-id")
            is None
        )

    async def test_list_recent(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        await _make_device(repos, organization_id)
        await _make_device(repos, organization_id)
        rows = await repos.devices.list_recent(organization_id)
        assert len(rows) == 2

    async def test_list_by_trust_status(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await _make_device(repos, organization_id, trust_status=DeviceTrustStatus.APPROVED)
        await _make_device(repos, organization_id, trust_status=DeviceTrustStatus.PENDING)
        approved = await repos.devices.list_by_trust_status(
            organization_id, trust_status=DeviceTrustStatus.APPROVED
        )
        assert len(approved) == 1

    async def test_list_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await _make_device(repos, organization_id)
        ids = await repos.devices.list_organization_ids()
        assert organization_id in ids


class TestMobileSessionRepository:
    async def test_find_active_for_device(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device = await _make_device(repos, organization_id)
        session = await repos.sessions.create(
            MobileSession(
                organization_id=organization_id,
                device_id=device.id,
                user_id="user-1",
                auth_method=MobileAuthMethod.JWT,
                issued_at=utcnow(),
                expires_at=hours_ahead(1),
            )
        )
        found = await repos.sessions.find_active_for_device(
            organization_id, device_id=device.id, user_id="user-1"
        )
        assert found is not None
        assert found.id == session.id

    async def test_find_active_for_device_wrong_user(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device = await _make_device(repos, organization_id)
        await repos.sessions.create(
            MobileSession(
                organization_id=organization_id,
                device_id=device.id,
                user_id="user-1",
                auth_method=MobileAuthMethod.JWT,
                issued_at=utcnow(),
                expires_at=hours_ahead(1),
            )
        )
        assert (
            await repos.sessions.find_active_for_device(
                organization_id, device_id=device.id, user_id="user-2"
            )
            is None
        )

    async def test_has_prior_session(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        device = await _make_device(repos, organization_id)
        assert not await repos.sessions.has_prior_session(organization_id, device_id=device.id)
        await repos.sessions.create(
            MobileSession(
                organization_id=organization_id,
                device_id=device.id,
                user_id="user-1",
                auth_method=MobileAuthMethod.JWT,
                issued_at=utcnow(),
                expires_at=hours_ahead(1),
            )
        )
        assert await repos.sessions.has_prior_session(organization_id, device_id=device.id)

    async def test_list_active(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        device = await _make_device(repos, organization_id)
        await repos.sessions.create(
            MobileSession(
                organization_id=organization_id,
                device_id=device.id,
                user_id="u",
                auth_method=MobileAuthMethod.JWT,
                status=SessionStatus.EXPIRED,
                issued_at=utcnow(),
                expires_at=hours_ago(1),
            )
        )
        await repos.sessions.create(
            MobileSession(
                organization_id=organization_id,
                device_id=device.id,
                user_id="u2",
                auth_method=MobileAuthMethod.JWT,
                issued_at=utcnow(),
                expires_at=hours_ahead(1),
            )
        )
        active = await repos.sessions.list_active(organization_id)
        assert len(active) == 1

    async def test_list_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device = await _make_device(repos, organization_id)
        await repos.sessions.create(
            MobileSession(
                organization_id=organization_id,
                device_id=device.id,
                user_id="u",
                auth_method=MobileAuthMethod.JWT,
                issued_at=utcnow(),
                expires_at=hours_ahead(1),
            )
        )
        assert organization_id in await repos.sessions.list_organization_ids()


class TestMobileProfileRepository:
    async def test_find_by_user_missing(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        assert await repos.profiles.find_by_user(organization_id, user_id="ghost") is None

    async def test_find_by_user(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        profile = await repos.profiles.create(
            MobileProfile(organization_id=organization_id, user_id="u1", display_name="Ada")
        )
        found = await repos.profiles.find_by_user(organization_id, user_id="u1")
        assert found is not None
        assert found.id == profile.id


class TestMobileTokenRepository:
    async def test_list_active(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        device = await _make_device(repos, organization_id)
        await repos.tokens.create(
            MobileToken(
                organization_id=organization_id,
                device_id=device.id,
                token_hash="hash-1",
                status=TokenStatus.EXPIRED,
                issued_at=utcnow(),
                expires_at=hours_ago(1),
            )
        )
        await repos.tokens.create(
            MobileToken(
                organization_id=organization_id,
                device_id=device.id,
                token_hash="hash-2",
                issued_at=utcnow(),
                expires_at=hours_ahead(1),
            )
        )
        active = await repos.tokens.list_active(organization_id)
        assert len(active) == 1

    async def test_list_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device = await _make_device(repos, organization_id)
        await repos.tokens.create(
            MobileToken(
                organization_id=organization_id,
                device_id=device.id,
                token_hash="hash-3",
                issued_at=utcnow(),
                expires_at=hours_ahead(1),
            )
        )
        assert organization_id in await repos.tokens.list_organization_ids()


class TestMobileSyncRepositories:
    async def test_list_for_job_and_queued(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device = await _make_device(repos, organization_id)
        job = await repos.sync_jobs.create(
            MobileSyncJob(
                organization_id=organization_id, device_id=device.id, sync_type=SyncType.DELTA
            )
        )
        await repos.sync_queue.create(
            MobileSyncQueueItem(
                organization_id=organization_id,
                sync_job_id=job.id,
                device_id=device.id,
                action_type="update",
                client_updated_at=utcnow(),
            )
        )
        items = await repos.sync_queue.list_for_job(job.id)
        assert len(items) == 1
        queued = await repos.sync_queue.list_queued(organization_id)
        assert len(queued) == 1

    async def test_list_for_device(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        device = await _make_device(repos, organization_id)
        await repos.sync_jobs.create(
            MobileSyncJob(
                organization_id=organization_id, device_id=device.id, sync_type=SyncType.MANUAL
            )
        )
        jobs = await repos.sync_jobs.list_for_device(organization_id, device_id=device.id)
        assert len(jobs) == 1

    async def test_list_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device = await _make_device(repos, organization_id)
        job = await repos.sync_jobs.create(
            MobileSyncJob(
                organization_id=organization_id, device_id=device.id, sync_type=SyncType.MANUAL
            )
        )
        await repos.sync_queue.create(
            MobileSyncQueueItem(
                organization_id=organization_id,
                sync_job_id=job.id,
                device_id=device.id,
                action_type="update",
                status=SyncQueueStatus.QUEUED,
                client_updated_at=utcnow(),
            )
        )
        assert organization_id in await repos.sync_queue.list_organization_ids()


class TestNotificationRepositories:
    async def test_find_for_device_and_active_list(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device = await _make_device(repos, organization_id)
        token = await repos.push_tokens.create(
            MobilePushToken(
                organization_id=organization_id,
                device_id=device.id,
                platform=PushPlatform.FCM,
                token_value="tok-1",
                registered_at=utcnow(),
            )
        )
        found = await repos.push_tokens.find_for_device(
            organization_id, device_id=device.id, platform=PushPlatform.FCM
        )
        assert found is not None
        assert found.id == token.id
        active = await repos.push_tokens.list_active_for_device(
            organization_id, device_id=device.id
        )
        assert len(active) == 1

    async def test_list_pending_and_for_device(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device = await _make_device(repos, organization_id)
        await repos.notifications.create(
            MobileNotification(
                organization_id=organization_id, device_id=device.id, title="t", body="b"
            )
        )
        await repos.notifications.create(
            MobileNotification(
                organization_id=organization_id,
                device_id=device.id,
                title="t2",
                body="b2",
                status=NotificationDeliveryStatus.DELIVERED,
            )
        )
        pending = await repos.notifications.list_pending(organization_id)
        assert len(pending) == 1
        for_device = await repos.notifications.list_for_device(organization_id, device_id=device.id)
        assert len(for_device) == 2

    async def test_list_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device = await _make_device(repos, organization_id)
        await repos.notifications.create(
            MobileNotification(
                organization_id=organization_id, device_id=device.id, title="t", body="b"
            )
        )
        assert organization_id in await repos.notifications.list_organization_ids()


class TestConfigurationRepositories:
    async def test_find_latest_for_platform(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.app_versions.create(
            MobileAppVersion(
                organization_id=organization_id,
                platform=MobilePlatform.IOS,
                version_label="1.0.0",
                release_channel=ReleaseChannel.STABLE,
                minimum_version_label="1.0.0",
                recommended_version_label="1.0.0",
                released_at=hours_ago(2),
            )
        )
        newer = await repos.app_versions.create(
            MobileAppVersion(
                organization_id=organization_id,
                platform=MobilePlatform.IOS,
                version_label="2.0.0",
                release_channel=ReleaseChannel.STABLE,
                minimum_version_label="1.0.0",
                recommended_version_label="2.0.0",
                released_at=hours_ago(1),
            )
        )
        latest = await repos.app_versions.find_latest_for_platform(
            organization_id, platform=MobilePlatform.IOS
        )
        assert latest is not None
        assert latest.id == newer.id

    async def test_find_latest_for_platform_missing(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        assert (
            await repos.app_versions.find_latest_for_platform(
                organization_id, platform=MobilePlatform.ANDROID
            )
            is None
        )

    async def test_list_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.app_versions.create(
            MobileAppVersion(
                organization_id=organization_id,
                platform=MobilePlatform.ANDROID,
                version_label="1.0.0",
                minimum_version_label="1.0.0",
                recommended_version_label="1.0.0",
                released_at=utcnow(),
            )
        )
        assert organization_id in await repos.app_versions.list_organization_ids()

    async def test_list_for_environment(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.configuration.create(
            MobileConfiguration(organization_id=organization_id, key="k", environment="production")
        )
        await repos.configuration.create(
            MobileConfiguration(organization_id=organization_id, key="k2", environment="staging")
        )
        production = await repos.configuration.list_for_environment(
            organization_id, environment="production"
        )
        assert len(production) == 1


class TestTelemetryRepositories:
    async def test_list_since(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        device = await _make_device(repos, organization_id)
        await repos.telemetry.create(
            MobileTelemetryEvent(
                organization_id=organization_id,
                device_id=device.id,
                metric_type=TelemetryMetricType.CRASH,
                value=1.0,
                recorded_at=hours_ago(1),
            )
        )
        await repos.telemetry.create(
            MobileTelemetryEvent(
                organization_id=organization_id,
                device_id=device.id,
                metric_type=TelemetryMetricType.CRASH,
                value=1.0,
                recorded_at=hours_ago(48),
            )
        )
        recent = await repos.telemetry.list_since(organization_id, since=hours_ago(2))
        assert len(recent) == 1

    async def test_list_for_device(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        device = await _make_device(repos, organization_id)
        await repos.telemetry.create(
            MobileTelemetryEvent(
                organization_id=organization_id,
                device_id=device.id,
                metric_type=TelemetryMetricType.LATENCY,
                value=42.0,
                recorded_at=utcnow(),
            )
        )
        rows = await repos.telemetry.list_for_device(organization_id, device_id=device.id)
        assert len(rows) == 1

    async def test_analytics_list_since(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        device = await _make_device(repos, organization_id)
        await repos.analytics.create(
            MobileAnalyticsEvent(
                organization_id=organization_id,
                device_id=device.id,
                user_id="u1",
                metric_type=AnalyticsMetricType.SESSION_DURATION,
                value=120.0,
                recorded_at=utcnow(),
            )
        )
        rows = await repos.analytics.list_since(organization_id, since=hours_ago(1))
        assert len(rows) == 1


class TestReportingRepositories:
    async def test_reports_list_recent_filters(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.reports.create(
            MobileReport(
                organization_id=organization_id,
                kind=ReportKind.DEVICE,
                report_format=ReportFormat.JSON,
                title="Devices",
                status=ReportStatus.COMPLETED,
                period_start=hours_ago(1),
                period_end=utcnow(),
            )
        )
        await repos.reports.create(
            MobileReport(
                organization_id=organization_id,
                kind=ReportKind.SECURITY,
                report_format=ReportFormat.JSON,
                title="Security",
                status=ReportStatus.PENDING,
                period_start=hours_ago(1),
                period_end=utcnow(),
            )
        )
        device_reports = await repos.reports.list_recent(organization_id, kind=ReportKind.DEVICE)
        assert len(device_reports) == 1
        completed = await repos.reports.list_recent(organization_id, status=ReportStatus.COMPLETED)
        assert len(completed) == 1

    async def test_audit_list_recent_and_for_entity(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        entity_id = uuid.uuid4()
        await repos.audit.create(
            MobileAudit(
                organization_id=organization_id,
                action=MobileAuditAction.DEVICE_REGISTRATION,
                entity_type="mobile_device",
                entity_id=entity_id,
                summary="registered",
                occurred_at=utcnow(),
            )
        )
        recent = await repos.audit.list_recent(organization_id)
        assert len(recent) == 1
        for_entity = await repos.audit.list_for_entity("mobile_device", entity_id)
        assert len(for_entity) == 1

    async def test_audit_list_recent_since_filter(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.audit.create(
            MobileAudit(
                organization_id=organization_id,
                action=MobileAuditAction.ADMINISTRATIVE,
                entity_type="x",
                entity_id=uuid.uuid4(),
                summary="old",
                occurred_at=hours_ago(48),
            )
        )
        recent = await repos.audit.list_recent(organization_id, since=hours_ago(1))
        assert len(recent) == 0
