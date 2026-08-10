"""The review-cycle sweep worker (docs/061 "GOVERNANCE": Review Cycle,
Expiration Policies).

Flags published prompts that have gone unreviewed past the configured
cycle, and deprecates ones past their own explicit expiry.
**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Flagging is not deprecating.** An overdue review means "a human
should look at this", not "stop serving it" -- silently deprecating a
prompt because nobody reviewed it on schedule would break production
over a paperwork lapse. Only an explicit ``expires_at`` deprecates.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.analytics import PromptAudit
from app.models.enums import AuditAction, PromptLifecycleStatus
from app.repositories.analytics import PromptAuditRepository
from app.repositories.prompt import PromptRepository

logger = get_logger("app.workers.review_cycle_sweep")


class ReviewCycleSweepWorker:
    """Flags overdue reviews and deprecates genuinely expired prompts."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        review_cycle_days: int,
        max_per_tick: int = 200,
    ) -> None:
        self._session_factory = session_factory
        self._review_cycle_days = review_cycle_days
        self._max_per_tick = max_per_tick

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> tuple[int, int]:
        """Returns ``(flagged_overdue, deprecated_expired)``."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=self._review_cycle_days)
        flagged = 0
        deprecated = 0

        try:
            async with self._session_factory() as session:
                prompts = PromptRepository(session)
                audit = PromptAuditRepository(session)

                for prompt in await prompts.list_due_for_review(cutoff, limit=self._max_per_tick):
                    await audit.create(
                        PromptAudit(
                            organization_id=prompt.organization_id,
                            action=AuditAction.ADMINISTRATIVE,
                            entity_type="prompt",
                            entity_id=prompt.id,
                            entity_reference=prompt.slug,
                            actor_type="system",
                            occurred_at=now,
                            summary=(
                                f"Prompt {prompt.slug!r} has gone unreviewed for over "
                                f"{self._review_cycle_days} days."
                            ),
                            succeeded=False,
                        )
                    )
                    flagged += 1

                for prompt in await prompts.list_expired(now, limit=self._max_per_tick):
                    prompt.status = PromptLifecycleStatus.DEPRECATED
                    await prompts.update(prompt)
                    await audit.create(
                        PromptAudit(
                            organization_id=prompt.organization_id,
                            action=AuditAction.DEPRECATED,
                            entity_type="prompt",
                            entity_id=prompt.id,
                            entity_reference=prompt.slug,
                            actor_type="system",
                            occurred_at=now,
                            summary=(
                                f"Prompt {prompt.slug!r} passed its own expiry date and "
                                "was deprecated automatically."
                            ),
                        )
                    )
                    deprecated += 1

                await session.commit()
        except Exception as exc:
            logger.warning(
                "The review cycle sweep failed; the next tick will retry.",
                extra={"extra_fields": {"error": str(exc)}},
            )
            return 0, 0

        logger.info(
            "Review cycle sweep complete.",
            extra={"extra_fields": {"flagged": flagged, "deprecated": deprecated}},
        )
        return flagged, deprecated


__all__ = ["ReviewCycleSweepWorker"]
