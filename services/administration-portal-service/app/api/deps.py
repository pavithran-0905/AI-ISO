"""FastAPI dependency injection for the administration portal service.

**The caller's organization comes from their verified token and from
nowhere else.** Accepting it as a query or body parameter would be a
cross-tenant read: every repository here scopes on the value it is
handed, so a caller supplying somebody else's organization id would be
served their tenants and settings -- or worse, able to provision a
tenant against them.
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

from app.config.settings import AdministrationPortalServiceSettings
from app.services.bundle import Repositories, build_repositories
from app.services.dashboard import DashboardService
from app.services.diagnostics import DiagnosticsService
from app.services.jobs import JobService
from app.services.reports import ReportService
from app.services.settings import FeatureFlagService, PlatformSettingService
from app.services.statistics import StatisticsService
from app.services.tenants import TenantService
from app.types import EventPublisher

_bearer_scheme = HTTPBearer(auto_error=False)

ADMINISTRATOR_ROLES = frozenset({"admin", "administrator", "platform_admin", "super_admin"})
"""Roles permitted to provision tenants, change settings, and manage
feature flags/jobs. Never across organizations: an administrator's
remit is their own tenant."""

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


def get_service_settings(request: Request) -> AdministrationPortalServiceSettings:
    return request.app.state.service_settings  # type: ignore[no-any-return]


ServiceSettings = Annotated[AdministrationPortalServiceSettings, Depends(get_service_settings)]


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
            "The token carries no organization claim, so no tenant scope can be established."
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


def get_dashboard_service(repos: Repos) -> DashboardService:
    return DashboardService(repos)


DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]


def get_platform_setting_service(repos: Repos) -> PlatformSettingService:
    return PlatformSettingService(repos.platform_settings)


PlatformSettingServiceDep = Annotated[PlatformSettingService, Depends(get_platform_setting_service)]


def get_tenant_service(repos: Repos, publish: EventPublisherDep) -> TenantService:
    return TenantService(repos.tenants, repos.tenant_provisioning, publish=publish)


TenantServiceDep = Annotated[TenantService, Depends(get_tenant_service)]


def get_feature_flag_service(repos: Repos, publish: EventPublisherDep) -> FeatureFlagService:
    return FeatureFlagService(repos.feature_flags, publish=publish)


FeatureFlagServiceDep = Annotated[FeatureFlagService, Depends(get_feature_flag_service)]


def get_job_service(repos: Repos) -> JobService:
    return JobService(repos.jobs, repos.job_history)


JobServiceDep = Annotated[JobService, Depends(get_job_service)]


def get_diagnostics_service(repos: Repos, publish: EventPublisherDep) -> DiagnosticsService:
    return DiagnosticsService(repos.diagnostics, repos.health_checks, publish=publish)


DiagnosticsServiceDep = Annotated[DiagnosticsService, Depends(get_diagnostics_service)]


def get_statistics_service(repos: Repos) -> StatisticsService:
    return StatisticsService(repos.statistics)


StatisticsServiceDep = Annotated[StatisticsService, Depends(get_statistics_service)]


def get_report_service(repos: Repos) -> ReportService:
    return ReportService(repos.reports)


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]
