"""The document expiry sweep worker (docs/062 "DOCUMENT LIFECYCLE").

Archives documents past their own retention date.
**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Archived, never deleted.** An expiry date is a retention policy set
months in advance by people who are not present when it fires. Archiving
keeps the embeddings, so an expiry set in error costs nothing to undo;
destroying them on an unattended timer is not recoverable.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.analytics import RagAuditRepository
from app.repositories.document import (
    DocumentChunkRepository,
    DocumentMetadataRepository,
    DocumentRepository,
    DocumentVersionRepository,
)
from app.repositories.embedding import EmbeddingVectorRepository
from app.services.documents import DocumentService
from app.types import EventPublisher

logger = get_logger("app.workers.document_expiry_sweep")


class DocumentExpirySweepWorker:
    """Archives every document past its expiry date."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        batch_size: int = 200,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._batch_size = batch_size

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Archive expired documents; returns how many were archived."""
        try:
            async with self._session_factory() as session:
                archived = await self._build(session).expire_documents(
                    datetime.now(UTC), limit=self._batch_size
                )
                await session.commit()
            if archived:
                logger.info(
                    "Archived expired documents.",
                    extra={"extra_fields": {"archived": len(archived)}},
                )
            return len(archived)
        except Exception as exc:
            logger.warning(
                "The document expiry sweep failed; it will retry on the next tick.",
                extra={"extra_fields": {"error": str(exc)}},
            )
            return 0

    def _build(self, session: AsyncSession) -> DocumentService:
        """A document service bound to one session."""
        return DocumentService(
            DocumentRepository(session),
            DocumentVersionRepository(session),
            DocumentChunkRepository(session),
            DocumentMetadataRepository(session),
            EmbeddingVectorRepository(session),
            RagAuditRepository(session),
            publish_event=self._publish_event,
        )


__all__ = ["DocumentExpirySweepWorker"]
