"""The knowledge-source sync sweep worker (docs/062 "KNOWLEDGE SOURCE
MANAGEMENT").

Finds the sources whose sync interval has elapsed and keeps their document
counts honest. **Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**It does not fetch anything, and says so rather than pretending.** No
Confluence, SharePoint, or S3 instance exists in this platform's
infrastructure, so a connector here would be code that has never run
against the system it claims to talk to. What this worker does is real and
useful on its own: it is the scheduler half -- identifying due sources and
recounting their documents -- with
:meth:`~app.services.sources.SourceService.record_sync` as the seam a
connector calls back into.

**Being due does not mark a source ``SYNCING``.** Claiming it here would be
worse than doing nothing: nothing would then clear the claim, so after one
tick every source would be stuck syncing forever. The claim belongs to
whoever is actually about to fetch.
"""

from __future__ import annotations

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.analytics import KnowledgeSourceRepository, RagAuditRepository
from app.repositories.document import DocumentRepository
from app.services.sources import SourceService
from app.types import EventPublisher

logger = get_logger("app.workers.source_sync_sweep")


class SourceSyncSweepWorker:
    """Reports which knowledge sources are due for a sync."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        batch_size: int = 100,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._batch_size = batch_size

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Report the due sources and refresh their counts; returns how many."""
        try:
            async with self._session_factory() as session:
                service = self._build(session)
                due = await service.list_due_for_sync(limit=self._batch_size)
                for organization_id in {source.organization_id for source in due}:
                    await service.refresh_document_counts(organization_id)
                await session.commit()
            if due:
                logger.info(
                    "Knowledge sources are due for sync.",
                    extra={
                        "extra_fields": {
                            "due": len(due),
                            "slugs": sorted(source.slug for source in due)[:20],
                        }
                    },
                )
            return len(due)
        except Exception as exc:
            logger.warning(
                "The knowledge-source sync sweep failed; it will retry on the next tick.",
                extra={"extra_fields": {"error": str(exc)}},
            )
            return 0

    def _build(self, session: AsyncSession) -> SourceService:
        """A source service bound to one session."""
        return SourceService(
            KnowledgeSourceRepository(session),
            DocumentRepository(session),
            RagAuditRepository(session),
            publish_event=self._publish_event,
        )


__all__ = ["SourceSyncSweepWorker"]
