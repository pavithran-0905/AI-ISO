"""Repositories for :class:`~app.models.testing.PromptTest`,
:class:`~app.models.testing.PromptTestResult`,
:class:`~app.models.testing.PromptAbTest`, and
:class:`~app.models.testing.PromptExecution`.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AbTestStatus, ExecutionStatus, TestRunStatus
from app.models.testing import PromptAbTest, PromptExecution, PromptTest, PromptTestResult


class PromptTestRepository(BaseRepository[PromptTest]):
    """CRUD plus lookup for :class:`PromptTest`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptTest, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, test_id: UUID) -> PromptTest:
        """Return *test_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such test exists in that organization.
        """
        stmt = self._base_select().where(
            PromptTest.id == test_id, PromptTest.organization_id == organization_id
        )
        result = await self._session.execute(stmt)
        found: PromptTest | None = result.scalars().first()
        if found is None:
            raise NotFoundError(
                f"PromptTest {test_id!s} was not found in organization {organization_id!s}."
            )
        return found

    async def list_for_prompt(
        self, prompt_id: UUID, *, enabled_only: bool = False
    ) -> list[PromptTest]:
        """Every test defined for *prompt_id*."""
        stmt = self._base_select().where(PromptTest.prompt_id == prompt_id)
        if enabled_only:
            stmt = stmt.where(PromptTest.enabled.is_(True))
        stmt = stmt.order_by(PromptTest.name.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_org(
        self, organization_id: UUID, *, limit: int = 200, offset: int = 0
    ) -> list[PromptTest]:
        """Every test in *organization_id*, newest first."""
        stmt = (
            self._base_select()
            .where(PromptTest.organization_id == organization_id)
            .order_by(PromptTest.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class PromptTestResultRepository(BaseRepository[PromptTestResult]):
    """CRUD plus lookup for :class:`PromptTestResult`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptTestResult, tenant_scope=tenant_scope)

    async def list_for_test(
        self, prompt_test_id: UUID, *, limit: int = 100
    ) -> list[PromptTestResult]:
        """One test's own run history, newest first -- the regression signal."""
        stmt = (
            self._base_select()
            .where(PromptTestResult.prompt_test_id == prompt_test_id)
            .order_by(PromptTestResult.run_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_version(self, prompt_version_id: UUID) -> list[PromptTestResult]:
        """Every test result recorded against one revision."""
        stmt = (
            self._base_select()
            .where(PromptTestResult.prompt_version_id == prompt_version_id)
            .order_by(PromptTestResult.run_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_failed_for_version(self, prompt_version_id: UUID) -> int:
        """How many tests one revision currently fails.

        Counts ``ERRORED`` alongside ``FAILED``: a test that could not
        run has not demonstrated the revision is sound, and treating it
        as a pass would let a publish through on the strength of a
        broken test harness.
        """
        stmt = self._base_select().where(
            PromptTestResult.prompt_version_id == prompt_version_id,
            PromptTestResult.status.in_((TestRunStatus.FAILED, TestRunStatus.ERRORED)),
        )
        result = await self._session.execute(stmt)
        return len(list(result.scalars().all()))


class PromptAbTestRepository(BaseRepository[PromptAbTest]):
    """CRUD plus lookup for :class:`PromptAbTest`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptAbTest, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, ab_test_id: UUID) -> PromptAbTest:
        """Return *ab_test_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such experiment exists in that organization.
        """
        stmt = self._base_select().where(
            PromptAbTest.id == ab_test_id, PromptAbTest.organization_id == organization_id
        )
        result = await self._session.execute(stmt)
        found: PromptAbTest | None = result.scalars().first()
        if found is None:
            raise NotFoundError(
                f"PromptAbTest {ab_test_id!s} was not found in organization "
                f"{organization_id!s}."
            )
        return found

    async def get_running_for_prompt(self, prompt_id: UUID) -> PromptAbTest | None:
        """The live experiment on *prompt_id*, or ``None``.

        At most one experiment may run per prompt at a time -- two
        concurrent splits over the same prompt would make each one's
        control arm contaminated by the other's variant, and neither
        result would mean anything.
        """
        stmt = self._base_select().where(
            PromptAbTest.prompt_id == prompt_id,
            PromptAbTest.status == AbTestStatus.RUNNING,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_running(self, *, limit: int = 200) -> list[PromptAbTest]:
        """Every running experiment platform-wide -- backs the evaluation sweep."""
        stmt = (
            self._base_select()
            .where(PromptAbTest.status == AbTestStatus.RUNNING)
            .order_by(PromptAbTest.started_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_org(
        self, organization_id: UUID, *, limit: int = 200, offset: int = 0
    ) -> list[PromptAbTest]:
        """Every experiment in *organization_id*, newest first."""
        stmt = (
            self._base_select()
            .where(PromptAbTest.organization_id == organization_id)
            .order_by(PromptAbTest.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class PromptExecutionRepository(BaseRepository[PromptExecution]):
    """CRUD plus lookup for :class:`PromptExecution`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptExecution, tenant_scope=tenant_scope)

    async def list_for_prompt(self, prompt_id: UUID, *, limit: int = 100) -> list[PromptExecution]:
        """One prompt's own most recent executions, newest first."""
        stmt = (
            self._base_select()
            .where(PromptExecution.prompt_id == prompt_id)
            .order_by(PromptExecution.executed_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_version(
        self, prompt_version_id: UUID, *, limit: int = 100
    ) -> list[PromptExecution]:
        """One revision's own executions, newest first."""
        stmt = (
            self._base_select()
            .where(PromptExecution.prompt_version_id == prompt_version_id)
            .order_by(PromptExecution.executed_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_in_window(
        self, organization_id: UUID, *, since: datetime, until: datetime
    ) -> list[PromptExecution]:
        """Executions for *organization_id* within one window -- backs
        the statistics rollup."""
        stmt = self._base_select().where(
            PromptExecution.organization_id == organization_id,
            PromptExecution.executed_at >= since,
            PromptExecution.executed_at < until,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def arm_counts(self, ab_test_id: UUID) -> dict[str, tuple[int, int]]:
        """``{arm: (executions, successes)}`` for one experiment.

        The authoritative recount the A/B evaluation sweep reconciles
        the experiment row's own cached counters against -- those
        counters exist for speed, and a cheap way to confirm they have
        not drifted is worth having.
        """
        stmt = self._base_select().where(PromptExecution.ab_test_id == ab_test_id)
        result = await self._session.execute(stmt)
        counts: dict[str, list[int]] = {}
        for row in result.scalars().all():
            if row.ab_arm is None:
                continue
            bucket = counts.setdefault(str(row.ab_arm), [0, 0])
            bucket[0] += 1
            if row.status == ExecutionStatus.SUCCEEDED:
                bucket[1] += 1
        return {arm: (totals[0], totals[1]) for arm, totals in counts.items()}


__all__ = [
    "PromptAbTestRepository",
    "PromptExecutionRepository",
    "PromptTestRepository",
    "PromptTestResultRepository",
]
