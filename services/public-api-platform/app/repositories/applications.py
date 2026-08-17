"""Repositories for developer applications and their credentials."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.applications import ApplicationCredential, DeveloperApplication

MAX_PAGE_SIZE = 500


class DeveloperApplicationRepository(BaseRepository[DeveloperApplication]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeveloperApplication, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[DeveloperApplication]:
        stmt = (
            self._base_select()
            .where(DeveloperApplication.organization_id == organization_id)
            .order_by(DeveloperApplication.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(DeveloperApplication.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_developer(
        self, organization_id: UUID, *, developer_account_id: UUID, limit: int = 100
    ) -> Sequence[DeveloperApplication]:
        stmt = (
            self._base_select()
            .where(
                DeveloperApplication.organization_id == organization_id,
                DeveloperApplication.developer_account_id == developer_account_id,
            )
            .order_by(DeveloperApplication.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def count_for_developer(
        self, organization_id: UUID, *, developer_account_id: UUID
    ) -> int:
        stmt = self._base_select().where(
            DeveloperApplication.organization_id == organization_id,
            DeveloperApplication.developer_account_id == developer_account_id,
        )
        return len((await self._session.execute(stmt)).scalars().all())


class ApplicationCredentialRepository(BaseRepository[ApplicationCredential]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ApplicationCredential, tenant_scope=tenant_scope)

    async def find_by_client_id(
        self, organization_id: UUID, *, client_id: str
    ) -> ApplicationCredential | None:
        stmt = self._base_select().where(
            ApplicationCredential.organization_id == organization_id,
            ApplicationCredential.client_id == client_id,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_application(self, application_id: UUID) -> Sequence[ApplicationCredential]:
        stmt = self._base_select().where(ApplicationCredential.application_id == application_id)
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "ApplicationCredentialRepository", "DeveloperApplicationRepository"]
