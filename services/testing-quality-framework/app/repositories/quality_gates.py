"""Repository for quality gates."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import QualityGateStatus
from app.models.quality_gates import QualityGate

MAX_PAGE_SIZE = 500


class QualityGateRepository(BaseRepository[QualityGate]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, QualityGate, tenant_scope=tenant_scope)

    async def find_by_name(self, organization_id: UUID, *, name: str) -> QualityGate | None:
        stmt = self._base_select().where(
            QualityGate.organization_id == organization_id, QualityGate.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[QualityGate]:
        stmt = (
            self._base_select().where(QualityGate.organization_id == organization_id).limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: QualityGateStatus, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[QualityGate]:
        stmt = (
            self._base_select()
            .where(QualityGate.organization_id == organization_id, QualityGate.status == status)
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "QualityGateRepository"]
