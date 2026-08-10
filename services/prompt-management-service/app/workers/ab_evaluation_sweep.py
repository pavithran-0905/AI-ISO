"""The A/B evaluation sweep worker (docs/061 "A/B TESTING": Winner
Selection, Automatic Promotion).

Evaluates every running experiment and concludes the ones that have
reached significance. **Leader-elected** through
``shared_core.scheduler``; see :mod:`app.workers.registrar`.

**Automatic promotion is off by default, and even when on it does not
publish here.** Promoting a winner means publishing a new prompt
version, which is exactly the action this service's own approval
workflow exists to gate. When ``auto_promote`` is enabled the
experiment is marked ``PROMOTED`` and the decision recorded; the
publish itself still goes through the normal gated path.
"""

from __future__ import annotations

from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import AbTestStatus
from app.repositories.analytics import PromptAuditRepository
from app.repositories.testing import PromptAbTestRepository, PromptExecutionRepository
from app.services.testing import AbTestingService
from app.types import EventPublisher

logger = get_logger("app.workers.ab_evaluation_sweep")


class AbEvaluationSweepWorker:
    """Concludes running experiments that have reached significance."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        auto_promote: bool = False,
        max_per_tick: int = 100,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._auto_promote = auto_promote
        self._max_per_tick = max_per_tick

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Evaluate every running experiment; returns how many concluded."""
        async with self._session_factory() as session:
            running = await PromptAbTestRepository(session).list_running(limit=self._max_per_tick)
            targets = [(row.id, row.organization_id) for row in running]

        concluded = 0
        for experiment_id, organization_id in targets:
            if await self._evaluate_one(experiment_id, organization_id):
                concluded += 1

        logger.info(
            "A/B evaluation sweep complete.",
            extra={"extra_fields": {"running": len(targets), "concluded": concluded}},
        )
        return concluded

    async def _evaluate_one(self, experiment_id: UUID, organization_id: UUID) -> bool:
        """Evaluate one experiment under its own session.

        One experiment failing must not poison the transaction the next
        one needs, nor stop the sweep.
        """
        try:
            async with self._session_factory() as session:
                repo = PromptAbTestRepository(session)
                service = AbTestingService(
                    repo,
                    PromptExecutionRepository(session),
                    PromptAuditRepository(session),
                    publish_event=self._publish_event,
                )
                experiment = await repo.require_in_org(organization_id, experiment_id)
                result = await service.evaluate(experiment)
                if not result.significant:
                    await session.commit()
                    return False

                experiment = await service.conclude(experiment, result, decided_by="ab-sweep")
                if self._auto_promote and experiment.auto_promote and result.variant_wins:
                    experiment.status = AbTestStatus.PROMOTED
                    await repo.update(experiment)
                await session.commit()
                return True
        except Exception as exc:
            logger.warning(
                "An A/B experiment evaluation failed; the rest of the sweep continues.",
                extra={"extra_fields": {"ab_test_id": str(experiment_id), "error": str(exc)}},
            )
            return False


__all__ = ["AbEvaluationSweepWorker"]
