"""FastAPI dependency injection for the Public API & Developer Platform.

**The caller's organization comes from their verified token and from
nowhere else.** Accepting it as a query or body parameter would be a
cross-tenant read: every repository here scopes on the value it is
handed, so a caller supplying somebody else's organization id would be
served (or could register against) another tenant's developer
ecosystem.

**A developer-facing caller is identified by email, not a platform
user id.** This service's own bearer token is the same
authentication-service-issued JWT every AI-IOS service verifies, but
for a public developer portal login flow the token's ``sub`` claim
carries the developer's own email address -- the identifier
``developer_accounts.email`` is actually keyed on.
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
from shared_core.exceptions.not_found import NotFoundError
from shared_core.security.jwt import decode_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import PublicApiPlatformSettings
from app.models.developers import DeveloperAccount
from app.services.applications import ApplicationService
from app.services.audit import AuditService
from app.services.bundle import Repositories, build_repositories
from app.services.credentials import ApiKeyService, OAuthClientService
from app.services.developers import DeveloperAccountService
from app.services.notifications import DeveloperNotifier
from app.services.products import ApiPlanService, ApiProductService, ApiSubscriptionService
from app.services.statistics import StatisticsService
from app.types import EventPublisher

_bearer_scheme = HTTPBearer(auto_error=False)

ADMINISTRATOR_ROLES = frozenset({"admin", "administrator", "platform_admin", "api_platform_admin"})
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


def get_notifier(request: Request) -> DeveloperNotifier:
    return request.app.state.notifier  # type: ignore[no-any-return]


NotifierDep = Annotated[DeveloperNotifier, Depends(get_notifier)]


def get_service_settings(request: Request) -> PublicApiPlatformSettings:
    return request.app.state.service_settings  # type: ignore[no-any-return]


ServiceSettings = Annotated[PublicApiPlatformSettings, Depends(get_service_settings)]


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


async def get_current_developer_email(claims: TokenClaims) -> str:
    subject = claims.get("sub")
    if not subject:
        raise AuthenticationError("The token carries no valid subject claim.")
    return str(subject)


CurrentDeveloperEmail = Annotated[str, Depends(get_current_developer_email)]


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


async def get_current_developer(
    repos: Repos, organization_id: OrganizationId, email: CurrentDeveloperEmail
) -> DeveloperAccount:
    account = await repos.developer_accounts.find_by_email(organization_id, email=email)
    if account is None:
        raise NotFoundError(f"No developer account is registered for {email!r}.")
    return account


CurrentDeveloper = Annotated[DeveloperAccount, Depends(get_current_developer)]


def get_audit_service(repos: Repos) -> AuditService:
    return AuditService(repos.audit)


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


def get_developer_account_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep, notifier: NotifierDep
) -> DeveloperAccountService:
    return DeveloperAccountService(
        repos.developer_accounts, publish=publish, audit=audit, notifier=notifier
    )


DeveloperAccountServiceDep = Annotated[
    DeveloperAccountService, Depends(get_developer_account_service)
]


def get_application_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep, notifier: NotifierDep
) -> ApplicationService:
    return ApplicationService(repos.applications, publish=publish, audit=audit, notifier=notifier)


ApplicationServiceDep = Annotated[ApplicationService, Depends(get_application_service)]


def get_api_key_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep
) -> ApiKeyService:
    return ApiKeyService(repos.api_keys, publish=publish, audit=audit)


ApiKeyServiceDep = Annotated[ApiKeyService, Depends(get_api_key_service)]


def get_oauth_client_service(repos: Repos, publish: EventPublisherDep) -> OAuthClientService:
    return OAuthClientService(repos.oauth_clients, publish=publish)


OAuthClientServiceDep = Annotated[OAuthClientService, Depends(get_oauth_client_service)]


def get_api_product_service(repos: Repos, audit: AuditServiceDep) -> ApiProductService:
    return ApiProductService(repos.api_products, audit=audit)


ApiProductServiceDep = Annotated[ApiProductService, Depends(get_api_product_service)]


def get_api_plan_service(repos: Repos) -> ApiPlanService:
    return ApiPlanService(repos.api_plans)


ApiPlanServiceDep = Annotated[ApiPlanService, Depends(get_api_plan_service)]


def get_api_subscription_service(
    repos: Repos, publish: EventPublisherDep
) -> ApiSubscriptionService:
    return ApiSubscriptionService(repos.api_subscriptions, publish=publish)


ApiSubscriptionServiceDep = Annotated[ApiSubscriptionService, Depends(get_api_subscription_service)]


def get_statistics_service(repos: Repos) -> StatisticsService:
    return StatisticsService(repos.statistics)


StatisticsServiceDep = Annotated[StatisticsService, Depends(get_statistics_service)]


__all__ = [
    "ADMINISTRATOR_ROLES",
    "ApiKeyServiceDep",
    "ApiPlanServiceDep",
    "ApiProductServiceDep",
    "ApiSubscriptionServiceDep",
    "ApplicationServiceDep",
    "AuditServiceDep",
    "CurrentDeveloper",
    "CurrentDeveloperEmail",
    "DbSession",
    "DeveloperAccountServiceDep",
    "EventPublisherDep",
    "NotifierDep",
    "OAuthClientServiceDep",
    "OrganizationId",
    "Repos",
    "Roles",
    "ServiceSettings",
    "StatisticsServiceDep",
    "TokenClaims",
    "get_api_key_service",
    "get_api_plan_service",
    "get_api_product_service",
    "get_api_subscription_service",
    "get_application_service",
    "get_audit_service",
    "get_current_developer",
    "get_current_developer_email",
    "get_db_session",
    "get_developer_account_service",
    "get_event_publisher",
    "get_notifier",
    "get_oauth_client_service",
    "get_organization_id",
    "get_roles",
    "get_service_settings",
    "get_statistics_service",
    "get_token_claims",
    "require_administrator",
]
