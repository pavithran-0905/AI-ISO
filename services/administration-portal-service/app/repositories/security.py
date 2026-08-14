"""Repositories for security policy settings and security events."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SecurityEventSeverity
from app.models.security import SecurityEvent, SecuritySetting

MAX_PAGE_SIZE = 500


class SecuritySettingRepository(BaseRepository[SecuritySetting]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SecuritySetting, tenant_scope=tenant_scope)

    async def find_by_key(self, organization_id: UUID, *, key: str) -> SecuritySetting | None:
        stmt = self._base_select().where(
            SecuritySetting.organization_id == organization_id, SecuritySetting.key == key
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_all(self, organization_id: UUID) -> Sequence[SecuritySetting]:
        stmt = self._base_select().where(SecuritySetting.organization_id == organization_id)
        return (await self._session.execute(stmt)).scalars().all()


class SecurityEventRepository(BaseRepository[SecurityEvent]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SecurityEvent, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        severity: SecurityEventSeverity | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> Sequence[SecurityEvent]:
        stmt = self._base_select().where(SecurityEvent.organization_id == organization_id)
        if severity is not None:
            stmt = stmt.where(SecurityEvent.severity == severity)
        if since is not None:
            stmt = stmt.where(SecurityEvent.detected_at >= since)
        stmt = stmt.order_by(SecurityEvent.detected_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def count_since(self, organization_id: UUID, *, since: datetime) -> int:
        stmt = self._base_select().where(
            SecurityEvent.organization_id == organization_id, SecurityEvent.detected_at >= since
        )
        return len((await self._session.execute(stmt)).scalars().all())

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(SecurityEvent.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "SecurityEventRepository", "SecuritySettingRepository"]
