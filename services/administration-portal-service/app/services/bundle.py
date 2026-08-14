"""The repository bundle every route works through.

One object rather than twenty-five constructor arguments, all sharing
one tenant scope: a bundle where one repository was built without it
would enforce tenant isolation everywhere except the one query that
forgot, and that query is the leak.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.admin import AdminActionRepository, AdminSessionRepository
from app.repositories.api_management import ApiKeyRepository, ApiUsageRepository
from app.repositories.diagnostics import DiagnosticRepository, HealthCheckRepository
from app.repositories.jobs import JobHistoryRepository, SystemJobRepository
from app.repositories.maintenance import MaintenanceWindowRepository, PlatformAnnouncementRepository
from app.repositories.reporting import (
    SystemAuditRepository,
    SystemReportRepository,
    SystemStatisticRepository,
)
from app.repositories.security import SecurityEventRepository, SecuritySettingRepository
from app.repositories.settings import (
    FeatureFlagRepository,
    PlatformSettingRepository,
    SystemConfigurationRepository,
)
from app.repositories.tenants import (
    OrganizationRepository,
    TenantHealthRepository,
    TenantLimitRepository,
    TenantProvisioningRepository,
    TenantRepository,
    TenantSettingRepository,
    TenantUsageRepository,
)


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    platform_settings: PlatformSettingRepository
    system_configuration: SystemConfigurationRepository
    feature_flags: FeatureFlagRepository

    organizations: OrganizationRepository
    tenants: TenantRepository
    tenant_settings: TenantSettingRepository
    tenant_limits: TenantLimitRepository
    tenant_usage: TenantUsageRepository
    tenant_health: TenantHealthRepository
    tenant_provisioning: TenantProvisioningRepository

    admin_sessions: AdminSessionRepository
    admin_actions: AdminActionRepository

    jobs: SystemJobRepository
    job_history: JobHistoryRepository

    maintenance_windows: MaintenanceWindowRepository
    announcements: PlatformAnnouncementRepository

    api_keys: ApiKeyRepository
    api_usage: ApiUsageRepository

    security_settings: SecuritySettingRepository
    security_events: SecurityEventRepository

    diagnostics: DiagnosticRepository
    health_checks: HealthCheckRepository

    statistics: SystemStatisticRepository
    reports: SystemReportRepository
    audit: SystemAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        platform_settings=PlatformSettingRepository(session, tenant_scope=tenant_scope),
        system_configuration=SystemConfigurationRepository(session, tenant_scope=tenant_scope),
        feature_flags=FeatureFlagRepository(session, tenant_scope=tenant_scope),
        organizations=OrganizationRepository(session, tenant_scope=tenant_scope),
        tenants=TenantRepository(session, tenant_scope=tenant_scope),
        tenant_settings=TenantSettingRepository(session, tenant_scope=tenant_scope),
        tenant_limits=TenantLimitRepository(session, tenant_scope=tenant_scope),
        tenant_usage=TenantUsageRepository(session, tenant_scope=tenant_scope),
        tenant_health=TenantHealthRepository(session, tenant_scope=tenant_scope),
        tenant_provisioning=TenantProvisioningRepository(session, tenant_scope=tenant_scope),
        admin_sessions=AdminSessionRepository(session, tenant_scope=tenant_scope),
        admin_actions=AdminActionRepository(session, tenant_scope=tenant_scope),
        jobs=SystemJobRepository(session, tenant_scope=tenant_scope),
        job_history=JobHistoryRepository(session, tenant_scope=tenant_scope),
        maintenance_windows=MaintenanceWindowRepository(session, tenant_scope=tenant_scope),
        announcements=PlatformAnnouncementRepository(session, tenant_scope=tenant_scope),
        api_keys=ApiKeyRepository(session, tenant_scope=tenant_scope),
        api_usage=ApiUsageRepository(session, tenant_scope=tenant_scope),
        security_settings=SecuritySettingRepository(session, tenant_scope=tenant_scope),
        security_events=SecurityEventRepository(session, tenant_scope=tenant_scope),
        diagnostics=DiagnosticRepository(session, tenant_scope=tenant_scope),
        health_checks=HealthCheckRepository(session, tenant_scope=tenant_scope),
        statistics=SystemStatisticRepository(session, tenant_scope=tenant_scope),
        reports=SystemReportRepository(session, tenant_scope=tenant_scope),
        audit=SystemAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
