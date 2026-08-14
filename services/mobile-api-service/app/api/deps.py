"""FastAPI dependency injection for the Mobile API service.

**The caller's organization comes from their verified token and from
nowhere else.** Accepting it as a query or body parameter would be a
cross-tenant read: every repository here scopes on the value it is
handed, so a caller supplying somebody else's organization id would be
served (or could register against) another tenant's devices.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from shared_core.cache.manager import CacheManager
from shared_core.database.session import session_scope
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.authentication import AuthenticationError
from shared_core.exceptions.authorization import AuthorizationError
from shared_core.security.jwt import decode_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import MobileApiServiceSettings
from app.services.audit import AuditService
from app.services.bundle import Repositories, build_repositories
from app.services.configuration import ConfigurationService
from app.services.devices import DeviceService
from app.services.notifications import MobileNotifier
from app.services.profiles import ProfileService
from app.services.push import PushService
from app.services.qr import QrService
from app.services.reports import ReportService
from app.services.sessions import SessionService
from app.services.statistics import StatisticsService
from app.services.sync import SyncService
from app.services.tokens import MobileTokenService
from app.services.versions import AppVersionService
from app.types import EventPublisher

_bearer_scheme = HTTPBearer(auto_error=False)

ADMINISTRATOR_ROLES = frozenset({"admin", "administrator", "platform_admin", "mobile_admin"})
"""Roles permitted to view fleet-wide statistics and reports. Never
across organizations: an administrator's remit is their own tenant."""

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


def get_notifier(request: Request) -> MobileNotifier:
    return request.app.state.notifier  # type: ignore[no-any-return]


NotifierDep = Annotated[MobileNotifier, Depends(get_notifier)]


def get_cache_manager(request: Request) -> CacheManager:
    return request.app.state.cache_manager  # type: ignore[no-any-return]


CacheManagerDep = Annotated[CacheManager, Depends(get_cache_manager)]


def get_service_settings(request: Request) -> MobileApiServiceSettings:
    return request.app.state.service_settings  # type: ignore[no-any-return]


ServiceSettings = Annotated[MobileApiServiceSettings, Depends(get_service_settings)]


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


def get_audit_service(repos: Repos) -> AuditService:
    return AuditService(repos.audit)


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


def get_device_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep, notifier: NotifierDep
) -> DeviceService:
    return DeviceService(repos.devices, publish=publish, audit=audit, notifier=notifier)


DeviceServiceDep = Annotated[DeviceService, Depends(get_device_service)]


def get_session_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep, notifier: NotifierDep
) -> SessionService:
    return SessionService(repos.sessions, publish=publish, audit=audit, notifier=notifier)


SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]


def get_token_service(repos: Repos) -> MobileTokenService:
    return MobileTokenService(repos.tokens)


TokenServiceDep = Annotated[MobileTokenService, Depends(get_token_service)]


def get_profile_service(repos: Repos) -> ProfileService:
    return ProfileService(repos.profiles)


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]


def get_sync_service(repos: Repos, publish: EventPublisherDep) -> SyncService:
    return SyncService(repos.sync_jobs, repos.sync_queue, publish=publish)


SyncServiceDep = Annotated[SyncService, Depends(get_sync_service)]


def get_push_service(repos: Repos, publish: EventPublisherDep) -> PushService:
    return PushService(repos.push_tokens, repos.notifications, publish=publish)


PushServiceDep = Annotated[PushService, Depends(get_push_service)]


def get_qr_service(cache: CacheManagerDep) -> QrService:
    return QrService(cache)


QrServiceDep = Annotated[QrService, Depends(get_qr_service)]


def get_app_version_service(repos: Repos, publish: EventPublisherDep) -> AppVersionService:
    return AppVersionService(repos.app_versions, publish=publish)


AppVersionServiceDep = Annotated[AppVersionService, Depends(get_app_version_service)]


def get_configuration_service(repos: Repos) -> ConfigurationService:
    return ConfigurationService(repos.configuration)


ConfigurationServiceDep = Annotated[ConfigurationService, Depends(get_configuration_service)]


def get_statistics_service(repos: Repos) -> StatisticsService:
    return StatisticsService(repos.analytics, repos.telemetry)


StatisticsServiceDep = Annotated[StatisticsService, Depends(get_statistics_service)]


def get_report_service(repos: Repos) -> ReportService:
    return ReportService(repos.reports)


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]


__all__ = [
    "ADMINISTRATOR_ROLES",
    "AppVersionServiceDep",
    "AuditServiceDep",
    "CacheManagerDep",
    "ConfigurationServiceDep",
    "CurrentUserId",
    "DbSession",
    "DeviceServiceDep",
    "EventPublisherDep",
    "NotifierDep",
    "OrganizationId",
    "ProfileServiceDep",
    "PushServiceDep",
    "QrServiceDep",
    "ReportServiceDep",
    "Repos",
    "Roles",
    "ServiceSettings",
    "SessionServiceDep",
    "StatisticsServiceDep",
    "SyncServiceDep",
    "TokenClaims",
    "TokenServiceDep",
    "get_app_version_service",
    "get_audit_service",
    "get_cache_manager",
    "get_configuration_service",
    "get_current_user_id",
    "get_db_session",
    "get_device_service",
    "get_event_publisher",
    "get_notifier",
    "get_organization_id",
    "get_profile_service",
    "get_push_service",
    "get_qr_service",
    "get_report_service",
    "get_repos",
    "get_roles",
    "get_service_settings",
    "get_session_service",
    "get_statistics_service",
    "get_sync_service",
    "get_token_claims",
    "get_token_service",
    "require_administrator",
]
