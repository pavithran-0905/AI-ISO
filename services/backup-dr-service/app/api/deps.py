"""FastAPI dependency injection for the backup & disaster recovery
service.

**The caller's organization comes from their verified token and from
nowhere else.** Accepting it as a query parameter or a body field would
be a cross-tenant read: every repository here scopes on the value it is
handed, so a caller supplying somebody else's organization id would be
served their backups -- or worse, able to request a restore into them.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from shared_core.database.session import session_scope
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.authentication import AuthenticationError
from shared_core.exceptions.authorization import AuthorizationError
from shared_core.security.jwt import decode_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import BackupDrServiceSettings
from app.services.audit import AuditService
from app.services.backup import BackupJobService, BackupScheduleService, BackupTargetService
from app.services.bundle import Repositories, build_repositories
from app.services.dr import DrPlanService, DrTestService, RecoveryReportService
from app.services.failover import FailoverService
from app.services.immutability import ImmutabilityService
from app.services.replication import ReplicationService
from app.services.reports import ReportService
from app.services.restore import RestoreService
from app.services.retention import RetentionService
from app.services.snapshots import SnapshotService
from app.services.statistics import StatisticsService
from app.services.verification import VerificationService
from app.types import EventPublisher

_bearer_scheme = HTTPBearer(auto_error=False)

ADMINISTRATOR_ROLES = frozenset(
    {"admin", "administrator", "platform_admin", "backup_admin", "dr_admin"}
)
"""Roles permitted to configure schedules, initiate restores/failovers,
and manage retention/immutability. Never across organizations: an
administrator's remit is their tenant."""

