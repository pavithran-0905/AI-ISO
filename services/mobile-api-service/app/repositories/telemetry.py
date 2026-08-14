"""Repositories for raw telemetry and analytics events."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telemetry import MobileAnalyticsEvent, MobileTelemetryEvent

MAX_PAGE_SIZE = 5_000


class MobileTelemetryEventRepository(BaseRepository[MobileTelemetryEvent]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MobileTelemetryEvent, tenant_scope=tenant_scope)

    async def list_since(
        self, organization_id: UUID, *, since: datetime, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[MobileTelemetryEvent]:
        stmt = (
            self._base_select()
            .where(
                MobileTelemetryEvent.organization_id == organization_id,
                MobileTelemetryEvent.recorded_at >= since,
            )
            .order_by(MobileTelemetryEvent.recorded_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_device(
        self, organization_id: UUID, *, device_id: UUID, limit: int = 100
    ) -> Sequence[MobileTelemetryEvent]:
        stmt = (
            self._base_select()
            .where(
                MobileTelemetryEvent.organization_id == organization_id,
                MobileTelemetryEvent.device_id == device_id,
            )
            .order_by(MobileTelemetryEvent.recorded_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class MobileAnalyticsEventRepository(BaseRepository[MobileAnalyticsEvent]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MobileAnalyticsEvent, tenant_scope=tenant_scope)

    async def list_since(
        self, organization_id: UUID, *, since: datetime, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[MobileAnalyticsEvent]:
        stmt = (
            self._base_select()
            .where(
                MobileAnalyticsEvent.organization_id == organization_id,
                MobileAnalyticsEvent.recorded_at >= since,
            )
            .order_by(MobileAnalyticsEvent.recorded_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "MobileAnalyticsEventRepository",
    "MobileTelemetryEventRepository",
]
