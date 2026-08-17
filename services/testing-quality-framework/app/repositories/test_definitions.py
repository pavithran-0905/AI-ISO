"""Repositories for test suites and test cases."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_definitions import TestCase, TestSuite

MAX_PAGE_SIZE = 500


class TestSuiteRepository(BaseRepository[TestSuite]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, TestSuite, tenant_scope=tenant_scope)

    async def find_by_name(self, organization_id: UUID, *, name: str) -> TestSuite | None:
        stmt = self._base_select().where(
            TestSuite.organization_id == organization_id, TestSuite.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_enabled(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[TestSuite]:
        stmt = (
            self._base_select()
            .where(TestSuite.organization_id == organization_id, TestSuite.is_enabled.is_(True))
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[TestSuite]:
        stmt = self._base_select().where(TestSuite.organization_id == organization_id).limit(limit)
        return (await self._session.execute(stmt)).scalars().all()


class TestCaseRepository(BaseRepository[TestCase]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, TestCase, tenant_scope=tenant_scope)

    async def list_for_suite(self, test_suite_id: UUID) -> Sequence[TestCase]:
        stmt = self._base_select().where(TestCase.test_suite_id == test_suite_id)
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "TestCaseRepository", "TestSuiteRepository"]
