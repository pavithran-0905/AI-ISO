"""Repository for the compatibility matrix."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compatibility import CompatibilityMatrixEntry
from app.models.enums import CompatibilityType

MAX_PAGE_SIZE = 500


class CompatibilityMatrixRepository(BaseRepository[CompatibilityMatrixEntry]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CompatibilityMatrixEntry, tenant_scope=tenant_scope)

    async def find_entry(
        self,
        organization_id: UUID,
        *,
        from_version: str,
        to_version: str,
        compatibility_type: CompatibilityType,
    ) -> CompatibilityMatrixEntry | None:
        stmt = self._base_select().where(
            CompatibilityMatrixEntry.organization_id == organization_id,
            CompatibilityMatrixEntry.from_version == from_version,
            CompatibilityMatrixEntry.to_version == to_version,
            CompatibilityMatrixEntry.compatibility_type == compatibility_type,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_version_pair(
        self, organization_id: UUID, *, from_version: str, to_version: str
    ) -> Sequence[CompatibilityMatrixEntry]:
        stmt = self._base_select().where(
            CompatibilityMatrixEntry.organization_id == organization_id,
            CompatibilityMatrixEntry.from_version == from_version,
            CompatibilityMatrixEntry.to_version == to_version,
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[CompatibilityMatrixEntry]:
        stmt = (
            self._base_select()
            .where(CompatibilityMatrixEntry.organization_id == organization_id)
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "CompatibilityMatrixRepository"]
