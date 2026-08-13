"""The SLO evaluation worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Counts good/total from trace span status, per :class:`Slo.service_name`.
An SLI derived from span outcomes covers ``AVAILABILITY``,
``SUCCESS_RATE`` and ``ERROR_RATE`` -- the three ratio kinds every span
already carries evidence for via :class:`~app.models.enums.SpanStatus`.
``LATENCY``, ``THROUGHPUT`` and ``CUSTOM`` SLOs need a different counting
source (a duration threshold, a rate, an arbitrary query) and are left at
``NO_DATA`` here rather than approximated -- a wrong approximation is
worse than an honest gap, and the engine already renders ``NO_DATA``
correctly end to end.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import SliKind, SpanStatus
from app.models.signals import TraceSpan
from app.services.bundle import build_repositories
from app.services.slo import SloEvaluationService
from app.slo.engine import RatioWindow
from app.types import EventPublisher

logger = get_logger("app.workers.slo_evaluation")

_RATIO_KINDS = frozenset({SliKind.AVAILABILITY, SliKind.SUCCESS_RATE, SliKind.ERROR_RATE})


async def _span_ratio_window(
    session: AsyncSession,
    organization_id: UUID,
    service_name: str,
    *,
    start: datetime,
    end: datetime,
) -> RatioWindow:
    """Good/total span counts for one service and window.

    A span is "good" when it did not end in ``ERROR``. ``UNSET`` counts
    as good deliberately: it is OpenTelemetry's default when nothing
    reported a problem, and treating "nobody said it failed" as a failure
    would make every SLO evaluated against unannotated spans look
    permanently unhealthy.
    """
    total_stmt = (
        select(func.count())
        .select_from(TraceSpan)
        .where(
            TraceSpan.organization_id == organization_id,
            TraceSpan.service_name == service_name,
            TraceSpan.started_at >= start,
            TraceSpan.started_at < end,
        )
    )
    bad_stmt = total_stmt.where(TraceSpan.status == SpanStatus.ERROR)
    total = (await session.execute(total_stmt)).scalar_one()
    bad = (await session.execute(bad_stmt)).scalar_one()
    return RatioWindow(
        window_start=start, window_end=end, good_count=total - bad, total_count=total
    )


class SloEvaluationWorker:
    """Evaluates every enabled SLO across every organization."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Evaluate every ratio-kind SLO once, returning how many were evaluated."""
        now = datetime.now(UTC)
        evaluated = 0
        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = SloEvaluationService(repos.slos, repos.slis, publish=self._publish_event)

            for organization_id in await repos.slos.list_organization_ids():
                for slo in await repos.slos.list_enabled(organization_id):
                    if slo.sli_kind not in _RATIO_KINDS:
                        continue
                    fast_start = now - timedelta(hours=slo.fast_burn_hours)
                    slow_start = now - timedelta(hours=slo.slow_burn_hours)
                    window_start = now - timedelta(days=slo.window_days)

                    window = await _span_ratio_window(
                        session, organization_id, slo.service_name, start=window_start, end=now
                    )
                    fast_window = await _span_ratio_window(
                        session, organization_id, slo.service_name, start=fast_start, end=now
                    )
                    slow_window = await _span_ratio_window(
                        session, organization_id, slo.service_name, start=slow_start, end=now
                    )
                    await service.evaluate(
                        slo, window, fast_window=fast_window, slow_window=slow_window, now=now
                    )
                    evaluated += 1
            await session.commit()

        logger.info(
            "SLO evaluation sweep completed", extra={"extra_fields": {"evaluated": evaluated}}
        )
        return evaluated


__all__ = ["SloEvaluationWorker"]
