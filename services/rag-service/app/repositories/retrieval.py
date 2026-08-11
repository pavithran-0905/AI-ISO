"""Repositories for retrieval queries, results, reranking, and feedback."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import FeedbackVerdict, RetrievalOutcome
from app.models.retrieval import (
    RerankingResult,
    RetrievalFeedback,
    RetrievalQuery,
    RetrievalResult,
)


class RetrievalQueryRepository(BaseRepository[RetrievalQuery]):
    """CRUD plus lookup for :class:`RetrievalQuery`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, RetrievalQuery, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, query_id: UUID) -> RetrievalQuery:
        """Return *query_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such query exists in that organization.
        """
        stmt = self._base_select().where(
            RetrievalQuery.id == query_id, RetrievalQuery.organization_id == organization_id
        )
        found: RetrievalQuery | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(
                f"RetrievalQuery {query_id!s} was not found in organization "
                f"{organization_id!s}."
            )
        return found

    async def list_for_org(
        self,
        organization_id: UUID,
        *,
        outcome: RetrievalOutcome | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[RetrievalQuery]:
        """Recent queries, newest first."""
        stmt = self._base_select().where(RetrievalQuery.organization_id == organization_id)
        if outcome is not None:
            stmt = stmt.where(RetrievalQuery.outcome == outcome)
        stmt = stmt.order_by(RetrievalQuery.executed_at.desc()).limit(limit).offset(offset)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_in_window(
        self, organization_id: UUID, *, since: datetime, until: datetime
    ) -> list[RetrievalQuery]:
        """Every query inside one window."""
        stmt = self._base_select().where(
            RetrievalQuery.organization_id == organization_id,
            RetrievalQuery.executed_at >= since,
            RetrievalQuery.executed_at < until,
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def unanswered(
        self, organization_id: UUID, *, since: datetime, limit: int = 20
    ) -> list[tuple[str, int]]:
        """The queries that returned nothing, most frequent first.

        The most actionable output this service produces: a ranked list
        of what people are asking that the corpus cannot answer. Grouped
        on the normalised text so "Restore Backup" and "restore   backup"
        count as one question rather than two.
        """
        stmt = (
            select(RetrievalQuery.normalized_query, func.count().label("hits"))
            .where(
                RetrievalQuery.organization_id == organization_id,
                RetrievalQuery.outcome == RetrievalOutcome.EMPTY,
                RetrievalQuery.executed_at >= since,
                RetrievalQuery.normalized_query.is_not(None),
            )
            .group_by(RetrievalQuery.normalized_query)
            .order_by(func.count().desc())
            .limit(limit)
        )
        return [(str(text), int(hits)) for text, hits in (await self._session.execute(stmt))]

    async def average_latency(
        self, organization_id: UUID, *, since: datetime, until: datetime
    ) -> float | None:
        """Mean duration over a window, or ``None`` if nothing ran.

        ``None`` rather than ``0.0``: a window with no queries has no
        latency, and reporting zero would look like an impossibly fast
        service on a dashboard.
        """
        stmt = select(func.avg(RetrievalQuery.duration_ms)).where(
            RetrievalQuery.organization_id == organization_id,
            RetrievalQuery.executed_at >= since,
            RetrievalQuery.executed_at < until,
        )
        value = (await self._session.execute(stmt)).scalar()
        return float(value) if value is not None else None

    async def count_by_strategy(self, organization_id: UUID, *, since: datetime) -> dict[str, int]:
        """How many queries used each retrieval strategy."""
        stmt = (
            select(RetrievalQuery.strategy, func.count())
            .where(
                RetrievalQuery.organization_id == organization_id,
                RetrievalQuery.executed_at >= since,
            )
            .group_by(RetrievalQuery.strategy)
        )
        return {str(name): int(count) for name, count in (await self._session.execute(stmt))}


class RetrievalResultRepository(BaseRepository[RetrievalResult]):
    """CRUD plus lookup for :class:`RetrievalResult`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, RetrievalResult, tenant_scope=tenant_scope)

    async def list_for_query(self, retrieval_query_id: UUID) -> list[RetrievalResult]:
        """Every result of one query, in rank order."""
        stmt = (
            self._base_select()
            .where(RetrievalResult.retrieval_query_id == retrieval_query_id)
            .order_by(RetrievalResult.rank.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def top_documents(
        self, organization_id: UUID, *, since: datetime, limit: int = 10
    ) -> list[tuple[UUID, int]]:
        """The most frequently retrieved documents in a window."""
        stmt = (
            select(RetrievalResult.document_id, func.count().label("hits"))
            .where(
                RetrievalResult.organization_id == organization_id,
                RetrievalResult.created_at >= since,
            )
            .group_by(RetrievalResult.document_id)
            .order_by(func.count().desc())
            .limit(limit)
        )
        return [(doc, int(hits)) for doc, hits in (await self._session.execute(stmt))]

    async def average_result_count(
        self, organization_id: UUID, *, since: datetime, until: datetime
    ) -> float | None:
        """Mean results per query over a window."""
        subquery = (
            select(func.count().label("per_query"))
            .where(
                RetrievalResult.organization_id == organization_id,
                RetrievalResult.created_at >= since,
                RetrievalResult.created_at < until,
            )
            .group_by(RetrievalResult.retrieval_query_id)
            .subquery()
        )
        value = (await self._session.execute(select(func.avg(subquery.c.per_query)))).scalar()
        return float(value) if value is not None else None


class RerankingResultRepository(BaseRepository[RerankingResult]):
    """CRUD plus lookup for :class:`RerankingResult`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, RerankingResult, tenant_scope=tenant_scope)

    async def list_for_query(self, retrieval_query_id: UUID) -> list[RerankingResult]:
        """Every reranking decision for one query."""
        stmt = (
            self._base_select()
            .where(RerankingResult.retrieval_query_id == retrieval_query_id)
            .order_by(RerankingResult.rank_after.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def average_movement(self, organization_id: UUID, *, since: datetime) -> float:
        """Mean absolute rank change a reranker produced.

        Near zero means the reranker is pure latency -- it is running and
        changing nothing. That is worth knowing and is invisible without
        recording both ranks.
        """
        stmt = select(
            func.coalesce(
                func.avg(func.abs(RerankingResult.rank_before - RerankingResult.rank_after)), 0.0
            )
        ).where(
            RerankingResult.organization_id == organization_id,
            RerankingResult.created_at >= since,
        )
        return float((await self._session.execute(stmt)).scalar_one())


class RetrievalFeedbackRepository(BaseRepository[RetrievalFeedback]):
    """CRUD plus lookup for :class:`RetrievalFeedback`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, RetrievalFeedback, tenant_scope=tenant_scope)

    async def list_for_query(self, retrieval_query_id: UUID) -> list[RetrievalFeedback]:
        """Every human judgement on one query."""
        stmt = self._base_select().where(RetrievalFeedback.retrieval_query_id == retrieval_query_id)
        return list((await self._session.execute(stmt)).scalars().all())

    async def relevant_chunk_ids(self, retrieval_query_id: UUID) -> set[UUID]:
        """Chunks a human called relevant -- the ground truth for metrics.

        ``PARTIALLY_RELEVANT`` counts as relevant for the binary metrics.
        Precision and recall have no middle grade, and treating a
        partially useful result as a miss would understate retrieval more
        than treating it as a hit overstates it.
        """
        stmt = self._base_select().where(
            RetrievalFeedback.retrieval_query_id == retrieval_query_id,
            RetrievalFeedback.verdict.in_(
                [FeedbackVerdict.RELEVANT, FeedbackVerdict.PARTIALLY_RELEVANT]
            ),
            RetrievalFeedback.document_chunk_id.is_not(None),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return {row.document_chunk_id for row in rows if row.document_chunk_id is not None}

    async def graded_relevance(self, retrieval_query_id: UUID) -> dict[UUID, float]:
        """Chunk ids to graded relevance, for nDCG.

        A verdict with no explicit grade falls back to 1.0 for relevant
        and 0.5 for partially relevant, so nDCG still has something to
        work with when a reviewer only clicked a button.
        """
        graded: dict[UUID, float] = {}
        for row in await self.list_for_query(retrieval_query_id):
            if row.document_chunk_id is None:
                continue
            if row.relevance is not None:
                graded[row.document_chunk_id] = float(row.relevance)
            elif row.verdict == FeedbackVerdict.RELEVANT:
                graded[row.document_chunk_id] = 1.0
            elif row.verdict == FeedbackVerdict.PARTIALLY_RELEVANT:
                graded[row.document_chunk_id] = 0.5
        return graded

    async def count_by_verdict(self, organization_id: UUID, *, since: datetime) -> dict[str, int]:
        """How much feedback of each kind arrived in a window."""
        stmt = (
            select(RetrievalFeedback.verdict, func.count())
            .where(
                RetrievalFeedback.organization_id == organization_id,
                RetrievalFeedback.submitted_at >= since,
            )
            .group_by(RetrievalFeedback.verdict)
        )
        return {str(name): int(count) for name, count in (await self._session.execute(stmt))}

    async def list_judged_queries(
        self, organization_id: UUID, *, since: datetime, limit: int = 500
    ) -> list[UUID]:
        """Queries that have any human feedback at all.

        The population every offline metric is computed over. Queries
        nobody judged are excluded rather than scored zero -- see
        :func:`~app.evaluation.metrics.mean_reciprocal_rank`.
        """
        stmt = (
            select(RetrievalFeedback.retrieval_query_id)
            .where(
                RetrievalFeedback.organization_id == organization_id,
                RetrievalFeedback.submitted_at >= since,
            )
            .distinct()
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())


__all__ = [
    "RerankingResultRepository",
    "RetrievalFeedbackRepository",
    "RetrievalQueryRepository",
    "RetrievalResultRepository",
]
