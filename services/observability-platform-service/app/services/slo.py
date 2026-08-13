"""SLO evaluation service: turns a stored :class:`Slo` and a counted
window into a persisted :class:`Sli` row via ``app.slo.engine``.

Counting good and total events from raw signals is a separate concern --
what "good" means is encoded in ``Slo.query`` and evaluated by whatever
executes that query against metrics, logs, or traces (a worker, in this
service). This module accepts the count as a :class:`RatioWindow` and is
responsible only for the part that must not be reimplemented ad hoc at
every call site: building a valid :class:`Objective` from stored fields
and running every counted window through the same pure engine.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.events.domain_events import SloBreachedEvent
from app.models.analysis import Sli, Slo
from app.models.enums import SliStatus
from app.repositories.analysis import SliRepository, SloRepository
from app.slo.engine import (
    DEFAULT_AT_RISK_FRACTION,
    Objective,
    RatioWindow,
    classify_status,
    compute_burn_rate,
    compute_error_budget,
    compute_ratio_sli,
    evaluate_burn,
    project_exhaustion,
)
from app.types import EventPublisher

_SOURCE_SERVICE = "observability-platform-service"

_BREACH_STATUSES = frozenset({SliStatus.BREACHING, SliStatus.AT_RISK, SliStatus.EXHAUSTED})
"""Not HEALTHY, not NO_DATA. An all-clear is not the same kind of
notification as an incident, and a consumer paging on this event must
not receive both under one name."""


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


def objective_from_slo(slo: Slo) -> Objective:
    """Build the engine's :class:`Objective` from a stored SLO row.

    The one place a stored SLO's fields become the engine's validated
    input, so an invalid combination (a latency SLO with no threshold, a
    target of exactly 1.0) is rejected the same way regardless of which
    caller is evaluating it.
    """
    return Objective(
        kind=slo.sli_kind,
        target=slo.target,
        latency_threshold_ms=slo.latency_threshold_ms,
        window_days=slo.window_days,
        is_rolling=slo.is_rolling,
    )


class SloEvaluationService:
    """Evaluates one SLO's counted window and persists the result."""

    def __init__(
        self,
        slo_repo: SloRepository,
        sli_repo: SliRepository,
        *,
        publish: EventPublisher = _noop_publisher,
    ) -> None:
        self._slo_repo = slo_repo
        self._sli_repo = sli_repo
        self._publish = publish

    async def evaluate(
        self,
        slo: Slo,
        window: RatioWindow,
        *,
        fast_window: RatioWindow,
        slow_window: RatioWindow,
        now: datetime | None = None,
    ) -> Sli:
        """Run the full engine pipeline for one window and persist an SLI.

        ``fast_window`` and ``slow_window`` are the short and long burn
        windows the multi-window alert needs; they are independent counts
        over their own spans, never derived by slicing ``window``.
        """
        objective = objective_from_slo(slo)
        moment = now or datetime.now(UTC)

        result = compute_ratio_sli(objective, window)
        budget = compute_error_budget(objective, window)
        status = classify_status(
            objective, result, budget, at_risk_fraction=self._at_risk_fraction(slo)
        )
        fast_burn = compute_burn_rate(objective, fast_window, window_hours=slo.fast_burn_hours)
        slow_burn = compute_burn_rate(objective, slow_window, window_hours=slo.slow_burn_hours)
        alert = evaluate_burn(
            fast_burn,
            slow_burn,
            fast_threshold=slo.fast_burn_threshold,
            slow_threshold=slo.slow_burn_threshold,
        )
        exhaustion = (
            project_exhaustion(budget, fast_burn, window_days=slo.window_days, now=moment)
            if budget is not None
            else None
        )

        record = Sli(
            organization_id=slo.organization_id,
            slo_id=slo.id,
            window_start=window.window_start,
            window_end=window.window_end,
            good_count=window.good_count,
            total_count=window.total_count,
            value=result.value,
            # classify_status, not result.status: an exhausted budget must
            # outrank a healthy instantaneous ratio, which is exactly what
            # the raw per-window status cannot see on its own.
            status=status,
            error_budget_total=budget.allowed_bad_events if budget else None,
            error_budget_consumed=budget.actual_bad_events if budget else None,
            error_budget_remaining=budget.remaining_events if budget else None,
            fast_burn_rate=fast_burn.rate,
            slow_burn_rate=slow_burn.rate,
            is_burning=alert.should_alert,
            projected_exhaustion_at=exhaustion,
            computed_at=moment,
            details={
                "reason": result.reason,
                "status": str(status),
                "burn_alert_reason": alert.reason,
            },
        )
        created = await self._sli_repo.create(record)
        if status in _BREACH_STATUSES:
            await self._publish(
                SloBreachedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=slo.organization_id,
                    payload={
                        "slo_id": str(slo.id),
                        "slo_name": slo.name,
                        "service_name": slo.service_name,
                        "sli_id": str(created.id),
                        "status": str(status),
                        "value": result.value,
                        "error_budget_remaining": (budget.remaining_events if budget else None),
                    },
                )
            )
        return created

    @staticmethod
    def _at_risk_fraction(slo: Slo) -> float:
        """Placeholder for a per-SLO override; the engine's own default
        applies when nothing more specific is configured on the row."""
        return DEFAULT_AT_RISK_FRACTION


async def require_slo(slo_repo: SloRepository, organization_id: UUID, slo_id: UUID) -> Slo:
    """Convenience re-export so callers do not need both modules."""
    return await slo_repo.require_in_org(organization_id, slo_id)


__all__ = [
    "SloEvaluationService",
    "objective_from_slo",
    "require_slo",
]
