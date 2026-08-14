"""Statistics aggregation for ``GET /mobile/statistics``.

Computed live from raw telemetry/analytics events for the requested
window, rather than from a separately maintained rollup table -- there
is no ``mobile_statistics`` table among docs/072's fourteen, so an
on-demand aggregation over the raw event tables is the only shape that
matches the spec.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.analytics.engine import (
    average_session_duration,
    distinct_user_count,
    success_rate,
)
from app.analytics.engine import (
    crash_rate as compute_crash_rate,
)
from app.analytics.engine import (
    engagement_rate as compute_engagement_rate,
)
from app.analytics.engine import (
    offline_usage_ratio as compute_offline_usage_ratio,
)
from app.models.enums import AnalyticsMetricType, TelemetryMetricType
from app.repositories.telemetry import (
    MobileAnalyticsEventRepository,
    MobileTelemetryEventRepository,
)


@dataclass(frozen=True, slots=True)
class StatisticsSnapshot:
    window_start: datetime
    window_end: datetime
    daily_active_users: int
    session_count: int
    average_session_duration_seconds: float
    crash_count: int
    crash_rate: float
    offline_usage_ratio: float
    notification_engagement_rate: float
    sync_success_rate: float


class StatisticsService:
    def __init__(
        self,
        analytics_repo: MobileAnalyticsEventRepository,
        telemetry_repo: MobileTelemetryEventRepository,
    ) -> None:
        self._analytics = analytics_repo
        self._telemetry = telemetry_repo

    async def compute(
        self, organization_id: UUID, *, since: datetime, until: datetime
    ) -> StatisticsSnapshot:
        analytics_events = await self._analytics.list_since(organization_id, since=since)
        analytics_events = [event for event in analytics_events if event.recorded_at < until]
        telemetry_events = await self._telemetry.list_since(organization_id, since=since)
        telemetry_events = [event for event in telemetry_events if event.recorded_at < until]

        daily_active_users = distinct_user_count([event.user_id for event in analytics_events])

        session_values = [
            event.value
            for event in analytics_events
            if event.metric_type == AnalyticsMetricType.SESSION_DURATION
        ]
        session_count = len(session_values)
        avg_session_duration = average_session_duration(session_values)

        crash_count = sum(
            1 for event in telemetry_events if event.metric_type == TelemetryMetricType.CRASH
        )
        computed_crash_rate = compute_crash_rate(crash_count, max(session_count, 1))

        offline_count = sum(
            1
            for event in analytics_events
            if event.metric_type == AnalyticsMetricType.OFFLINE_USAGE
        )
        offline_ratio = compute_offline_usage_ratio(offline_count, max(len(analytics_events), 1))

        engagement_values = [
            event.value
            for event in analytics_events
            if event.metric_type == AnalyticsMetricType.NOTIFICATION_ENGAGEMENT
        ]
        engagement_rate_value = compute_engagement_rate(
            int(sum(engagement_values)), max(len(engagement_values), 1)
        )

        sync_values = [
            event.value
            for event in analytics_events
            if event.metric_type == AnalyticsMetricType.SYNC_STATISTICS
        ]
        sync_success = success_rate(int(sum(sync_values)), max(len(sync_values), 1))

        return StatisticsSnapshot(
            window_start=since,
            window_end=until,
            daily_active_users=daily_active_users,
            session_count=session_count,
            average_session_duration_seconds=avg_session_duration,
            crash_count=crash_count,
            crash_rate=computed_crash_rate,
            offline_usage_ratio=offline_ratio,
            notification_engagement_rate=engagement_rate_value,
            sync_success_rate=sync_success,
        )


__all__ = ["StatisticsService", "StatisticsSnapshot"]
