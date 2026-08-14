"""FastAPI dependency injection for the multi-cluster management
service.

**The caller's organization comes from their verified token and from
nowhere else.** Accepting it as a query parameter or a body field would
be a cross-tenant read: every repository here scopes on the value it is
handed, so a caller supplying somebody else's organization id would be
served their clusters -- or worse, able to register a credential against
them.
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

from app.config.settings import MultiClusterManagementServiceSettings
from app.services.audit import AuditService
from app.services.bundle import Repositories, build_repositories
from app.services.capacity import CapacityService
from app.services.compliance import ComplianceService
from app.services.credentials import CredentialService
from app.services.federation import FederationService
from app.services.fleet import ClusterGroupService, ClusterRegionService, ClusterService
from app.services.health import HealthService
from app.services.inventory import InventoryService
from app.services.placement import PlacementService
from app.services.policies import PolicyService
from app.services.reports import ReportService
from app.services.statistics import StatisticsService
from app.services.upgrades import UpgradeService
from app.types import EventPublisher

_bearer_scheme = HTTPBearer(auto_error=False)

ADMINISTRATOR_ROLES = frozenset(
    {"admin", "administrator", "platform_admin", "cluster_admin", "fleet_admin"}
)
"""Roles permitted to register/modify/decommission clusters, propagate
policies, and run upgrades. Never across organizations: an
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


def get_service_settings(request: Request) -> MultiClusterManagementServiceSettings:
    return request.app.state.service_settings  # type: ignore[no-any-return]


ServiceSettings = Annotated[MultiClusterManagementServiceSettings, Depends(get_service_settings)]


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
            "The token carries no organization claim, so no fleet scope can be established."
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


def get_group_service(repos: Repos) -> ClusterGroupService:
    return ClusterGroupService(repos.groups)


GroupServiceDep = Annotated[ClusterGroupService, Depends(get_group_service)]


def get_region_service(repos: Repos) -> ClusterRegionService:
    return ClusterRegionService(repos.regions)


RegionServiceDep = Annotated[ClusterRegionService, Depends(get_region_service)]


def get_cluster_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep
) -> ClusterService:
    return ClusterService(repos.clusters, publish=publish, audit=audit)


ClusterServiceDep = Annotated[ClusterService, Depends(get_cluster_service)]


def get_credential_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep
) -> CredentialService:
    return CredentialService(repos.credentials, publish=publish, audit=audit)


CredentialServiceDep = Annotated[CredentialService, Depends(get_credential_service)]


def get_health_service(repos: Repos, publish: EventPublisherDep) -> HealthService:
    return HealthService(repos.health, repos.clusters, publish=publish)


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]


def get_capacity_service(repos: Repos) -> CapacityService:
    return CapacityService(repos.capacity)


CapacityServiceDep = Annotated[CapacityService, Depends(get_capacity_service)]


def get_upgrade_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep
) -> UpgradeService:
    return UpgradeService(
        repos.upgrades, repos.versions, repos.clusters, publish=publish, audit=audit
    )


UpgradeServiceDep = Annotated[UpgradeService, Depends(get_upgrade_service)]


def get_policy_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep
) -> PolicyService:
    return PolicyService(repos.policies, repos.clusters, publish=publish, audit=audit)


PolicyServiceDep = Annotated[PolicyService, Depends(get_policy_service)]


def get_compliance_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep
) -> ComplianceService:
    return ComplianceService(repos.compliance, publish=publish, audit=audit)


ComplianceServiceDep = Annotated[ComplianceService, Depends(get_compliance_service)]


def get_placement_service(repos: Repos) -> PlacementService:
    return PlacementService(repos.workloads)


PlacementServiceDep = Annotated[PlacementService, Depends(get_placement_service)]


def get_federation_service(audit: AuditServiceDep) -> FederationService:
    return FederationService(audit)


FederationServiceDep = Annotated[FederationService, Depends(get_federation_service)]


def get_inventory_service(repos: Repos) -> InventoryService:
    return InventoryService(repos.inventory)


InventoryServiceDep = Annotated[InventoryService, Depends(get_inventory_service)]


def get_statistics_service(repos: Repos) -> StatisticsService:
    return StatisticsService(repos.statistics)


StatisticsServiceDep = Annotated[StatisticsService, Depends(get_statistics_service)]


def get_report_service(repos: Repos) -> ReportService:
    return ReportService(repos.reports)


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]
