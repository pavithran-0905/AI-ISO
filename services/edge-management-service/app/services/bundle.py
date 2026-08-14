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

from app.repositories.devices import (
    EdgeClusterRepository,
    EdgeDeviceRepository,
    EdgeGatewayRepository,
    EdgeInventoryRepository,
)
from app.repositories.operations import (
    EdgeAiModelRepository,
    EdgeApplicationRepository,
    EdgeConfigurationRepository,
    EdgeFirmwareRepository,
    EdgeHealthRepository,
    EdgeProtocolRepository,
    EdgeSynchronizationRepository,
    EdgeUpdateRepository,
)
from app.repositories.reporting import (
    EdgeAuditRepository,
    EdgeReportRepository,
    EdgeStatisticRepository,
)
from app.repositories.sites import EdgeLocationRepository, EdgeSiteRepository


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    sites: EdgeSiteRepository
    locations: EdgeLocationRepository

    clusters: EdgeClusterRepository
    gateways: EdgeGatewayRepository
    devices: EdgeDeviceRepository
    inventory: EdgeInventoryRepository

    configuration: EdgeConfigurationRepository
    synchronization: EdgeSynchronizationRepository
    updates: EdgeUpdateRepository
    firmware: EdgeFirmwareRepository
    applications: EdgeApplicationRepository
    ai_models: EdgeAiModelRepository
    protocols: EdgeProtocolRepository
    health: EdgeHealthRepository

    statistics: EdgeStatisticRepository
    reports: EdgeReportRepository
    audit: EdgeAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        sites=EdgeSiteRepository(session, tenant_scope=tenant_scope),
        locations=EdgeLocationRepository(session, tenant_scope=tenant_scope),
        clusters=EdgeClusterRepository(session, tenant_scope=tenant_scope),
        gateways=EdgeGatewayRepository(session, tenant_scope=tenant_scope),
        devices=EdgeDeviceRepository(session, tenant_scope=tenant_scope),
        inventory=EdgeInventoryRepository(session, tenant_scope=tenant_scope),
        configuration=EdgeConfigurationRepository(session, tenant_scope=tenant_scope),
        synchronization=EdgeSynchronizationRepository(session, tenant_scope=tenant_scope),
        updates=EdgeUpdateRepository(session, tenant_scope=tenant_scope),
        firmware=EdgeFirmwareRepository(session, tenant_scope=tenant_scope),
        applications=EdgeApplicationRepository(session, tenant_scope=tenant_scope),
        ai_models=EdgeAiModelRepository(session, tenant_scope=tenant_scope),
        protocols=EdgeProtocolRepository(session, tenant_scope=tenant_scope),
        health=EdgeHealthRepository(session, tenant_scope=tenant_scope),
        statistics=EdgeStatisticRepository(session, tenant_scope=tenant_scope),
        reports=EdgeReportRepository(session, tenant_scope=tenant_scope),
        audit=EdgeAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
