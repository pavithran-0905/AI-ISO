"""Integration tests for repository query methods, against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from shared_core.exceptions.not_found import NotFoundError

from app.models.admin import AdminAction, AdminSession
from app.models.api_management import ApiKey, ApiUsage
from app.models.diagnostics import Diagnostic, HealthCheck
from app.models.enums import (
    ApiKeyStatus,
    AuditAction,
    DiagnosticCategory,
    FeatureFlagScope,
    HealthCheckStatus,
    JobPriority,
    JobStatus,
    MaintenanceKind,
    MaintenanceStatus,
    OrganizationStatus,
    ProvisioningStatus,
    ReportFormat,
    ReportKind,
    ReportStatus,
    SecurityEventKind,
    SecurityEventSeverity,
    TenantStatus,
)
from app.models.jobs import JobHistory, SystemJob
from app.models.maintenance import MaintenanceWindow, PlatformAnnouncement
from app.models.reporting import SystemAudit, SystemReport, SystemStatistic
from app.models.security import SecurityEvent, SecuritySetting
from app.models.settings import FeatureFlag, PlatformSetting, SystemConfiguration
from app.models.tenants import (
    Organization,
    Tenant,
    TenantHealth,
    TenantLimit,
    TenantProvisioning,
    TenantUsage,
)

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _organization(organization_id: UUID, *, name: str = "Acme Corp") -> Organization:
    return Organization(
        organization_id=organization_id, name=name, status=OrganizationStatus.ACTIVE
    )


def _tenant(organization_id: UUID, organization_ref_id: UUID, *, name: str = "t1") -> Tenant:
    return Tenant(
        organization_id=organization_id, organization_ref_id=organization_ref_id, name=name
    )


class TestOrganizationRepository:
    async def test_require_in_org(self, repos, organization_id: UUID) -> None:
        created = await repos.organizations.create(_organization(organization_id))
        found = await repos.organizations.require_in_org(organization_id, created.id)
        assert found.id == created.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.organizations.require_in_org(organization_id, uuid4())

    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.organizations.create(_organization(organization_id))
        found = await repos.organizations.list_recent(organization_id)
        assert len(found) == 1


class TestTenantRepository:
    async def test_require_in_org(self, repos, organization_id: UUID) -> None:
        org = await repos.organizations.create(_organization(organization_id))
        created = await repos.tenants.create(_tenant(organization_id, org.id))
        found = await repos.tenants.require_in_org(organization_id, created.id)
        assert found.id == created.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.tenants.require_in_org(organization_id, uuid4())

    async def test_list_for_organization_ref(self, repos, organization_id: UUID) -> None:
        org = await repos.organizations.create(_organization(organization_id))
        await repos.tenants.create(_tenant(organization_id, org.id))
        found = await repos.tenants.list_for_organization_ref(org.id)
        assert len(found) == 1

    async def test_list_recent_by_status_and_organization_ids(
        self, repos, organization_id: UUID
    ) -> None:
        org = await repos.organizations.create(_organization(organization_id))
        await repos.tenants.create(_tenant(organization_id, org.id))
        found = await repos.tenants.list_recent(organization_id, status=TenantStatus.PROVISIONING)
        assert len(found) == 1
        by_status = await repos.tenants.list_by_status(
            organization_id, status=TenantStatus.PROVISIONING
        )
        assert len(by_status) == 1
        ids = await repos.tenants.list_organization_ids()
        assert organization_id in ids


class TestTenantSettingRepository:
    async def test_list_for_tenant_and_find_by_key(self, repos, organization_id: UUID) -> None:
        org = await repos.organizations.create(_organization(organization_id))
        tenant = await repos.tenants.create(_tenant(organization_id, org.id))
        from app.models.tenants import TenantSetting

        await repos.tenant_settings.create(
            TenantSetting(
                organization_id=organization_id,
                tenant_id=tenant.id,
                key="theme",
                value={"dark": True},
            )
        )
        found = await repos.tenant_settings.list_for_tenant(tenant.id)
        assert len(found) == 1
        by_key = await repos.tenant_settings.find_by_key(tenant.id, key="theme")
        assert by_key is not None


class TestTenantLimitRepository:
    async def test_list_for_tenant_and_find_by_metric(self, repos, organization_id: UUID) -> None:
        org = await repos.organizations.create(_organization(organization_id))
        tenant = await repos.tenants.create(_tenant(organization_id, org.id))
        await repos.tenant_limits.create(
            TenantLimit(
                organization_id=organization_id,
                tenant_id=tenant.id,
                metric_key="seats",
                limit_value=10.0,
            )
        )
        found = await repos.tenant_limits.list_for_tenant(tenant.id)
        assert len(found) == 1
        by_metric = await repos.tenant_limits.find_by_metric(tenant.id, metric_key="seats")
        assert by_metric is not None


class TestTenantUsageRepository:
    async def test_list_for_tenant_and_latest(self, repos, organization_id: UUID) -> None:
        org = await repos.organizations.create(_organization(organization_id))
        tenant = await repos.tenants.create(_tenant(organization_id, org.id))
        await repos.tenant_usage.create(
            TenantUsage(
                organization_id=organization_id,
                tenant_id=tenant.id,
                metric_key="seats",
                used_value=3.0,
                recorded_at=NOW - timedelta(hours=1),
            )
        )
        await repos.tenant_usage.create(
            TenantUsage(
                organization_id=organization_id,
                tenant_id=tenant.id,
                metric_key="seats",
                used_value=5.0,
                recorded_at=NOW,
            )
        )
        found = await repos.tenant_usage.list_for_tenant(tenant.id)
        assert len(found) == 2
        by_metric = await repos.tenant_usage.list_for_tenant(tenant.id, metric_key="seats")
        assert len(by_metric) == 2
        latest = await repos.tenant_usage.latest_for_metric(tenant.id, metric_key="seats")
        assert latest is not None and latest.used_value == 5.0


class TestTenantHealthRepository:
    async def test_latest_for_tenant_and_list(self, repos, organization_id: UUID) -> None:
        org = await repos.organizations.create(_organization(organization_id))
        tenant = await repos.tenants.create(_tenant(organization_id, org.id))
        await repos.tenant_health.create(
            TenantHealth(
                organization_id=organization_id,
                tenant_id=tenant.id,
                status=HealthCheckStatus.HEALTHY,
                checked_at=NOW - timedelta(hours=1),
            )
        )
        await repos.tenant_health.create(
            TenantHealth(
                organization_id=organization_id,
                tenant_id=tenant.id,
                status=HealthCheckStatus.DEGRADED,
                checked_at=NOW,
            )
        )
        latest = await repos.tenant_health.latest_for_tenant(tenant.id)
        assert latest is not None and latest.status == HealthCheckStatus.DEGRADED
        found = await repos.tenant_health.list_for_tenant(tenant.id)
        assert len(found) == 2


class TestTenantProvisioningRepository:
    async def test_list_for_tenant(self, repos, organization_id: UUID) -> None:
        org = await repos.organizations.create(_organization(organization_id))
        tenant = await repos.tenants.create(_tenant(organization_id, org.id))
        await repos.tenant_provisioning.create(
            TenantProvisioning(
                organization_id=organization_id,
                tenant_id=tenant.id,
                status=ProvisioningStatus.COMPLETED,
                requested_at=NOW,
            )
        )
        found = await repos.tenant_provisioning.list_for_tenant(tenant.id)
        assert len(found) == 1


class TestPlatformSettingRepository:
    async def test_find_by_key_and_list_all(self, repos, organization_id: UUID) -> None:
        await repos.platform_settings.create(
            PlatformSetting(
                organization_id=organization_id, key="brand_name", value={"name": "AI-IOS"}
            )
        )
        found = await repos.platform_settings.find_by_key(organization_id, key="brand_name")
        assert found is not None
        all_settings = await repos.platform_settings.list_all(organization_id)
        assert len(all_settings) == 1


class TestSystemConfigurationRepository:
    async def test_find_by_key_and_list_all(self, repos, organization_id: UUID) -> None:
        await repos.system_configuration.create(
            SystemConfiguration(
                organization_id=organization_id, key="feature_x", value={"enabled": True}
            )
        )
        found = await repos.system_configuration.find_by_key(organization_id, key="feature_x")
        assert found is not None
        all_configs = await repos.system_configuration.list_all(organization_id)
        assert len(all_configs) == 1


class TestFeatureFlagRepository:
    async def test_find_by_name_and_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.feature_flags.create(
            FeatureFlag(
                organization_id=organization_id, name="new-ui", scope=FeatureFlagScope.GLOBAL
            )
        )
        found = await repos.feature_flags.find_by_name(organization_id, name="new-ui")
        assert found is not None
        recent = await repos.feature_flags.list_recent(
            organization_id, scope=FeatureFlagScope.GLOBAL
        )
        assert len(recent) == 1


class TestAdminSessionRepository:
    async def test_list_for_admin_user_and_enabled(self, repos, organization_id: UUID) -> None:
        await repos.admin_sessions.create(
            AdminSession(
                organization_id=organization_id,
                admin_user_id="admin-1",
                started_at=NOW,
                expires_at=NOW + timedelta(hours=1),
            )
        )
        found = await repos.admin_sessions.list_for_admin_user("admin-1")
        assert len(found) == 1
        enabled = await repos.admin_sessions.list_enabled(organization_id)
        assert len(enabled) == 1


class TestAdminActionRepository:
    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.admin_actions.create(
            AdminAction(
                organization_id=organization_id,
                admin_user_id="admin-1",
                action="force_logout",
                target_type="admin_session",
                performed_at=NOW,
            )
        )
        found = await repos.admin_actions.list_recent(
            organization_id, since=NOW - timedelta(hours=1)
        )
        assert len(found) == 1


class TestSystemJobRepository:
    async def test_require_in_org(self, repos, organization_id: UUID) -> None:
        created = await repos.jobs.create(
            SystemJob(
                organization_id=organization_id,
                job_key="sync-1",
                priority=JobPriority.NORMAL,
                queued_at=NOW,
            )
        )
        found = await repos.jobs.require_in_org(organization_id, created.id)
        assert found.id == created.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.jobs.require_in_org(organization_id, uuid4())

    async def test_list_recent_by_status_and_organization_ids(
        self, repos, organization_id: UUID
    ) -> None:
        await repos.jobs.create(
            SystemJob(
                organization_id=organization_id,
                job_key="sync-1",
                priority=JobPriority.NORMAL,
                queued_at=NOW,
            )
        )
        found = await repos.jobs.list_recent(organization_id, status=JobStatus.QUEUED)
        assert len(found) == 1
        by_status = await repos.jobs.list_by_status(organization_id, status=JobStatus.QUEUED)
        assert len(by_status) == 1
        ids = await repos.jobs.list_organization_ids()
        assert organization_id in ids


class TestJobHistoryRepository:
    async def test_list_for_job(self, repos, organization_id: UUID) -> None:
        job = await repos.jobs.create(
            SystemJob(
                organization_id=organization_id,
                job_key="sync-1",
                priority=JobPriority.NORMAL,
                queued_at=NOW,
            )
        )
        await repos.job_history.create(
            JobHistory(
                organization_id=organization_id,
                job_id=job.id,
                status=JobStatus.QUEUED,
                occurred_at=NOW,
            )
        )
        found = await repos.job_history.list_for_job(job.id)
        assert len(found) == 1


class TestMaintenanceWindowRepository:
    async def test_require_in_org_and_list(self, repos, organization_id: UUID) -> None:
        created = await repos.maintenance_windows.create(
            MaintenanceWindow(
                organization_id=organization_id,
                title="Upgrade",
                kind=MaintenanceKind.ROUTINE,
                starts_at=NOW,
                ends_at=NOW + timedelta(hours=2),
            )
        )
        found = await repos.maintenance_windows.require_in_org(organization_id, created.id)
        assert found.id == created.id
        recent = await repos.maintenance_windows.list_recent(
            organization_id, status=MaintenanceStatus.SCHEDULED
        )
        assert len(recent) == 1
        by_status = await repos.maintenance_windows.list_by_status(
            organization_id, status=MaintenanceStatus.SCHEDULED
        )
        assert len(by_status) == 1
        ids = await repos.maintenance_windows.list_organization_ids()
        assert organization_id in ids

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.maintenance_windows.require_in_org(organization_id, uuid4())


class TestPlatformAnnouncementRepository:
    async def test_list_enabled(self, repos, organization_id: UUID) -> None:
        await repos.announcements.create(
            PlatformAnnouncement(organization_id=organization_id, title="Notice", body="Body text")
        )
        found = await repos.announcements.list_enabled(organization_id)
        assert len(found) == 1


class TestApiKeyRepository:
    async def test_require_in_org_and_find_by_hash(self, repos, organization_id: UUID) -> None:
        created = await repos.api_keys.create(
            ApiKey(organization_id=organization_id, name="ci-key", key_hash="abc123")
        )
        found = await repos.api_keys.require_in_org(organization_id, created.id)
        assert found.id == created.id
        by_hash = await repos.api_keys.find_by_hash("abc123")
        assert by_hash is not None
        recent = await repos.api_keys.list_recent(organization_id, status=ApiKeyStatus.ACTIVE)
        assert len(recent) == 1
        by_status = await repos.api_keys.list_by_status(organization_id, status=ApiKeyStatus.ACTIVE)
        assert len(by_status) == 1
        ids = await repos.api_keys.list_organization_ids()
        assert organization_id in ids

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.api_keys.require_in_org(organization_id, uuid4())


class TestApiUsageRepository:
    async def test_find_window_and_total(self, repos, organization_id: UUID) -> None:
        key = await repos.api_keys.create(
            ApiKey(organization_id=organization_id, name="ci-key", key_hash="h1")
        )
        await repos.api_usage.create(
            ApiUsage(
                organization_id=organization_id,
                api_key_id=key.id,
                window_start=NOW,
                window_end=NOW + timedelta(hours=1),
                request_count=5,
            )
        )
        found = await repos.api_usage.find_window(key.id, window_start=NOW)
        assert found is not None
        for_key = await repos.api_usage.list_for_key(key.id)
        assert len(for_key) == 1
        total = await repos.api_usage.total_requests_for_org(
            organization_id, since=NOW - timedelta(hours=1)
        )
        assert total == 5


class TestSecuritySettingRepository:
    async def test_find_by_key_and_list_all(self, repos, organization_id: UUID) -> None:
        await repos.security_settings.create(
            SecuritySetting(
                organization_id=organization_id, key="password_policy", value={"min_length": 8}
            )
        )
        found = await repos.security_settings.find_by_key(organization_id, key="password_policy")
        assert found is not None
        all_settings = await repos.security_settings.list_all(organization_id)
        assert len(all_settings) == 1


class TestSecurityEventRepository:
    async def test_list_recent_and_count(self, repos, organization_id: UUID) -> None:
        await repos.security_events.create(
            SecurityEvent(
                organization_id=organization_id,
                kind=SecurityEventKind.LOGIN_FAILURE,
                severity=SecurityEventSeverity.LOW,
                detected_at=NOW,
            )
        )
        found = await repos.security_events.list_recent(
            organization_id, since=NOW - timedelta(hours=1)
        )
        assert len(found) == 1
        by_severity = await repos.security_events.list_recent(
            organization_id, severity=SecurityEventSeverity.LOW
        )
        assert len(by_severity) == 1
        count = await repos.security_events.count_since(
            organization_id, since=NOW - timedelta(hours=1)
        )
        assert count == 1
        ids = await repos.security_events.list_organization_ids()
        assert organization_id in ids


class TestDiagnosticRepository:
    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.diagnostics.create(
            Diagnostic(
                organization_id=organization_id,
                category=DiagnosticCategory.DATABASE,
                ran_at=NOW,
                status=HealthCheckStatus.HEALTHY,
            )
        )
        found = await repos.diagnostics.list_recent(
            organization_id, category=DiagnosticCategory.DATABASE
        )
        assert len(found) == 1


class TestHealthCheckRepository:
    async def test_find_by_component_and_list(self, repos, organization_id: UUID) -> None:
        await repos.health_checks.create(
            HealthCheck(
                organization_id=organization_id,
                component="database",
                status=HealthCheckStatus.HEALTHY,
                checked_at=NOW,
            )
        )
        found = await repos.health_checks.find_by_component(organization_id, component="database")
        assert found is not None
        all_checks = await repos.health_checks.list_all(organization_id)
        assert len(all_checks) == 1
        ids = await repos.health_checks.list_organization_ids()
        assert organization_id in ids


class TestSystemStatisticRepository:
    async def test_find_window_and_list_range(self, repos, organization_id: UUID) -> None:
        await repos.statistics.create(
            SystemStatistic(
                organization_id=organization_id,
                window_start=NOW,
                window_end=NOW + timedelta(hours=1),
            )
        )
        found = await repos.statistics.find_window(organization_id, window_start=NOW)
        assert found is not None
        in_range = await repos.statistics.list_range(
            organization_id, since=NOW - timedelta(hours=1)
        )
        assert len(in_range) == 1

    async def test_find_window_missing_returns_none(self, repos, organization_id: UUID) -> None:
        assert await repos.statistics.find_window(organization_id, window_start=NOW) is None


class TestSystemReportRepository:
    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.reports.create(
            SystemReport(
                organization_id=organization_id,
                kind=ReportKind.PLATFORM,
                report_format=ReportFormat.JSON,
                title="Platform Report",
                status=ReportStatus.COMPLETED,
            )
        )
        recent = await repos.reports.list_recent(organization_id, status=ReportStatus.COMPLETED)
        assert len(recent) == 1
        by_kind = await repos.reports.list_recent(organization_id, kind=ReportKind.PLATFORM)
        assert len(by_kind) == 1


class TestSystemAuditRepository:
    async def test_list_recent_and_for_entity(self, repos, organization_id: UUID) -> None:
        entity_id = uuid4()
        await repos.audit.create(
            SystemAudit(
                organization_id=organization_id,
                action=AuditAction.ADMIN_LOGIN,
                entity_type="admin_session",
                entity_id=entity_id,
                occurred_at=NOW,
            )
        )
        found = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert len(found) == 1
        for_entity = await repos.audit.list_for_entity("admin_session", entity_id)
        assert len(for_entity) == 1
        ids = await repos.audit.list_organization_ids()
        assert organization_id in ids

    async def test_list_recent_excludes_before_since(self, repos, organization_id: UUID) -> None:
        await repos.audit.create(
            SystemAudit(
                organization_id=organization_id,
                action=AuditAction.ADMIN_LOGIN,
                entity_type="admin_session",
                occurred_at=NOW - timedelta(days=10),
            )
        )
        found = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert found == []
