"""Repositories for knowledge sources, indexing jobs, statistics,
reports, and audit."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import (
    IndexingJob,
    KnowledgeSource,
    RagAudit,
    RagReport,
    RagStatistic,
)
from app.models.document import Document
from app.models.enums import IndexStatus, ReportKind, SyncStatus


class KnowledgeSourceRepository(BaseRepository[KnowledgeSource]):
    """CRUD plus lookup for :class:`KnowledgeSource`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, KnowledgeSource, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, source_id: UUID) -> KnowledgeSource:
        """Return *source_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such source exists in that organization.
        """
        stmt = self._base_select().where(
            KnowledgeSource.id == source_id,
            KnowledgeSource.organization_id == organization_id,
        )
        found: KnowledgeSource | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(
                f"KnowledgeSource {source_id!s} was not found in organization "
                f"{organization_id!s}."
            )
        return found

    async def get_by_slug(self, organization_id: UUID, slug: str) -> KnowledgeSource | None:
        """One source by its stable slug."""
        stmt = self._base_select().where(
            KnowledgeSource.organization_id == organization_id, KnowledgeSource.slug == slug
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_org(
        self, organization_id: UUID, *, limit: int = 200, offset: int = 0
    ) -> list[KnowledgeSource]:
        """Every source in this organization, newest first."""
        stmt = (
            self._base_select()
            .where(KnowledgeSource.organization_id == organization_id)
            .order_by(KnowledgeSource.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_due_for_sync(
        self, moment: datetime, *, limit: int = 100
    ) -> list[KnowledgeSource]:
        """Sources whose sync interval has elapsed.

        A source that has never synced counts as due -- a ``NULL``
        ``last_synced_at`` is the strongest possible signal that a sync
        is owed, so excluding it would leave a newly configured source
        never fetching anything.
        """
        stmt = (
            self._base_select()
            .where(
                KnowledgeSource.is_enabled.is_(True),
                KnowledgeSource.sync_enabled.is_(True),
                KnowledgeSource.sync_status != SyncStatus.SYNCING,
            )
            .order_by(KnowledgeSource.last_synced_at.asc().nulls_first())
            .limit(limit)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        return [row for row in rows if _sync_due(row, moment)]

    async def count_documents(self, source_id: UUID) -> int:
        """How many documents came from one source."""
        stmt = (
            select(func.count())
            .select_from(Document)
            .where(Document.knowledge_source_id == source_id)
        )
        return int((await self._session.execute(stmt)).scalar_one())


def _sync_due(source: KnowledgeSource, moment: datetime) -> bool:
    """Whether *source*'s own interval has elapsed."""
    if source.last_synced_at is None:
        return True
    reference = (
        source.last_synced_at
        if source.last_synced_at.tzinfo
        else source.last_synced_at.replace(tzinfo=moment.tzinfo)
    )
    return (moment - reference).total_seconds() >= source.sync_interval_seconds


class IndexingJobRepository(BaseRepository[IndexingJob]):
    """CRUD plus lookup for :class:`IndexingJob`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, IndexingJob, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, job_id: UUID) -> IndexingJob:
        """Return *job_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such job exists in that organization.
        """
        stmt = self._base_select().where(
            IndexingJob.id == job_id, IndexingJob.organization_id == organization_id
        )
        found: IndexingJob | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(
                f"IndexingJob {job_id!s} was not found in organization {organization_id!s}."
            )
        return found

    async def list_due(self, moment: datetime, *, limit: int = 25) -> list[IndexingJob]:
        """Queued jobs whose time has come, highest priority first.

        Ordered by priority then schedule time, so a priority index
        submitted late still runs before a batch submitted early -- which
        is the entire point of having a priority.
        """
        stmt = (
            self._base_select()
            .where(
                IndexingJob.status == IndexStatus.QUEUED,
                IndexingJob.scheduled_at <= moment,
            )
            .order_by(IndexingJob.priority.asc(), IndexingJob.scheduled_at.asc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_stale_running(self, cutoff: datetime, *, limit: int = 100) -> list[IndexingJob]:
        """Jobs stuck in ``RUNNING`` since before *cutoff*.

        A worker that died mid-job leaves exactly this. Without
        reclaiming them the documents stay unindexed forever with a row
        claiming otherwise, which is worse than a visible failure.
        """
        stmt = (
            self._base_select()
            .where(
                IndexingJob.status == IndexStatus.RUNNING,
                IndexingJob.started_at.is_not(None),
                IndexingJob.started_at <= cutoff,
            )
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_for_org(
        self,
        organization_id: UUID,
        *,
        status: IndexStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[IndexingJob]:
        """Jobs in this organization, newest first."""
        stmt = self._base_select().where(IndexingJob.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(IndexingJob.status == status)
        stmt = stmt.order_by(IndexingJob.created_at.desc()).limit(limit).offset(offset)
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_by_status(self, organization_id: UUID) -> dict[str, int]:
        """How many jobs sit in each status."""
        stmt = (
            select(IndexingJob.status, func.count())
            .where(IndexingJob.organization_id == organization_id)
            .group_by(IndexingJob.status)
        )
        return {str(status): int(count) for status, count in (await self._session.execute(stmt))}


class RagStatisticRepository(BaseRepository[RagStatistic]):
    """CRUD plus lookup for :class:`RagStatistic`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, RagStatistic, tenant_scope=tenant_scope)

    async def latest(self, organization_id: UUID) -> RagStatistic | None:
        """The most recently computed window."""
        stmt = (
            self._base_select()
            .where(RagStatistic.organization_id == organization_id)
            .order_by(RagStatistic.window_start.desc())
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_since(self, organization_id: UUID, *, since: datetime) -> list[RagStatistic]:
        """Windows since *since*, oldest first.

        Oldest first because the caller is drawing a trend, and a chart
        plotted newest-first reads as a mirror image of the truth.
        """
        stmt = (
            self._base_select()
            .where(
                RagStatistic.organization_id == organization_id,
                RagStatistic.window_start >= since,
            )
            .order_by(RagStatistic.window_start.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())


class RagReportRepository(BaseRepository[RagReport]):
    """CRUD plus lookup for :class:`RagReport`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, RagReport, tenant_scope=tenant_scope)

    async def list_for_org(
        self, organization_id: UUID, *, kind: ReportKind | None = None
    ) -> list[RagReport]:
        """Reports, newest first."""
        stmt = self._base_select().where(RagReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(RagReport.kind == kind)
        stmt = stmt.order_by(RagReport.created_at.desc())
        return list((await self._session.execute(stmt)).scalars().all())


class RagAuditRepository(BaseRepository[RagAudit]):
    """Append-and-read access to :class:`RagAudit`.

    Append-only by discipline: nothing in this service updates or deletes
    a row here, and the repository offers no method that would.
    """

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, RagAudit, tenant_scope=tenant_scope)

    async def list_for_org(self, organization_id: UUID, *, limit: int = 200) -> list[RagAudit]:
        """Recent audit rows, newest first."""
        stmt = (
            self._base_select()
            .where(RagAudit.organization_id == organization_id)
            .order_by(RagAudit.occurred_at.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_for_entity(
        self, organization_id: UUID, *, entity_type: str, entity_id: UUID
    ) -> list[RagAudit]:
        """Everything that happened to one entity, newest first.

        The question an access review actually asks about a document:
        who touched it, and when.
        """
        stmt = (
            self._base_select()
            .where(
                RagAudit.organization_id == organization_id,
                RagAudit.entity_type == entity_type,
                RagAudit.entity_id == entity_id,
            )
            .order_by(RagAudit.occurred_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_by_action(self, organization_id: UUID, *, since: datetime) -> dict[str, int]:
        """How many rows of each action since *since*."""
        stmt = (
            select(RagAudit.action, func.count())
            .where(
                RagAudit.organization_id == organization_id,
                RagAudit.occurred_at >= since,
            )
            .group_by(RagAudit.action)
        )
        return {str(action): int(count) for action, count in (await self._session.execute(stmt))}


__all__ = [
    "IndexingJobRepository",
    "KnowledgeSourceRepository",
    "RagAuditRepository",
    "RagReportRepository",
    "RagStatisticRepository",
]
