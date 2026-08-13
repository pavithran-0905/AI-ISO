"""Capacity forecasting service: buckets raw samples, runs
``app.capacity.engine``, and persists exactly one :class:`CapacityForecast`
row per run -- a refusal included, never silently dropped.

**A refusal is a row, not an absence.** ``CapacityForecast.refusal_reason``
exists so an operator asking "why is there no forecast for this host"
gets an answer stored beside every forecast that did succeed, rather than
having to infer a refusal from a gap in a list.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from uuid import UUID

from app.capacity.buckets import Sample, bucket_samples
from app.capacity.engine import (
    Forecast,
    ForecastRefused,
    ForecastRequest,
    MetricBound,
    estimate_exhaustion,
    forecast_series,
)
from app.capacity.enums import BoundKind, ConfidenceLevel, ForecastQualifier, ReductionKind
from app.models.analysis import CapacityForecast
from app.models.enums import ForecastQuality, ResourceKind
from app.repositories.analysis import CapacityForecastRepository

_DEGRADED_QUALIFIERS = frozenset(
    {
        ForecastQualifier.LOW_EXPLANATORY_POWER,
    }
)
_FAIR_QUALIFIERS = frozenset(
    {
        ForecastQualifier.OUTLIER_SENSITIVE,
        ForecastQualifier.HIGH_INFLUENCE_POINTS,
        ForecastQualifier.SHORT_HISTORY,
        ForecastQualifier.SEASONALITY_UNASSESSED,
    }
)


def _quality_for(forecast: Forecast) -> ForecastQuality:
    """Map the engine's qualifiers onto the stored quality column.

    A forecast whose slope is real but whose fit barely explains the
    noise (``LOW_EXPLANATORY_POWER``) is the case
    :class:`CapacityForecast`'s docstring calls ``UNRELIABLE`` -- distinct
    from a plain refusal, because the remedy differs: this one needs a
    different model or question, not more time.
    """
    if _DEGRADED_QUALIFIERS & set(forecast.qualifiers):
        return ForecastQuality.UNRELIABLE
    if _FAIR_QUALIFIERS & set(forecast.qualifiers):
        return ForecastQuality.FAIR
    return ForecastQuality.GOOD


class CapacityForecastService:
    """Forecasts one resource and persists the outcome."""

    def __init__(self, repo: CapacityForecastRepository) -> None:
        self._repo = repo

    async def forecast_resource(
        self,
        organization_id: UUID,
        *,
        service_name: str | None,
        environment: str | None,
        resource_kind: ResourceKind,
        metric_name: str | None,
        unit: str | None,
        samples: Sequence[tuple[datetime, float]],
        bucket: timedelta,
        horizon_days: int,
        reduction: ReductionKind,
        ceiling: float | None = None,
        bound_kind: BoundKind = BoundKind.SOFT_TARGET,
        confidence: ConfidenceLevel = ConfidenceLevel.NINETY,
        generated_at: datetime,
    ) -> CapacityForecast:
        """Bucket, fit, project, and persist -- one row either way."""
        raw = [Sample(at=at, value=value) for at, value in samples]
        history_start = min((s.at for s in raw), default=generated_at)
        buckets = bucket_samples(raw, bucket=bucket, origin=history_start)

        bound = (
            MetricBound(upper=ceiling, kind=bound_kind) if ceiling is not None else MetricBound()
        )
        request = ForecastRequest(
            points=buckets,
            reduction=reduction,
            bucket=bucket,
            horizon_buckets=max(1, int(horizon_days * timedelta(days=1) / bucket)),
            confidence=confidence,
            bound=bound,
        )
        outcome = forecast_series(request)

        if isinstance(outcome, ForecastRefused):
            return await self._repo.create(
                CapacityForecast(
                    organization_id=organization_id,
                    service_name=service_name,
                    environment=environment,
                    resource_kind=resource_kind,
                    metric_name=metric_name,
                    unit=unit,
                    generated_at=generated_at,
                    history_start=history_start,
                    history_end=buckets[-1].bucket_start if buckets else history_start,
                    history_sample_count=len(raw),
                    horizon_days=horizon_days,
                    quality=ForecastQuality.INSUFFICIENT,
                    forecast_basis=str(reduction),
                    refusal_reason=f"{outcome.reason!s}: {outcome.remedy}",
                )
            )

        exhaustion = estimate_exhaustion(outcome, ceiling=ceiling) if ceiling is not None else None
        horizon_point = outcome.at_horizon()
        return await self._repo.create(
            CapacityForecast(
                organization_id=organization_id,
                service_name=service_name,
                environment=environment,
                resource_kind=resource_kind,
                metric_name=metric_name,
                unit=unit,
                generated_at=generated_at,
                history_start=history_start,
                history_end=buckets[-1].bucket_start if buckets else history_start,
                history_sample_count=outcome.evidence.n_usable,
                horizon_days=horizon_days,
                quality=_quality_for(outcome),
                r_squared=outcome.evidence.r_squared,
                slope_per_day=outcome.fit.slope / (bucket.total_seconds() / 86400.0),
                intercept=outcome.fit.intercept,
                residual_std=outcome.fit.residual_std,
                current_value=outcome.last_observed_value,
                forecast_value=horizon_point.value if horizon_point else None,
                forecast_low=horizon_point.interval.lower if horizon_point else None,
                forecast_high=horizon_point.interval.upper if horizon_point else None,
                ceiling=ceiling,
                days_until_exhaustion=exhaustion.days_point if exhaustion else None,
                exhaustion_at=exhaustion.exhaustion_at if exhaustion else None,
                forecast_basis=str(reduction),
                refusal_reason=None,
                points=[
                    {
                        "at": point.at.isoformat(),
                        "value": point.value,
                        "value_raw": point.value_raw,
                        "low": point.interval.lower,
                        "high": point.interval.upper,
                    }
                    for point in outcome.points
                ],
                details={
                    "trend_class": str(outcome.trend_class),
                    "validity": str(outcome.validity),
                    "qualifiers": [str(q) for q in outcome.qualifiers],
                    "exhaustion_status": str(exhaustion.status) if exhaustion else None,
                },
            )
        )


__all__ = ["CapacityForecastService"]
