"""Integration tests for the service layer, against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.events.domain_events import (
    AdminLoginEvent,
    ConfigurationChangedEvent,
    FeatureFlagUpdatedEvent,
    MaintenanceCompletedEvent,
    MaintenanceStartedEvent,
    PlatformHealthChangedEvent,
    SecurityPolicyUpdatedEvent,
    TenantCreatedEvent,
    TenantDeletedEvent,
    TenantUpdatedEvent,
)
from app.models.enums import (
    AnnouncementScope,
    ApiKeyStatus,
    DiagnosticCategory,
    FeatureFlagScope,
    HealthCheckStatus,
    JobPriority,
    JobStatus,
    MaintenanceKind,
    MaintenanceStatus,
    OrganizationStatus,
    SecurityEventKind,
    SecurityEventSeverity,
    TenantStatus,
)
from app.models.tenants import Organization
from app.services.admin_sessions import AdminActionService, AdminSessionService
from app.services.announcements import AnnouncementService
from app.services.api_keys import ApiKeyService
from app.services.audit import AuditService
from app.services.diagnostics import DiagnosticsService
from app.services.jobs import JobService
from app.services.jobs import TransitionRefusedError as JobTransitionRefusedError
from app.services.maintenance import MaintenanceConflictError, MaintenanceService
from app.services.maintenance import TransitionRefusedError as MaintenanceTransitionRefusedError
from app.services.organizations import OrganizationService
from app.services.organizations import TransitionRefusedError as OrgTransitionRefusedError
from app.services.reports import ReportService
from app.services.security import SecurityEventService, SecuritySettingService
from app.services.settings import (
    FeatureFlagService,
    PlatformSettingService,
    SystemConfigurationService,
)
from app.services.statistics import StatisticsService
from app.services.tenants import (
    TenantHealthService,
    TenantLimitService,
    TenantService,
    TenantUsageService,
)
from app.services.tenants import TransitionRefusedError as TenantTransitionRefusedError

NOW = datetime(2026, 6, 1, tzinfo=UTC)


async def _make_org(repos, organization_id):
    return await repos.organizations.create(
        Organization(organization_id=organization_id, name="Acme", status=OrganizationStatus.ACTIVE)
    )


class TestOrganizationService:
    async def test_create_and_transition(self, repos, organization_id) -> None:
        service = OrganizationService(repos.organizations)
        org = await service.create_organization(organization_id, name="Acme")
        assert org.status == OrganizationStatus.ACTIVE
        suspended = await service.transition(org, target=OrganizationStatus.SUSPENDED)
        assert suspended.status == OrganizationStatus.SUSPENDED

    async def test_invalid_transition_raises(self, repos, organization_id) -> None:
        service = OrganizationService(repos.organizations)
        org = await service.create_organization(organization_id, name="Acme")
        archived = await service.transition(org, target=OrganizationStatus.ARCHIVED)
        with pytest.raises(OrgTransitionRefusedError):
            await service.transition(archived, target=OrganizationStatus.ACTIVE)


class TestTenantService:
    async def test_provision_publishes_event(self, repos, organization_id, publisher) -> None:
        org = await _make_org(repos, organization_id)
        service = TenantService(repos.tenants, repos.tenant_provisioning, publish=publisher)
        tenant = await service.provision(
            organization_id, organization_ref_id=org.id, name="Tenant A", actor_id="tester", now=NOW
        )
        assert tenant.status == TenantStatus.PROVISIONING
        assert publisher.names() == [TenantCreatedEvent.event_name]

    async def test_transition_to_active_publishes_updated(
        self, repos, organization_id, publisher
    ) -> None:
        org = await _make_org(repos, organization_id)
        service = TenantService(repos.tenants, repos.tenant_provisioning, publish=publisher)
        tenant = await service.provision(
            organization_id, organization_ref_id=org.id, name="Tenant A", actor_id=None, now=NOW
        )
        activated = await service.transition(
            tenant, target=TenantStatus.ACTIVE, actor_id=None, now=NOW
        )
        assert activated.status == TenantStatus.ACTIVE
        assert TenantUpdatedEvent.event_name in publisher.names()

    async def test_transition_to_deleting_publishes_deleted(
        self, repos, organization_id, publisher
    ) -> None:
        org = await _make_org(repos, organization_id)
        service = TenantService(repos.tenants, repos.tenant_provisioning, publish=publisher)
        tenant = await service.provision(
            organization_id, organization_ref_id=org.id, name="Tenant A", actor_id=None, now=NOW
        )
        deleting = await service.transition(
            tenant, target=TenantStatus.DELETING, actor_id=None, now=NOW
        )
        assert deleting.status == TenantStatus.DELETING
        assert TenantDeletedEvent.event_name in publisher.names()

    async def test_invalid_transition_raises(self, repos, organization_id, publisher) -> None:
        org = await _make_org(repos, organization_id)
        service = TenantService(repos.tenants, repos.tenant_provisioning, publish=publisher)
        tenant = await service.provision(
            organization_id, organization_ref_id=org.id, name="Tenant A", actor_id=None, now=NOW
        )
        with pytest.raises(TenantTransitionRefusedError):
            await service.transition(tenant, target=TenantStatus.SUSPENDED, actor_id=None, now=NOW)


class TestTenantLimitService:
    async def test_set_limit_creates_then_updates(self, repos, organization_id) -> None:
        org = await _make_org(repos, organization_id)
        tenant = await TenantService(repos.tenants, repos.tenant_provisioning).provision(
            organization_id, organization_ref_id=org.id, name="T", actor_id=None, now=NOW
        )
        service = TenantLimitService(repos.tenant_limits)
        limit = await service.set_limit(
            organization_id, tenant_id=tenant.id, metric_key="seats", limit_value=10.0
        )
        assert limit.limit_value == 10.0
        updated = await service.set_limit(
            organization_id, tenant_id=tenant.id, metric_key="seats", limit_value=20.0
        )
        assert updated.id == limit.id
        assert updated.limit_value == 20.0
        assert service.classify(updated, used_value=5.0, warning_fraction=0.8) == "ok"


class TestTenantUsageService:
    async def test_record(self, repos, organization_id) -> None:
        org = await _make_org(repos, organization_id)
        tenant = await TenantService(repos.tenants, repos.tenant_provisioning).provision(
            organization_id, organization_ref_id=org.id, name="T", actor_id=None, now=NOW
        )
        service = TenantUsageService(repos.tenant_usage)
        usage = await service.record(
            organization_id, tenant_id=tenant.id, metric_key="seats", used_value=5.0, now=NOW
        )
        assert usage.used_value == 5.0


class TestTenantHealthService:
    async def test_record(self, repos, organization_id) -> None:
        org = await _make_org(repos, organization_id)
        tenant = await TenantService(repos.tenants, repos.tenant_provisioning).provision(
            organization_id, organization_ref_id=org.id, name="T", actor_id=None, now=NOW
        )
        service = TenantHealthService(repos.tenant_health)
        health = await service.record(
            organization_id, tenant_id=tenant.id, status=HealthCheckStatus.HEALTHY, now=NOW
        )
        assert health.status == HealthCheckStatus.HEALTHY


class TestPlatformSettingService:
    async def test_upsert_creates_then_updates(self, repos, organization_id) -> None:
        service = PlatformSettingService(repos.platform_settings)
        setting = await service.upsert(organization_id, key="brand", value={"name": "AI-IOS"})
        updated = await service.upsert(organization_id, key="brand", value={"name": "AI-IOS v2"})
        assert updated.id == setting.id
        assert updated.value == {"name": "AI-IOS v2"}

    async def test_upsert_updates_description_on_existing(self, repos, organization_id) -> None:
        service = PlatformSettingService(repos.platform_settings)
        await service.upsert(
            organization_id, key="brand", value={"name": "AI-IOS"}, description="v1"
        )
        updated = await service.upsert(
            organization_id, key="brand", value={"name": "AI-IOS"}, description="v2"
        )
        assert updated.description == "v2"


class TestSystemConfigurationService:
    async def test_upsert_publishes_event(self, repos, organization_id, publisher) -> None:
        service = SystemConfigurationService(repos.system_configuration, publish=publisher)
        config = await service.upsert(organization_id, key="feature_x", value={"enabled": True})
        assert config.is_validated is True
        assert ConfigurationChangedEvent.event_name in publisher.names()

    async def test_upsert_updates_existing(self, repos, organization_id, publisher) -> None:
        service = SystemConfigurationService(repos.system_configuration, publish=publisher)
        first = await service.upsert(organization_id, key="feature_x", value={"enabled": True})
        second = await service.upsert(
            organization_id, key="feature_x", value={"enabled": False}, environment="staging"
        )
        assert second.id == first.id
        assert second.value == {"enabled": False}
        assert second.environment == "staging"


class TestFeatureFlagService:
    async def test_create_and_update_publishes_event(
        self, repos, organization_id, publisher
    ) -> None:
        service = FeatureFlagService(repos.feature_flags, publish=publisher)
        flag = await service.create_flag(
            organization_id, name="new-ui", scope=FeatureFlagScope.GLOBAL
        )
        assert flag.is_enabled is True
        updated = await service.update_flag(flag, is_killed=True)
        assert updated.is_killed is True
        assert FeatureFlagUpdatedEvent.event_name in publisher.names()

    async def test_update_flag_enabled_and_rollout(self, repos, organization_id, publisher) -> None:
        service = FeatureFlagService(repos.feature_flags, publish=publisher)
        flag = await service.create_flag(
            organization_id, name="new-ui", scope=FeatureFlagScope.GLOBAL
        )
        updated = await service.update_flag(flag, is_enabled=False, rollout_percentage=25.0)
        assert updated.is_enabled is False
        assert updated.rollout_percentage == 25.0


class TestJobService:
    async def test_enqueue_and_transition(self, repos, organization_id) -> None:
        service = JobService(repos.jobs, repos.job_history)
        job = await service.enqueue(
            organization_id,
            job_key="sync",
            priority=JobPriority.NORMAL,
            payload={},
            max_attempts=3,
            now=NOW,
        )
        assert job.status == JobStatus.QUEUED
        running = await service.transition(job, target=JobStatus.RUNNING, now=NOW)
        assert running.status == JobStatus.RUNNING
        assert running.started_at == NOW
        history = await repos.job_history.list_for_job(job.id)
        assert len(history) == 2

    async def test_invalid_transition_raises(self, repos, organization_id) -> None:
        service = JobService(repos.jobs, repos.job_history)
        job = await service.enqueue(
            organization_id,
            job_key="sync",
            priority=JobPriority.NORMAL,
            payload={},
            max_attempts=3,
            now=NOW,
        )
        with pytest.raises(JobTransitionRefusedError):
            await service.transition(job, target=JobStatus.SUCCEEDED, now=NOW)

    async def test_prepare_retry(self, repos, organization_id) -> None:
        service = JobService(repos.jobs, repos.job_history)
        job = await service.enqueue(
            organization_id,
            job_key="sync",
            priority=JobPriority.NORMAL,
            payload={},
            max_attempts=3,
            now=NOW,
        )
        await service.transition(job, target=JobStatus.RUNNING, now=NOW)
        failed = await service.transition(job, target=JobStatus.FAILED, now=NOW)
        decision = await service.prepare_retry(failed, now=NOW)
        assert decision.should_retry
        assert failed.status == JobStatus.RETRYING
        assert failed.attempt_count == 1


class TestMaintenanceService:
    async def test_schedule_notifies(self, repos, organization_id, notifier) -> None:
        service = MaintenanceService(repos.maintenance_windows, notifier=notifier)
        window = await service.schedule(
            organization_id,
            title="Upgrade",
            kind=MaintenanceKind.ROUTINE,
            starts_at=NOW,
            ends_at=NOW + timedelta(hours=2),
        )
        assert window.status == MaintenanceStatus.SCHEDULED
        assert any(name == "notify_maintenance_scheduled" for name, _ in notifier.calls)

    async def test_schedule_conflict_raises(self, repos, organization_id) -> None:
        service = MaintenanceService(repos.maintenance_windows)
        await service.schedule(
            organization_id,
            title="Upgrade 1",
            kind=MaintenanceKind.ROUTINE,
            starts_at=NOW,
            ends_at=NOW + timedelta(hours=2),
        )
        with pytest.raises(MaintenanceConflictError):
            await service.schedule(
                organization_id,
                title="Upgrade 2",
                kind=MaintenanceKind.ROUTINE,
                starts_at=NOW + timedelta(hours=1),
                ends_at=NOW + timedelta(hours=3),
            )

    async def test_transition_to_in_progress_and_completed_publishes_events(
        self, repos, organization_id, publisher
    ) -> None:
        service = MaintenanceService(repos.maintenance_windows, publish=publisher)
        window = await service.schedule(
            organization_id,
            title="Upgrade",
            kind=MaintenanceKind.ROUTINE,
            starts_at=NOW,
            ends_at=NOW + timedelta(hours=2),
        )
        approved = await service.transition(window, target=MaintenanceStatus.APPROVED)
        in_progress = await service.transition(approved, target=MaintenanceStatus.IN_PROGRESS)
        assert MaintenanceStartedEvent.event_name in publisher.names()
        completed = await service.transition(in_progress, target=MaintenanceStatus.COMPLETED)
        assert completed.status == MaintenanceStatus.COMPLETED
        assert MaintenanceCompletedEvent.event_name in publisher.names()

    async def test_invalid_transition_raises(self, repos, organization_id) -> None:
        service = MaintenanceService(repos.maintenance_windows)
        window = await service.schedule(
            organization_id,
            title="Upgrade",
            kind=MaintenanceKind.ROUTINE,
            starts_at=NOW,
            ends_at=NOW + timedelta(hours=2),
        )
        with pytest.raises(MaintenanceTransitionRefusedError):
            await service.transition(window, target=MaintenanceStatus.COMPLETED)

    async def test_approve_sets_approver(self, repos, organization_id) -> None:
        service = MaintenanceService(repos.maintenance_windows)
        window = await service.schedule(
            organization_id,
            title="Upgrade",
            kind=MaintenanceKind.ROUTINE,
            starts_at=NOW,
            ends_at=NOW + timedelta(hours=2),
        )
        approved = await service.approve(window, approved_by="admin-1", now=NOW)
        assert approved.approved_by == "admin-1"
        assert approved.status == MaintenanceStatus.APPROVED


class TestAnnouncementService:
    async def test_publish_and_retract(self, repos, organization_id) -> None:
        service = AnnouncementService(repos.announcements)
        announcement = await service.publish_announcement(
            organization_id, title="Notice", body="Body", scope=AnnouncementScope.GLOBAL
        )
        assert announcement.is_enabled is True
        retracted = await service.retract(announcement)
        assert retracted.is_enabled is False


class TestApiKeyService:
    async def test_issue_rotate_revoke(self, repos, organization_id) -> None:
        service = ApiKeyService(repos.api_keys, repos.api_usage)
        issued = await service.issue(organization_id, name="ci-key")
        assert issued.api_key.status == ApiKeyStatus.ACTIVE
        assert len(issued.raw_key) > 0

        rotated = await service.rotate(issued.api_key, now=NOW)
        assert (
            rotated.api_key.key_hash != issued.api_key.key_hash or rotated.raw_key != issued.raw_key
        )
        assert rotated.api_key.last_rotated_at == NOW

        revoked = await service.revoke(rotated.api_key)
        assert revoked.status == ApiKeyStatus.REVOKED

    async def test_record_usage_is_idempotent_per_window(self, repos, organization_id) -> None:
        service = ApiKeyService(repos.api_keys, repos.api_usage)
        issued = await service.issue(organization_id, name="ci-key")
        window = await service.record_usage(
            organization_id,
            api_key_id=issued.api_key.id,
            window_start=NOW,
            window_end=NOW + timedelta(minutes=1),
        )
        assert window.request_count == 1
        window2 = await service.record_usage(
            organization_id,
            api_key_id=issued.api_key.id,
            window_start=NOW,
            window_end=NOW + timedelta(minutes=1),
        )
        assert window2.id == window.id
        assert window2.request_count == 2


class TestSecuritySettingService:
    async def test_upsert_publishes_event(self, repos, organization_id, publisher) -> None:
        service = SecuritySettingService(repos.security_settings, publish=publisher)
        setting = await service.upsert(
            organization_id, key="password_policy", value={"min_length": 8}
        )
        assert setting.key == "password_policy"
        assert SecurityPolicyUpdatedEvent.event_name in publisher.names()


class TestSecurityEventService:
    async def test_record_notifies(self, repos, organization_id, notifier) -> None:
        service = SecurityEventService(repos.security_events, notifier=notifier)
        event = await service.record(
            organization_id,
            kind=SecurityEventKind.LOGIN_FAILURE,
            severity=SecurityEventSeverity.LOW,
            now=NOW,
        )
        assert event.kind == SecurityEventKind.LOGIN_FAILURE
        assert any(name == "notify_security_event" for name, _ in notifier.calls)


class TestDiagnosticsService:
    async def test_run_diagnostic_and_record_health_check(
        self, repos, organization_id, publisher
    ) -> None:
        service = DiagnosticsService(repos.diagnostics, repos.health_checks, publish=publisher)
        diagnostic = await service.run_diagnostic(
            organization_id,
            category=DiagnosticCategory.DATABASE,
            latency_ms=10.0,
            warning_ms=100.0,
            critical_ms=500.0,
            now=NOW,
        )
        assert diagnostic.status == HealthCheckStatus.HEALTHY

        check = await service.record_health_check(
            organization_id, component="database", status=HealthCheckStatus.HEALTHY, now=NOW
        )
        assert check.status == HealthCheckStatus.HEALTHY
        # The first-ever reading always publishes: there is no prior status,
        # so "no data" -> "healthy" is itself a real crossing.
        assert publisher.names() == [PlatformHealthChangedEvent.event_name]

        repeat = await service.record_health_check(
            organization_id, component="database", status=HealthCheckStatus.HEALTHY, now=NOW
        )
        assert repeat.status == HealthCheckStatus.HEALTHY
        assert publisher.names() == [
            PlatformHealthChangedEvent.event_name
        ]  # unchanged: no new publish

        degraded = await service.record_health_check(
            organization_id, component="database", status=HealthCheckStatus.DEGRADED, now=NOW
        )
        assert degraded.status == HealthCheckStatus.DEGRADED
        assert publisher.names().count(PlatformHealthChangedEvent.event_name) == 2

    async def test_overall_status(self, repos, organization_id) -> None:
        service = DiagnosticsService(repos.diagnostics, repos.health_checks)
        assert await service.overall_status(organization_id) == HealthCheckStatus.UNKNOWN
        await service.record_health_check(
            organization_id, component="database", status=HealthCheckStatus.HEALTHY, now=NOW
        )
        assert await service.overall_status(organization_id) == HealthCheckStatus.HEALTHY


class TestStatisticsService:
    async def test_roll_up_window_is_idempotent(self, repos, organization_id) -> None:
        service = StatisticsService(repos.statistics)
        first = await service.roll_up_window(
            organization_id,
            window_start=NOW,
            window_end=NOW + timedelta(hours=1),
            tenant_count=1,
            user_count=1,
            api_request_count=10,
            background_job_count=2,
            security_event_count=0,
            platform_availability_fraction=1.0,
        )
        second = await service.roll_up_window(
            organization_id,
            window_start=NOW,
            window_end=NOW + timedelta(hours=1),
            tenant_count=2,
            user_count=2,
            api_request_count=20,
            background_job_count=4,
            security_event_count=1,
            platform_availability_fraction=0.9,
        )
        assert second.id == first.id
        assert second.tenant_count == 2


class TestReportService:
    async def test_generate(self, repos, organization_id) -> None:
        from app.models.enums import ReportFormat, ReportKind

        report = await ReportService(repos.reports).generate(
            organization_id,
            kind=ReportKind.PLATFORM,
            title="Platform Report",
            report_format=ReportFormat.JSON,
            period_start=NOW,
            period_end=NOW + timedelta(days=7),
            content={"tenants": 5},
            row_count=1,
            generated_by="tester",
            now=NOW,
        )
        assert report.status.value == "completed"


class TestAdminSessionService:
    async def test_start_session_publishes_event(self, repos, organization_id, publisher) -> None:
        service = AdminSessionService(repos.admin_sessions, publish=publisher)
        session = await service.start_session(
            organization_id, admin_user_id="admin-1", max_age_minutes=60, now=NOW
        )
        assert session.is_enabled is True
        assert AdminLoginEvent.event_name in publisher.names()
        assert service.is_usable(session, now=NOW)
        assert not service.is_usable(session, now=NOW + timedelta(hours=2))

    async def test_force_logout(self, repos, organization_id) -> None:
        service = AdminSessionService(repos.admin_sessions)
        session = await service.start_session(
            organization_id, admin_user_id="admin-1", max_age_minutes=60, now=NOW
        )
        logged_out = await service.force_logout(session)
        assert logged_out.is_enabled is False
        assert not service.is_usable(logged_out, now=NOW)


class TestAdminActionService:
    async def test_log(self, repos, organization_id) -> None:
        entry = await AdminActionService(repos.admin_actions).log(
            organization_id,
            admin_user_id="admin-1",
            action="force_logout",
            target_type="admin_session",
            target_id=None,
            now=NOW,
        )
        assert entry.action == "force_logout"


class TestAuditService:
    async def test_record(self, repos, organization_id) -> None:
        from app.models.enums import AuditAction

        entry = await AuditService(repos.audit).record(
            organization_id,
            action=AuditAction.PLATFORM_ADMINISTRATION,
            entity_type="test",
            entity_id=None,
            occurred_at=NOW,
            summary="test entry",
        )
        assert entry.id is not None
        assert entry.succeeded is True
