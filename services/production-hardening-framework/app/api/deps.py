"""FastAPI dependency injection for the Production Hardening Framework.

**Every route requires an administrator role.** Hardening execution,
security findings, vulnerabilities, and certification decisions are
internal engineering signals, not customer-facing data -- the same
administrator-heavy routing every adjacent infrastructure-framework
service in this build (075-078) established.

**The caller's organization comes from their verified token and from
nowhere else** -- the same tenant-isolation discipline every AI-IOS
service in this build follows.
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

from app.config.settings import ProductionHardeningFrameworkSettings
from app.services.audit import AuditService
from app.services.bundle import Repositories, build_repositories
from app.services.certification import ProductionCertificationService
from app.services.hardening_definitions import HardeningProfileService
from app.services.hardening_execution import HardeningRunService
from app.services.notifications import HardeningNotifier
from app.types import EventPublisher

_bearer_scheme = HTTPBearer(auto_error=False)

ADMINISTRATOR_ROLES = frozenset({"admin", "administrator", "platform_admin", "hardening_admin"})
"""Roles permitted to operate this service at all -- every route
requires one of these; there is no lower-privilege caller shape."""

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


def get_notifier(request: Request) -> HardeningNotifier:
    return request.app.state.notifier  # type: ignore[no-any-return]


NotifierDep = Annotated[HardeningNotifier, Depends(get_notifier)]


def get_service_settings(request: Request) -> ProductionHardeningFrameworkSettings:
    return request.app.state.service_settings  # type: ignore[no-any-return]


ServiceSettings = Annotated[ProductionHardeningFrameworkSettings, Depends(get_service_settings)]


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


def get_hardening_profile_service(repos: Repos) -> HardeningProfileService:
    return HardeningProfileService(repos.hardening_profiles)


HardeningProfileServiceDep = Annotated[
    HardeningProfileService, Depends(get_hardening_profile_service)
]


def get_hardening_run_service(
    repos: Repos, publish: EventPublisherDep, notifier: NotifierDep
) -> HardeningRunService:
    return HardeningRunService(repos.hardening_runs, publish=publish, notifier=notifier)


HardeningRunServiceDep = Annotated[HardeningRunService, Depends(get_hardening_run_service)]


def get_production_certification_service(
    repos: Repos, publish: EventPublisherDep, notifier: NotifierDep
) -> ProductionCertificationService:
    return ProductionCertificationService(
        repos.production_certifications, publish=publish, notifier=notifier
    )


ProductionCertificationServiceDep = Annotated[
    ProductionCertificationService, Depends(get_production_certification_service)
]


__all__ = [
    "ADMINISTRATOR_ROLES",
    "AuditServiceDep",
    "CurrentUserId",
    "DbSession",
    "EventPublisherDep",
    "HardeningProfileServiceDep",
    "HardeningRunServiceDep",
    "NotifierDep",
    "OrganizationId",
    "ProductionCertificationServiceDep",
    "Repos",
    "Roles",
    "ServiceSettings",
    "TokenClaims",
    "get_audit_service",
    "get_current_user_id",
    "get_db_session",
    "get_event_publisher",
    "get_hardening_profile_service",
    "get_hardening_run_service",
    "get_notifier",
    "get_organization_id",
    "get_production_certification_service",
    "get_repos",
    "get_roles",
    "get_service_settings",
    "get_token_claims",
    "require_administrator",
]
