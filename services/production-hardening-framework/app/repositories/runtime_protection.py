"""Repository for runtime protection events."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.runtime_protection import RuntimeProtectionEvent

MAX_PAGE_SIZE = 500


class RuntimeProtectionEventRepository(BaseRepository[RuntimeProtectionEvent]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, RuntimeProtectionEvent, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[RuntimeProtectionEvent]:
        stmt = (
            self._base_select()
            .where(RuntimeProtectionEvent.organization_id == organization_id)
            .order_by(RuntimeProtectionEvent.detected_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "RuntimeProtectionEventRepository"]
