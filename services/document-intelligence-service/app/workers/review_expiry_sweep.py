"""The review expiry sweep worker (docs/063 "HUMAN REVIEW").

Escalates reviews that passed their deadline. **Leader-elected** through
``shared_core.scheduler``; see :mod:`app.workers.registrar`.

**Escalated, not expired.** A review nobody completed is still a document
nobody checked; marking it EXPIRED would drop it out of every open-work
query while leaving the document unreviewed, which is the quiet failure
this sweep exists to prevent.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.bundle import build_repositories
from app.services.review import ReviewService
from app.types import EventPublisher

logger = get_logger("app.workers.review_expiry_sweep")


class ReviewExpirySweepWorker:
    """Escalates overdue reviews."""

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
        """Escalate every overdue review, returning how many."""
        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = ReviewService(repositories=repos, publish=self._publish_event)
            escalated = await service.expire_overdue(now=datetime.now(UTC), limit=self._batch_size)
            await session.commit()

        if escalated:
            logger.info(
                "review expiry sweep escalated overdue reviews",
                extra={"extra_fields": {"escalated": escalated}},
            )
        return escalated


__all__ = ["ReviewExpirySweepWorker"]
