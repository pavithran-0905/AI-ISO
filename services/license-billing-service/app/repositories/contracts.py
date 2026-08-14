"""Repository for enterprise contracts."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contracts import Contract

MAX_PAGE_SIZE = 500


class ContractRepository(BaseRepository[Contract]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Contract, tenant_scope=tenant_scope)

    async def list_for_customer(self, customer_id: UUID) -> Sequence[Contract]:
        stmt = self._base_select().where(Contract.customer_id == customer_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(self, organization_id: UUID, *, limit: int = 100) -> Sequence[Contract]:
        stmt = (
            self._base_select()
            .where(Contract.organization_id == organization_id)
            .order_by(Contract.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "ContractRepository"]
