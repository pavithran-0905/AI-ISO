"""The platform dashboard: a read-only composite of counts and overall
health, never a write path of its own."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.diagnostics.engine import aggregate_overall_status
from app.models.enums import HealthCheckStatus, JobStatus, TenantStatus
from app.services.bundle import Repositories


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    tenant_count: int
    active_tenant_count: int
    organization_count: int
    running_job_count: int
    failed_job_count: int
    open_maintenance_window_count: int
    overall_health: HealthCheckStatus


class DashboardService:
    """Assembles one point-in-time platform dashboard snapshot."""

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    async def snapshot(self, organization_id: UUID) -> DashboardSnapshot:
        tenants = await self._repos.tenants.list_recent(organization_id, limit=500)
        active_tenants = [t for t in tenants if t.status == TenantStatus.ACTIVE]
        organizations = await self._repos.organizations.list_recent(organization_id, limit=500)
        running_jobs = await self._repos.jobs.list_by_status(
            organization_id, status=JobStatus.RUNNING
        )
        failed_jobs = await self._repos.jobs.list_by_status(
            organization_id, status=JobStatus.FAILED
        )
        open_windows = [
            window
            for window in await self._repos.maintenance_windows.list_recent(
                organization_id, limit=500
            )
            if window.status.value in ("scheduled", "approved", "in_progress")
        ]
        health_checks = await self._repos.health_checks.list_all(organization_id)

        return DashboardSnapshot(
            tenant_count=len(tenants),
            active_tenant_count=len(active_tenants),
            organization_count=len(organizations),
            running_job_count=len(running_jobs),
            failed_job_count=len(failed_jobs),
            open_maintenance_window_count=len(open_windows),
            overall_health=aggregate_overall_status([check.status for check in health_checks]),
        )


__all__ = ["DashboardService", "DashboardSnapshot"]
