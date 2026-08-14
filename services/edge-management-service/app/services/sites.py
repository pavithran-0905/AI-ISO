"""Site and location registration.

Publishes ``EdgeSiteRegistered`` on site registration; location creation
records only an audit entry, since docs/067 names no dedicated event for
it.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import EdgeSiteRegisteredEvent
from app.models.enums import AuditAction, SiteHierarchyLevel
from app.models.sites import EdgeLocation, EdgeSite
from app.repositories.sites import EdgeLocationRepository, EdgeSiteRepository
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "edge-management-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class EdgeSiteService:
    def __init__(
        self,
        repo: EdgeSiteRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit

    async def register_site(
        self,
        organization_id: UUID,
        *,
        name: str,
        business_unit: str | None,
        description: str | None,
        geo_latitude: float | None,
        geo_longitude: float | None,
        actor_id: str | None,
        now: datetime,
    ) -> EdgeSite:
        site = await self._repo.create(
            EdgeSite(
                organization_id=organization_id,
                name=name,
                business_unit=business_unit,
                description=description,
                geo_latitude=geo_latitude,
                geo_longitude=geo_longitude,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.SITE_REGISTERED,
                entity_type="edge_site",
                entity_id=site.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Registered edge site {name!r}.",
            )
        await self._publish(
            EdgeSiteRegisteredEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"site_id": str(site.id), "name": name, "business_unit": business_unit},
            )
        )
        return site


class EdgeLocationService:
    def __init__(self, repo: EdgeLocationRepository) -> None:
        self._repo = repo

    async def create_location(
        self,
        organization_id: UUID,
        *,
        site_id: UUID,
        parent_location_id: UUID | None,
        name: str,
        hierarchy_level: SiteHierarchyLevel,
    ) -> EdgeLocation:
        return await self._repo.create(
            EdgeLocation(
                organization_id=organization_id,
                site_id=site_id,
                parent_location_id=parent_location_id,
                name=name,
                hierarchy_level=hierarchy_level,
            )
        )


__all__ = ["EdgeLocationService", "EdgeSiteService"]
