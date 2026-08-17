"""Repositories for test runs and test results."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TestRunStatus
from app.models.test_execution import TestResult, TestRun

MAX_PAGE_SIZE = 500


class TestRunRepository(BaseRepository[TestRun]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, TestRun, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, status: TestRunStatus | None = None, limit: int = 100
    ) -> Sequence[TestRun]:
        stmt = self._base_select().where(TestRun.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(TestRun.status == status)
        stmt = stmt.order_by(TestRun.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_running(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[TestRun]:
        stmt = (
            self._base_select()
            .where(
                TestRun.organization_id == organization_id, TestRun.status == TestRunStatus.RUNNING
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(TestRun.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class TestResultRepository(BaseRepository[TestResult]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, TestResult, tenant_scope=tenant_scope)

    async def list_for_run(self, test_run_id: UUID) -> Sequence[TestResult]:
        stmt = self._base_select().where(TestResult.test_run_id == test_run_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent_for_case(
        self, organization_id: UUID, *, test_case_id: UUID, limit: int = 10
    ) -> Sequence[TestResult]:
        stmt = (
            self._base_select()
            .where(
                TestResult.organization_id == organization_id,
                TestResult.test_case_id == test_case_id,
            )
            .order_by(TestResult.created_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_distinct_case_ids(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[UUID]:
        stmt = (
            select(TestResult.test_case_id)
            .where(TestResult.organization_id == organization_id)
            .distinct()
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(self, organization_id: UUID, *, limit: int = 100) -> Sequence[TestResult]:
        stmt = (
            self._base_select()
            .where(TestResult.organization_id == organization_id)
            .order_by(TestResult.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(TestResult.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "TestResultRepository", "TestRunRepository"]
