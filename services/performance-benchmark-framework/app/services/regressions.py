"""Recording a detected performance regression.

Severity is always computed here, from the same magnitude the caller
used to decide a regression occurred (see
``app.regression.engine.regression_magnitude_percent``) -- never
trusted as a caller-supplied value, so a worker cannot record an
inconsistent severity for the regression it just detected.
"""

from __future__ import annotations

from uuid import UUID

from app.events.domain_events import RegressionDetectedEvent
from app.models.enums import RegressionType
from app.models.regressions import PerformanceRegression
from app.regression.engine import classify_severity
from app.repositories.regressions import PerformanceRegressionRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "performance-benchmark-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class PerformanceRegressionService:
    def __init__(
        self, repo: PerformanceRegressionRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def record(
        self,
        organization_id: UUID,
        *,
        regression_type: RegressionType,
        metric_name: str,
        baseline_value: float,
        current_value: float,
        regression_percent: float,
        critical_threshold_percent: float,
    ) -> PerformanceRegression:
        severity = classify_severity(
            regression_percent=regression_percent,
            critical_threshold_percent=critical_threshold_percent,
        )
        regression = await self._repo.create(
            PerformanceRegression(
                organization_id=organization_id,
                regression_type=regression_type,
                metric_name=metric_name,
                baseline_value=baseline_value,
                current_value=current_value,
                regression_percent=regression_percent,
                severity=severity,
            )
        )
        await self._publish(
            RegressionDetectedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "performance_regression_id": str(regression.id),
                    "metric_name": metric_name,
                    "severity": str(severity),
                },
            )
        )
        return regression


__all__ = ["PerformanceRegressionService"]
