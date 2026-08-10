"""The approval-expiry sweep worker (docs/061 "GOVERNANCE": Approval
Workflow, Expiration Policies).

Marks every pending approval past its own deadline as ``EXPIRED``.
**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

An approval request that sits unanswered forever silently blocks a
publish with no signal that anything is wrong. Visibly lapsing is
strictly better: the blocker becomes legible, and reopening is an
explicit act.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.analytics import PromptAuditRepository
from app.repositories.governance import PromptApprovalRepository
from app.services.governance import ApprovalService
from app.types import EventPublisher

logger = get_logger("app.workers.approval_expiry_sweep")


class ApprovalExpirySweepWorker:
    """Expires approval requests whose own deadline has passed."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        max_per_tick: int = 200,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._max_per_tick = max_per_tick

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Expire every lapsed approval; returns how many lapsed."""
        try:
            async with self._session_factory() as session:
                service = ApprovalService(
                    PromptApprovalRepository(session),
                    PromptAuditRepository(session),
                    publish_event=self._publish_event,
                )
                expired = await service.expire_lapsed(datetime.now(UTC), limit=self._max_per_tick)
                await session.commit()
        except Exception as exc:
            logger.warning(
                "The approval expiry sweep failed; the next tick will retry.",
                extra={"extra_fields": {"error": str(exc)}},
            )
            return 0

        logger.info(
            "Approval expiry sweep complete.",
            extra={"extra_fields": {"expired": expired}},
        )
        return expired


__all__ = ["ApprovalExpirySweepWorker"]
