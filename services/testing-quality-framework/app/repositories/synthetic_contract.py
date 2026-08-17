"""Repositories for synthetic monitoring checks and contract tests."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.synthetic_contract import ContractTest, SyntheticCheck

MAX_PAGE_SIZE = 500


class SyntheticCheckRepository(BaseRepository[SyntheticCheck]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SyntheticCheck, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[SyntheticCheck]:
        stmt = (
            self._base_select()
            .where(SyntheticCheck.organization_id == organization_id)
            .order_by(SyntheticCheck.checked_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_since(
        self, organization_id: UUID, *, since: datetime, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[SyntheticCheck]:
        stmt = (
            self._base_select()
            .where(
                SyntheticCheck.organization_id == organization_id,
                SyntheticCheck.checked_at >= since,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


class ContractTestRepository(BaseRepository[ContractTest]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ContractTest, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ContractTest]:
        stmt = (
            self._base_select()
            .where(ContractTest.organization_id == organization_id)
            .order_by(ContractTest.created_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "ContractTestRepository", "SyntheticCheckRepository"]