_ROLES_CLAIM = "roles"
_ORGANIZATION_CLAIM = "organization_id"


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped database session, committing on success."""
    session_factory = request.app.state.db_session_factory
    async with session_scope(session_factory) as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_event_publisher(request: Request) -> EventPublisher:
    return request.app.state.publish_event  # type: ignore[no-any-return]


EventPublisherDep = Annotated[EventPublisher, Depends(get_event_publisher)]


def get_service_settings(request: Request) -> BackupDrServiceSettings:
    return request.app.state.service_settings  # type: ignore[no-any-return]


ServiceSettings = Annotated[BackupDrServiceSettings, Depends(get_service_settings)]


# ---- authentication -----------------------------------------------------------------


async def get_token_claims(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> dict[str, Any]:
    if credentials is None:
        raise AuthenticationError("Authentication required.")
    public_key = request.app.state.jwt_public_key
    return dict(decode_token(credentials.credentials, public_key=public_key))


TokenClaims = Annotated[dict[str, Any], Depends(get_token_claims)]


async def get_current_user_id(claims: TokenClaims) -> str:
    subject = claims.get("sub")
    if not subject:
        raise AuthenticationError("The token carries no valid subject claim.")
    return str(subject)


CurrentUserId = Annotated[str, Depends(get_current_user_id)]


async def get_organization_id(claims: TokenClaims) -> UUID:
    raw = claims.get(_ORGANIZATION_CLAIM)
    if not raw:
        raise AuthorizationError(
            "The token carries no organization claim, so no backup/DR scope can be established."
        )
    try:
        return UUID(str(raw))
    except ValueError as exc:
        raise AuthorizationError(
            f"The token's organization claim {raw!r} is not a valid identifier."
        ) from exc


OrganizationId = Annotated[UUID, Depends(get_organization_id)]


async def get_roles(claims: TokenClaims) -> frozenset[str]:
    raw = claims.get(_ROLES_CLAIM) or []
    if isinstance(raw, str):
        raw = [raw]
    return frozenset(str(role).strip().lower() for role in raw if str(role).strip())


Roles = Annotated[frozenset[str], Depends(get_roles)]


async def require_administrator(roles: Roles) -> None:
    if not roles & ADMINISTRATOR_ROLES:
        raise AuthorizationError("You do not have permission to perform this action.")


# ---- repositories and services -------------------------------------------------------------


def get_repos(session: DbSession, organization_id: OrganizationId) -> Repositories:
    return build_repositories(session, tenant_scope=TenantScope(organization_id=organization_id))


Repos = Annotated[Repositories, Depends(get_repos)]


def get_audit_service(repos: Repos) -> AuditService:
    return AuditService(repos.audit)


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


def get_target_service(repos: Repos, audit: AuditServiceDep) -> BackupTargetService:
    return BackupTargetService(repos.targets, audit=audit)


TargetServiceDep = Annotated[BackupTargetService, Depends(get_target_service)]


def get_schedule_service(repos: Repos, audit: AuditServiceDep) -> BackupScheduleService:
    return BackupScheduleService(repos.schedules, audit=audit)


ScheduleServiceDep = Annotated[BackupScheduleService, Depends(get_schedule_service)]


def get_job_service(repos: Repos, publish: EventPublisherDep) -> BackupJobService:
    return BackupJobService(repos.jobs, publish=publish)


JobServiceDep = Annotated[BackupJobService, Depends(get_job_service)]


def get_snapshot_service(repos: Repos) -> SnapshotService:
    return SnapshotService(repos.snapshots)


SnapshotServiceDep = Annotated[SnapshotService, Depends(get_snapshot_service)]


def get_restore_service(repos: Repos, publish: EventPublisherDep) -> RestoreService:
    return RestoreService(repos.restore_jobs, repos.restore_points, publish=publish)


RestoreServiceDep = Annotated[RestoreService, Depends(get_restore_service)]


def get_failover_service(repos: Repos, publish: EventPublisherDep) -> FailoverService:
    return FailoverService(repos.failover_events, publish=publish)


FailoverServiceDep = Annotated[FailoverService, Depends(get_failover_service)]


def get_dr_plan_service(repos: Repos) -> DrPlanService:
    return DrPlanService(repos.dr_plans)


DrPlanServiceDep = Annotated[DrPlanService, Depends(get_dr_plan_service)]


def get_dr_test_service(repos: Repos, publish: EventPublisherDep) -> DrTestService:
    return DrTestService(repos.dr_tests, repos.dr_plans, publish=publish)


DrTestServiceDep = Annotated[DrTestService, Depends(get_dr_test_service)]


def get_recovery_report_service(repos: Repos, publish: EventPublisherDep) -> RecoveryReportService:
    return RecoveryReportService(repos.recovery_reports, publish=publish)


RecoveryReportServiceDep = Annotated[RecoveryReportService, Depends(get_recovery_report_service)]


def get_statistics_service(repos: Repos) -> StatisticsService:
    return StatisticsService(repos.statistics)


StatisticsServiceDep = Annotated[StatisticsService, Depends(get_statistics_service)]


def get_report_service(repos: Repos) -> ReportService:
    return ReportService(repos.reports)


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]


def get_retention_service(repos: Repos) -> RetentionService:
    return RetentionService(repos.retention, repos.archives)


RetentionServiceDep = Annotated[RetentionService, Depends(get_retention_service)]


def get_verification_service(repos: Repos) -> VerificationService:
    return VerificationService(repos.verifications)


VerificationServiceDep = Annotated[VerificationService, Depends(get_verification_service)]


def get_replication_service(repos: Repos, settings: ServiceSettings) -> ReplicationService:
    return ReplicationService(
        repos.replication_jobs,
        warning_threshold_seconds=settings.replication_lag_warning_seconds,
        critical_threshold_seconds=settings.replication_lag_critical_seconds,
    )


ReplicationServiceDep = Annotated[ReplicationService, Depends(get_replication_service)]


def get_immutability_service(repos: Repos, audit: AuditServiceDep) -> ImmutabilityService:
    return ImmutabilityService(repos.archives, audit=audit)


ImmutabilityServiceDep = Annotated[ImmutabilityService, Depends(get_immutability_service)]
