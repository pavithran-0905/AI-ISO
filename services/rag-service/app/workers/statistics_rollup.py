"""The statistics rollup worker (docs/062 "ANALYTICS & REPORTING").

Recomputes every organization's rolling RAG statistics.
**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**One session per organization.** A failure on one tenant must not poison
the transaction the next one needs, and a tenant silently missing from a
rollup is worse than a rollup that visibly failed for it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.analytics import (
    IndexingJobRepository,
    KnowledgeSourceRepository,
    RagAuditRepository,
    RagReportRepository,
    RagStatisticRepository,
)
from app.repositories.document import DocumentChunkRepository, DocumentRepository
from app.repositories.embedding import EmbeddingVectorRepository
from app.repositories.retrieval import (
    RetrievalFeedbackRepository,
    RetrievalQueryRepository,
    RetrievalResultRepository,
)
from app.services.analytics import AnalyticsService
from app.types import EventPublisher

logger = get_logger("app.workers.statistics_rollup")


class StatisticsRollupWorker:
    """Recomputes every organization's RAG statistics."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        window_seconds: int,
        embedding_dimensions: int = 1_536,
        max_organizations_per_tick: int = 200,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._window_seconds = window_seconds
        self._dimensions = embedding_dimensions
        self._max_organizations = max_organizations_per_tick

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Recompute every organization's window; returns how many succeeded."""
        organizations = await self._organizations()
        done = 0
        for organization_id in organizations:
            if await self._recompute(organization_id):
                done += 1
        logger.info(
            "RAG statistics rollup complete.",
            extra={"extra_fields": {"organizations": len(organizations), "succeeded": done}},
        )
        return done

    async def _organizations(self) -> list[UUID]:
        """Every organization with at least one document."""
        async with self._session_factory() as session:
            return await DocumentRepository(session).list_organization_ids(
                limit=self._max_organizations
            )

    async def _recompute(self, organization_id: UUID) -> bool:
        """Recompute one organization's window under its own session."""
        try:
            now = datetime.now(UTC)
            async with self._session_factory() as session:
                await self._build(session).compute_statistics(
                    organization_id,
                    window_start=now - timedelta(seconds=self._window_seconds),
                    window_end=now,
                )
                await session.commit()
            return True
        except Exception as exc:
            logger.warning(
                "A RAG statistics rollup failed; the rest of the tick continues.",
                extra={
                    "extra_fields": {"organization_id": str(organization_id), "error": str(exc)}
                },
            )
            return False

    def _build(self, session: AsyncSession) -> AnalyticsService:
        """An analytics service bound to one session."""
        return AnalyticsService(
            DocumentRepository(session),
            DocumentChunkRepository(session),
            EmbeddingVectorRepository(session),
            RetrievalQueryRepository(session),
            RetrievalResultRepository(session),
            RetrievalFeedbackRepository(session),
            IndexingJobRepository(session),
            KnowledgeSourceRepository(session),
            RagStatisticRepository(session),
            RagReportRepository(session),
            RagAuditRepository(session),
            publish_event=self._publish_event,
            embedding_dimensions=self._dimensions,
        )


__all__ = ["StatisticsRollupWorker"]
