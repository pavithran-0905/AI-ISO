"""Repositories for developer accounts and their owning organizations."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.developers import DeveloperAccount, DeveloperOrganization

MAX_PAGE_SIZE = 500


class DeveloperAccountRepository(BaseRepository[DeveloperAccount]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeveloperAccount, tenant_scope=tenant_scope)

    async def find_by_email(self, organization_id: UUID, *, email: str) -> DeveloperAccount | None:
        stmt = self._base_select().where(
            DeveloperAccount.organization_id == organization_id, DeveloperAccount.email == email
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[DeveloperAccount]:
        stmt = (
            self._base_select()
            .where(DeveloperAccount.organization_id == organization_id)
            .order_by(DeveloperAccount.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def count_since(self, organization_id: UUID, *, since: datetime) -> int:
        stmt = self._base_select().where(
            DeveloperAccount.organization_id == organization_id,
            DeveloperAccount.created_at >= since,
        )
        return len((await self._session.execute(stmt)).scalars().all())

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(DeveloperAccount.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class DeveloperOrganizationRepository(BaseRepository[DeveloperOrganization]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeveloperOrganization, tenant_scope=tenant_scope)


__all__ = ["MAX_PAGE_SIZE", "DeveloperAccountRepository", "DeveloperOrganizationRepository"]
