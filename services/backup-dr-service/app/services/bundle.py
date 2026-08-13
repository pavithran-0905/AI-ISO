"""The repository bundle every route works through.

One object rather than seventeen constructor arguments, all sharing one
tenant scope: a bundle where one repository was built without it would
enforce tenant isolation everywhere except the one query that forgot,
and that query is the leak.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.backup import (
    BackupArchiveRepository,
    BackupJobRepository,
    BackupRetentionRepository,
    BackupScheduleRepository,
    BackupSnapshotRepository,
    BackupTargetRepository,
    BackupVerificationRepository,
)
from app.repositories.operations import (
    BackupAuditRepository,
    BackupReportRepository,
    BackupStatisticRepository,
)
from app.repositories.recovery import (
    DrPlanRepository,
    DrTestRepository,
    FailoverEventRepository,
    RecoveryReportRepository,
    ReplicationJobRepository,
    RestoreJobRepository,
    RestorePointRepository,
)


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    targets: BackupTargetRepository
    schedules: BackupScheduleRepository
    jobs: BackupJobRepository
    snapshots: BackupSnapshotRepository
    archives: BackupArchiveRepository
    retention: BackupRetentionRepository
    verifications: BackupVerificationRepository

    restore_points: RestorePointRepository
    restore_jobs: RestoreJobRepository
    replication_jobs: ReplicationJobRepository
    dr_plans: DrPlanRepository
    dr_tests: DrTestRepository
    failover_events: FailoverEventRepository
    recovery_reports: RecoveryReportRepository

    statistics: BackupStatisticRepository
    reports: BackupReportRepository
    audit: BackupAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        targets=BackupTargetRepository(session, tenant_scope=tenant_scope),
        schedules=BackupScheduleRepository(session, tenant_scope=tenant_scope),
        jobs=BackupJobRepository(session, tenant_scope=tenant_scope),
        snapshots=BackupSnapshotRepository(session, tenant_scope=tenant_scope),
        archives=BackupArchiveRepository(session, tenant_scope=tenant_scope),
        retention=BackupRetentionRepository(session, tenant_scope=tenant_scope),
        verifications=BackupVerificationRepository(session, tenant_scope=tenant_scope),
        restore_points=RestorePointRepository(session, tenant_scope=tenant_scope),
        restore_jobs=RestoreJobRepository(session, tenant_scope=tenant_scope),
        replication_jobs=ReplicationJobRepository(session, tenant_scope=tenant_scope),
        dr_plans=DrPlanRepository(session, tenant_scope=tenant_scope),
        dr_tests=DrTestRepository(session, tenant_scope=tenant_scope),
        failover_events=FailoverEventRepository(session, tenant_scope=tenant_scope),
        recovery_reports=RecoveryReportRepository(session, tenant_scope=tenant_scope),
        statistics=BackupStatisticRepository(session, tenant_scope=tenant_scope),
        reports=BackupReportRepository(session, tenant_scope=tenant_scope),
        audit=BackupAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
