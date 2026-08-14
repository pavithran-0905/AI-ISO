"""FastAPI dependency injection for the cloud management service.

**The caller's organization comes from their verified token and from
nowhere else.** Accepting it as a query parameter or a body field would
be a cross-tenant read: every repository here scopes on the value it is
handed, so a caller supplying somebody else's organization id would be
served their accounts and resources -- or worse, able to register an
account against them.
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

from app.config.settings import CloudManagementServiceSettings
from app.services.accounts import CloudAccountService
from app.services.audit import AuditService
from app.services.bundle import Repositories, build_repositories
from app.services.catalog import CloudCatalogService
from app.services.compliance import CloudComplianceService
from app.services.drift import CloudDriftService
from app.services.finops import CloudBudgetService, CloudCostService
from app.services.governance import CloudPolicyService
from app.services.iac import CloudIaCService
from app.services.providers import CloudProjectService, CloudProviderService, CloudRegionService
from app.services.reports import ReportService
from app.services.resource_details import (
    ComputeService,
    DatabaseService,
    KubernetesService,
    NetworkService,
    StorageService,
)
from app.services.resources import CloudResourceService
from app.services.statistics import StatisticsService
from app.types import EventPublisher

_bearer_scheme = HTTPBearer(auto_error=False)

ADMINISTRATOR_ROLES = frozenset(
    {"admin", "administrator", "platform_admin", "cloud_admin", "finops_admin"}
)
"""Roles permitted to register/modify accounts and resources, manage
budgets and policies, and approve catalog items. Never across
organizations: an administrator's remit is their tenant."""

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


def get_service_settings(request: Request) -> CloudManagementServiceSettings:
    return request.app.state.service_settings  # type: ignore[no-any-return]


ServiceSettings = Annotated[CloudManagementServiceSettings, Depends(get_service_settings)]


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


def get_provider_service(repos: Repos) -> CloudProviderService:
    return CloudProviderService(repos.providers)


ProviderServiceDep = Annotated[CloudProviderService, Depends(get_provider_service)]


def get_region_service(repos: Repos) -> CloudRegionService:
    return CloudRegionService(repos.regions)


RegionServiceDep = Annotated[CloudRegionService, Depends(get_region_service)]


def get_project_service(repos: Repos) -> CloudProjectService:
    return CloudProjectService(repos.projects)


ProjectServiceDep = Annotated[CloudProjectService, Depends(get_project_service)]


def get_account_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep
) -> CloudAccountService:
    return CloudAccountService(repos.accounts, publish=publish, audit=audit)


AccountServiceDep = Annotated[CloudAccountService, Depends(get_account_service)]


def get_resource_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep
) -> CloudResourceService:
    return CloudResourceService(repos.resources, publish=publish, audit=audit)


ResourceServiceDep = Annotated[CloudResourceService, Depends(get_resource_service)]


def get_compute_service(repos: Repos) -> ComputeService:
    return ComputeService(repos.compute)


ComputeServiceDep = Annotated[ComputeService, Depends(get_compute_service)]


def get_storage_service(repos: Repos) -> StorageService:
    return StorageService(repos.storage)


StorageServiceDep = Annotated[StorageService, Depends(get_storage_service)]


def get_network_service(repos: Repos) -> NetworkService:
    return NetworkService(repos.networks)


NetworkServiceDep = Annotated[NetworkService, Depends(get_network_service)]


def get_database_service(repos: Repos) -> DatabaseService:
    return DatabaseService(repos.databases)


DatabaseServiceDep = Annotated[DatabaseService, Depends(get_database_service)]


def get_kubernetes_service(repos: Repos) -> KubernetesService:
    return KubernetesService(repos.kubernetes)


KubernetesServiceDep = Annotated[KubernetesService, Depends(get_kubernetes_service)]


def get_cost_service(repos: Repos, audit: AuditServiceDep) -> CloudCostService:
    return CloudCostService(repos.costs, audit=audit)


CostServiceDep = Annotated[CloudCostService, Depends(get_cost_service)]


def get_budget_service(repos: Repos, publish: EventPublisherDep) -> CloudBudgetService:
    return CloudBudgetService(repos.budgets, publish=publish)


BudgetServiceDep = Annotated[CloudBudgetService, Depends(get_budget_service)]


def get_policy_service(repos: Repos, audit: AuditServiceDep) -> CloudPolicyService:
    return CloudPolicyService(repos.policies, audit=audit)


PolicyServiceDep = Annotated[CloudPolicyService, Depends(get_policy_service)]


def get_compliance_service(repos: Repos, audit: AuditServiceDep) -> CloudComplianceService:
    return CloudComplianceService(repos.compliance, audit=audit)


ComplianceServiceDep = Annotated[CloudComplianceService, Depends(get_compliance_service)]


def get_drift_service(repos: Repos, publish: EventPublisherDep) -> CloudDriftService:
    return CloudDriftService(repos.drift, publish=publish)


DriftServiceDep = Annotated[CloudDriftService, Depends(get_drift_service)]


def get_iac_service(repos: Repos, audit: AuditServiceDep) -> CloudIaCService:
    return CloudIaCService(repos.iac, audit=audit)


IaCServiceDep = Annotated[CloudIaCService, Depends(get_iac_service)]


def get_catalog_service(repos: Repos) -> CloudCatalogService:
    return CloudCatalogService(repos.catalog)


CatalogServiceDep = Annotated[CloudCatalogService, Depends(get_catalog_service)]


def get_statistics_service(repos: Repos) -> StatisticsService:
    return StatisticsService(repos.statistics)


StatisticsServiceDep = Annotated[StatisticsService, Depends(get_statistics_service)]


def get_report_service(repos: Repos) -> ReportService:
    return ReportService(repos.reports)


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]
