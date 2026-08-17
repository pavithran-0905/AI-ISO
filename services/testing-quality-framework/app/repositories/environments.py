"""Repositories for test environments, test data sets, and mock
services."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.environments import MockService, TestDataSet, TestEnvironment

MAX_PAGE_SIZE = 500


class TestEnvironmentRepository(BaseRepository[TestEnvironment]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, TestEnvironment, tenant_scope=tenant_scope)

    async def find_by_name(self, organization_id: UUID, *, name: str) -> TestEnvironment | None:
        stmt = self._base_select().where(
            TestEnvironment.organization_id == organization_id, TestEnvironment.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_active(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[TestEnvironment]:
        stmt = (
            self._base_select()
            .where(
                TestEnvironment.organization_id == organization_id,
                TestEnvironment.is_active.is_(True),
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


class TestDataSetRepository(BaseRepository[TestDataSet]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, TestDataSet, tenant_scope=tenant_scope)

    async def list_reusable(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[TestDataSet]:
        stmt = (
            self._base_select()
            .where(
                TestDataSet.organization_id == organization_id, TestDataSet.is_reusable.is_(True)
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


class MockServiceRepository(BaseRepository[MockService]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MockService, tenant_scope=tenant_scope)

    async def list_active(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[MockService]:
        stmt = (
            self._base_select()
            .where(MockService.organization_id == organization_id, MockService.is_active.is_(True))
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "MockServiceRepository",
    "TestDataSetRepository",
    "TestEnvironmentRepository",
]
