"""The repository bundle every route works through.

One object rather than fourteen constructor arguments, all sharing one
tenant scope: a bundle where one repository was built without it would
enforce tenant isolation everywhere except the one query that forgot,
and that query is the leak.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.configuration import MobileAppVersionRepository, MobileConfigurationRepository
from app.repositories.devices import (
    MobileDeviceRepository,
    MobileProfileRepository,
    MobileSessionRepository,
    MobileTokenRepository,
)
from app.repositories.notifications import MobileNotificationRepository, MobilePushTokenRepository
from app.repositories.reporting import MobileAuditRepository, MobileReportRepository
from app.repositories.sync import MobileSyncJobRepository, MobileSyncQueueItemRepository
from app.repositories.telemetry import (
    MobileAnalyticsEventRepository,
    MobileTelemetryEventRepository,
)


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    devices: MobileDeviceRepository
    sessions: MobileSessionRepository
    profiles: MobileProfileRepository
    tokens: MobileTokenRepository

    sync_jobs: MobileSyncJobRepository
    sync_queue: MobileSyncQueueItemRepository

    push_tokens: MobilePushTokenRepository
    notifications: MobileNotificationRepository

    app_versions: MobileAppVersionRepository
    configuration: MobileConfigurationRepository

    telemetry: MobileTelemetryEventRepository
    analytics: MobileAnalyticsEventRepository

    reports: MobileReportRepository
    audit: MobileAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        devices=MobileDeviceRepository(session, tenant_scope=tenant_scope),
        sessions=MobileSessionRepository(session, tenant_scope=tenant_scope),
        profiles=MobileProfileRepository(session, tenant_scope=tenant_scope),
        tokens=MobileTokenRepository(session, tenant_scope=tenant_scope),
        sync_jobs=MobileSyncJobRepository(session, tenant_scope=tenant_scope),
        sync_queue=MobileSyncQueueItemRepository(session, tenant_scope=tenant_scope),
        push_tokens=MobilePushTokenRepository(session, tenant_scope=tenant_scope),
        notifications=MobileNotificationRepository(session, tenant_scope=tenant_scope),
        app_versions=MobileAppVersionRepository(session, tenant_scope=tenant_scope),
        configuration=MobileConfigurationRepository(session, tenant_scope=tenant_scope),
        telemetry=MobileTelemetryEventRepository(session, tenant_scope=tenant_scope),
        analytics=MobileAnalyticsEventRepository(session, tenant_scope=tenant_scope),
        reports=MobileReportRepository(session, tenant_scope=tenant_scope),
        audit=MobileAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
