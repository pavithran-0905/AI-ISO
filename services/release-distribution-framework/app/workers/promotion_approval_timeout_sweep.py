"""The promotion approval timeout sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Rejects every release promotion that has sat ``PENDING`` past its own
configured maximum approval age -- an approval workflow that times out
is treated as a rejection, not an indefinitely-open request. Only
promotions created through the lower-level
``ReleasePromotionService.create()`` (rather than the single-hop
``promote()`` the REST route uses) can ever be found in this state.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import PromotionStatus
from app.services.bundle import build_repositories

logger = get_logger("app.workers.promotion_approval_timeout_sweep")


class PromotionApprovalTimeoutSweepWorker:
    """Rejects release promotions stuck too long in ``PENDING``."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, max_age_hours: int
    ) -> None:
        self._session_factory = session_factory
        self._max_age_hours = max_age_hours

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's pending promotions, returning how
        many were rejected."""
        now = datetime.now(UTC)
        max_age = timedelta(hours=self._max_age_hours)
        rejected = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.release_promotions.list_organization_ids():
                for promotion in await repos.release_promotions.list_by_status(
                    organization_id, status=PromotionStatus.PENDING
                ):
                    if now - promotion.created_at >= max_age:
                        promotion.status = PromotionStatus.REJECTED
                        await repos.release_promotions.update(promotion)
                        rejected += 1
            await session.commit()

        logger.info(
            "promotion approval timeout sweep completed",
            extra={"extra_fields": {"rejected": rejected}},
        )
        return rejected


__all__ = ["PromotionApprovalTimeoutSweepWorker"]
