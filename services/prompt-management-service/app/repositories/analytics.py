"""Repositories for :class:`~app.models.analytics.PromptOptimization`,
:class:`~app.models.analytics.PromptStatistic`,
:class:`~app.models.analytics.PromptReport`, and
:class:`~app.models.analytics.PromptAudit`.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import PromptAudit, PromptOptimization, PromptReport, PromptStatistic
from app.models.enums import OptimizationStatus, ReportKind


class PromptOptimizationRepository(BaseRepository[PromptOptimization]):
    """CRUD plus lookup for :class:`PromptOptimization`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptOptimization, tenant_scope=tenant_scope)

    async def require_in_org(
        self, organization_id: UUID, optimization_id: UUID
    ) -> PromptOptimization:
        """Return *optimization_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such suggestion exists in that organization.
        """
        stmt = self._base_select().where(
            PromptOptimization.id == optimization_id,
            PromptOptimization.organization_id == organization_id,
        )
        result = await self._session.execute(stmt)
        found: PromptOptimization | None = result.scalars().first()
        if found is None:
            raise NotFoundError(
                f"PromptOptimization {optimization_id!s} was not found in organization "
                f"{organization_id!s}."
            )
        return found

    async def list_for_version(self, prompt_version_id: UUID) -> list[PromptOptimization]:
        """Every suggestion made for one revision, newest first."""
        stmt = (
            self._base_select()
            .where(PromptOptimization.prompt_version_id == prompt_version_id)
            .order_by(PromptOptimization.suggested_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_open(
        self, organization_id: UUID, *, limit: int = 200
    ) -> list[PromptOptimization]:
        """Suggestions nobody has accepted or rejected yet."""
        stmt = (
            self._base_select()
            .where(
                PromptOptimization.organization_id == organization_id,
                PromptOptimization.status == OptimizationStatus.SUGGESTED,
            )
            .order_by(PromptOptimization.token_saving.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def accepted_savings_in_window(
        self, organization_id: UUID, *, since: datetime, until: datetime
    ) -> int:
        """Total tokens saved by suggestions actually **accepted**.

        Accepted only. Counting suggestions nobody took would report
        savings the organization never actually realised, which is the
        one number in this whole service most likely to end up in a
        slide deck.
        """
        stmt = self._base_select().where(
            PromptOptimization.organization_id == organization_id,
            PromptOptimization.status == OptimizationStatus.ACCEPTED,
            PromptOptimization.decided_at.is_not(None),
            PromptOptimization.decided_at >= since,
            PromptOptimization.decided_at < until,
        )
        result = await self._session.execute(stmt)
        return sum(row.token_saving for row in result.scalars().all())


class PromptStatisticRepository(BaseRepository[PromptStatistic]):
    """CRUD plus lookup for :class:`PromptStatistic`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptStatistic, tenant_scope=tenant_scope)

    async def latest(self, organization_id: UUID) -> PromptStatistic | None:
        """The most recently rolled-up window for *organization_id*."""
        stmt = (
            self._base_select()
            .where(PromptStatistic.organization_id == organization_id)
            .order_by(PromptStatistic.window_start.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_since(self, organization_id: UUID, *, since: datetime) -> list[PromptStatistic]:
        """Every window starting at or after *since*, **oldest first**.

        The ordering is part of the contract, not incidental: a trend
        chart plots these in arrival order, and an unordered ``SELECT``
        lets PostgreSQL return them however a scan happens to produce
        them. (The same defect was found and fixed in
        ai-agent-platform-service's equivalent.)
        """
        stmt = (
            self._base_select()
            .where(
                PromptStatistic.organization_id == organization_id,
                PromptStatistic.window_start >= since,
            )
            .order_by(PromptStatistic.window_start.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class PromptReportRepository(BaseRepository[PromptReport]):
    """CRUD plus lookup for :class:`PromptReport`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptReport, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, report_id: UUID) -> PromptReport:
        """Return *report_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such report exists in that organization.
        """
        stmt = self._base_select().where(
            PromptReport.id == report_id, PromptReport.organization_id == organization_id
        )
        result = await self._session.execute(stmt)
        found: PromptReport | None = result.scalars().first()
        if found is None:
            raise NotFoundError(
                f"PromptReport {report_id!s} was not found in organization {organization_id!s}."
            )
        return found

    async def list_for_org(
        self, organization_id: UUID, *, kind: ReportKind | None = None
    ) -> list[PromptReport]:
        """Every report for *organization_id*, newest first."""
        stmt = self._base_select().where(PromptReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(PromptReport.kind == kind)
        stmt = stmt.order_by(PromptReport.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class PromptAuditRepository(BaseRepository[PromptAudit]):
    """Append-and-read access to :class:`PromptAudit`.

    docs/061 requires an **immutable** audit history, so this exposes
    creation and reads only. Nothing here updates or deletes a row, and
    no service in this codebase calls the inherited mutators on it.
    """

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptAudit, tenant_scope=tenant_scope)

    async def list_for_entity(self, entity_type: str, entity_id: UUID) -> list[PromptAudit]:
        """Every audit row for one specific entity, newest first."""
        stmt = (
            self._base_select()
            .where(PromptAudit.entity_type == entity_type, PromptAudit.entity_id == entity_id)
            .order_by(PromptAudit.occurred_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_org(self, organization_id: UUID, *, limit: int = 200) -> list[PromptAudit]:
        """*organization_id*'s own most recent audit rows, newest first."""
        stmt = (
            self._base_select()
            .where(PromptAudit.organization_id == organization_id)
            .order_by(PromptAudit.occurred_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_action(self, organization_id: UUID, *, since: datetime) -> dict[str, int]:
        """How many audit rows of each action since *since*."""
        stmt = (
            self._base_select()
            .where(
                PromptAudit.organization_id == organization_id,
                PromptAudit.occurred_at >= since,
            )
            .with_only_columns(PromptAudit.action, func.count())
            .group_by(PromptAudit.action)
        )
        result = await self._session.execute(stmt)
        return {str(action): count for action, count in result.all()}


__all__ = [
    "PromptAuditRepository",
    "PromptOptimizationRepository",
    "PromptReportRepository",
    "PromptStatisticRepository",
]
