"""FastAPI dependency injection for the edge management service.

**The caller's organization comes from their verified token and from
nowhere else.** Accepting it as a query parameter or a body field would
be a cross-tenant read: every repository here scopes on the value it is
handed, so a caller supplying somebody else's organization id would be
served their sites and devices -- or worse, able to register a device
against them.
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

from app.config.settings import EdgeManagementServiceSettings
from app.services.applications import ApplicationService
from app.services.audit import AuditService
from app.services.bundle import Repositories, build_repositories
from app.services.configuration import ConfigurationService
from app.services.devices import EdgeClusterService, EdgeDeviceService, EdgeGatewayService
from app.services.digital_twins import DigitalTwinService
from app.services.edge_ai import EdgeAiModelService
from app.services.firmware import FirmwareService
from app.services.health import HealthService
from app.services.inventory import InventoryService
from app.services.ota import OTAService
from app.services.protocols import ProtocolService
from app.services.reports import ReportService
from app.services.sites import EdgeLocationService, EdgeSiteService
from app.services.statistics import StatisticsService
from app.services.synchronization import SynchronizationService
from app.types import EventPublisher

_bearer_scheme = HTTPBearer(auto_error=False)

ADMINISTRATOR_ROLES = frozenset(
    {"admin", "administrator", "platform_admin", "edge_admin", "device_admin"}
)
"""Roles permitted to register/modify/decommission sites and devices,
run OTA updates, and grant remote access. Never across organizations: an
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


def get_service_settings(request: Request) -> EdgeManagementServiceSettings:
    return request.app.state.service_settings  # type: ignore[no-any-return]


ServiceSettings = Annotated[EdgeManagementServiceSettings, Depends(get_service_settings)]


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


def get_site_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep
) -> EdgeSiteService:
    return EdgeSiteService(repos.sites, publish=publish, audit=audit)


SiteServiceDep = Annotated[EdgeSiteService, Depends(get_site_service)]


def get_location_service(repos: Repos) -> EdgeLocationService:
    return EdgeLocationService(repos.locations)


LocationServiceDep = Annotated[EdgeLocationService, Depends(get_location_service)]


def get_cluster_service(repos: Repos) -> EdgeClusterService:
    return EdgeClusterService(repos.clusters)


ClusterServiceDep = Annotated[EdgeClusterService, Depends(get_cluster_service)]


def get_gateway_service(repos: Repos) -> EdgeGatewayService:
    return EdgeGatewayService(repos.gateways)


GatewayServiceDep = Annotated[EdgeGatewayService, Depends(get_gateway_service)]


def get_device_service(
    repos: Repos, publish: EventPublisherDep, audit: AuditServiceDep
) -> EdgeDeviceService:
    return EdgeDeviceService(repos.devices, publish=publish, audit=audit)


DeviceServiceDep = Annotated[EdgeDeviceService, Depends(get_device_service)]


def get_inventory_service(repos: Repos) -> InventoryService:
    return InventoryService(repos.inventory)


InventoryServiceDep = Annotated[InventoryService, Depends(get_inventory_service)]


def get_health_service(repos: Repos) -> HealthService:
    return HealthService(repos.health, repos.devices)


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]


def get_synchronization_service(repos: Repos, publish: EventPublisherDep) -> SynchronizationService:
    return SynchronizationService(repos.synchronization, publish=publish)


SynchronizationServiceDep = Annotated[SynchronizationService, Depends(get_synchronization_service)]


def get_ota_service(
    repos: Repos, publish: EventPublisherDep, settings: ServiceSettings
) -> OTAService:
    return OTAService(
        repos.updates,
        repos.firmware,
        publish=publish,
        max_skew=settings.max_supported_firmware_skew,
    )


OTAServiceDep = Annotated[OTAService, Depends(get_ota_service)]


def get_firmware_service(repos: Repos) -> FirmwareService:
    return FirmwareService(repos.firmware)


FirmwareServiceDep = Annotated[FirmwareService, Depends(get_firmware_service)]


def get_application_service(repos: Repos) -> ApplicationService:
    return ApplicationService(repos.applications)


ApplicationServiceDep = Annotated[ApplicationService, Depends(get_application_service)]


def get_edge_ai_service(repos: Repos, publish: EventPublisherDep) -> EdgeAiModelService:
    return EdgeAiModelService(repos.ai_models, publish=publish)


EdgeAiServiceDep = Annotated[EdgeAiModelService, Depends(get_edge_ai_service)]


def get_protocol_service(repos: Repos) -> ProtocolService:
    return ProtocolService(repos.protocols)


ProtocolServiceDep = Annotated[ProtocolService, Depends(get_protocol_service)]


def get_digital_twin_service() -> DigitalTwinService:
    return DigitalTwinService()


DigitalTwinServiceDep = Annotated[DigitalTwinService, Depends(get_digital_twin_service)]


def get_configuration_service(repos: Repos) -> ConfigurationService:
    return ConfigurationService(repos.configuration)


ConfigurationServiceDep = Annotated[ConfigurationService, Depends(get_configuration_service)]


def get_statistics_service(repos: Repos) -> StatisticsService:
    return StatisticsService(repos.statistics)


StatisticsServiceDep = Annotated[StatisticsService, Depends(get_statistics_service)]


def get_report_service(repos: Repos) -> ReportService:
    return ReportService(repos.reports)


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]
