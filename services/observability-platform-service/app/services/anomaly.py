"""Anomaly detection service: runs ``app.anomaly.engine`` over a series'
recent samples and persists what it finds, without duplicating a
detection an overlapping sweep already recorded.

**Every sweep re-evaluates a window that overlaps the previous one.** The
detector's baseline needs history from before the window nominally under
test, so two consecutive sweeps a minute apart share almost all of their
input. Persisting every detection blindly would write the same anomaly
twice; :meth:`AnomalyDetectionRepository.find_existing` is the guard.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.anomaly.engine import (
    DEFAULT_ROBUST_THRESHOLD,
    Detection,
    DetectionOutcome,
    Point,
    classify_shape,
    detect_statistical,
    merge_outcomes,
)
from app.events.domain_events import AnomalyDetectedEvent
from app.models.analysis import AnomalyDetection
from app.repositories.analysis import AnomalyDetectionRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "observability-platform-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


def points_from_metrics(rows: Sequence[tuple[datetime, float]]) -> tuple[Point, ...]:
    """Adapt raw ``(occurred_at, value)`` pairs to the engine's input type."""
    return tuple(Point(at=at, value=value) for at, value in rows)


class AnomalyDetectionService:
    """Detects and persists anomalies for one metric series."""

    def __init__(
        self, repo: AnomalyDetectionRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def sweep_series(
        self,
        organization_id: UUID,
        *,
        metric_series_id: UUID,
        metric_name: str,
        service_name: str | None,
        environment: str | None,
        points: Sequence[Point],
        threshold: float = DEFAULT_ROBUST_THRESHOLD,
    ) -> tuple[AnomalyDetection, ...]:
        """Run statistical detection over *points* and persist new findings.

        Returns only the detections newly persisted in this call --
        already-recorded ones are skipped silently, not returned as if
        freshly found, so a caller counting "new anomalies this sweep"
        gets an honest count.
        """
        outcome = detect_statistical(points, threshold=threshold)
        if not outcome.could_evaluate:
            return ()

        shapes = {verdict.start: verdict for verdict in classify_shape(points, outcome.detections)}
        persisted: list[AnomalyDetection] = []
        for detection in outcome.detections:
            existing = await self._repo.find_existing(
                organization_id,
                metric_series_id=metric_series_id,
                occurred_at=detection.at,
                method=detection.method,
            )
            if existing is not None:
                continue
            shape_verdict = shapes.get(detection.at)
            row = await self._repo.create(
                AnomalyDetection(
                    organization_id=organization_id,
                    metric_series_id=metric_series_id,
                    metric_name=metric_name,
                    service_name=service_name,
                    environment=environment,
                    detected_at=detection.at,
                    occurred_at=detection.at,
                    window_start=points[0].at if points else None,
                    window_end=points[-1].at if points else None,
                    method=detection.method,
                    shape=shape_verdict.shape if shape_verdict else detection.shape,
                    severity=detection.severity,
                    observed_value=detection.observed,
                    expected_value=detection.expected,
                    expected_low=detection.expected_low,
                    expected_high=detection.expected_high,
                    deviation=detection.deviation,
                    baseline_sample_count=detection.baseline_sample_count,
                    rationale=detection.rationale,
                )
            )
            persisted.append(row)
            await self._publish(
                AnomalyDetectedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=organization_id,
                    payload={
                        "detection_id": str(row.id),
                        "metric_series_id": str(metric_series_id) if metric_series_id else None,
                        "service_name": service_name,
                        "severity": str(row.severity),
                        "method": str(row.method),
                        "deviation": row.deviation,
                    },
                )
            )
        return tuple(persisted)


def merge_and_summarize(*outcomes: DetectionOutcome) -> tuple[Detection, ...]:
    """Combine several detection passes' results for a caller that ran
    statistical, seasonal, and threshold detection over the same series
    and wants one deduplicated list."""
    return tuple(merge_outcomes(*outcomes).detections)


__all__ = [
    "AnomalyDetectionService",
    "merge_and_summarize",
    "points_from_metrics",
]
