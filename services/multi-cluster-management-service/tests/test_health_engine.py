"""Tests for app.health.engine: component health aggregation and staleness."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.health.engine import ComponentReading, aggregate_health, is_stale
from app.models.enums import ClusterComponent as C
from app.models.enums import ClusterHealthStatus as Health
from app.models.enums import ComponentHealthStatus as Comp

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


class TestAggregateHealth:
    def test_no_readings_is_unknown_never_healthy(self) -> None:
        result = aggregate_health([], degraded_threshold=1, unhealthy_threshold=2)
        assert result.overall is Health.UNKNOWN
        assert result.total_count == 0

    def test_all_ok_is_healthy(self) -> None:
        readings = [
            ComponentReading(C.API_SERVER, Comp.OK),
            ComponentReading(C.ETCD, Comp.OK),
        ]
        result = aggregate_health(readings, degraded_threshold=1, unhealthy_threshold=2)
        assert result.overall is Health.HEALTHY

    def test_one_warning_below_threshold_still_degraded(self) -> None:
        readings = [ComponentReading(C.API_SERVER, Comp.WARNING)]
        result = aggregate_health(readings, degraded_threshold=1, unhealthy_threshold=2)
        assert result.overall is Health.DEGRADED
        assert result.warning_count == 1

    def test_critical_count_meets_unhealthy_threshold(self) -> None:
        readings = [
            ComponentReading(C.API_SERVER, Comp.CRITICAL),
            ComponentReading(C.ETCD, Comp.CRITICAL),
        ]
        result = aggregate_health(readings, degraded_threshold=1, unhealthy_threshold=2)
        assert result.overall is Health.UNHEALTHY
        assert result.critical_count == 2

    def test_single_critical_below_unhealthy_threshold_is_degraded(self) -> None:
        readings = [ComponentReading(C.API_SERVER, Comp.CRITICAL)]
        result = aggregate_health(readings, degraded_threshold=1, unhealthy_threshold=2)
        assert result.overall is Health.DEGRADED

    def test_unknown_reading_counts_toward_neither_threshold(self) -> None:
        readings = [ComponentReading(C.API_SERVER, Comp.UNKNOWN)]
        result = aggregate_health(readings, degraded_threshold=1, unhealthy_threshold=2)
        assert result.overall is Health.HEALTHY


class TestIsStale:
    def test_never_seen_is_stale(self) -> None:
        assert is_stale(None, now=NOW, threshold_minutes=15)

    def test_recent_is_not_stale(self) -> None:
        assert not is_stale(NOW - timedelta(minutes=5), now=NOW, threshold_minutes=15)

    def test_old_is_stale(self) -> None:
        assert is_stale(NOW - timedelta(minutes=20), now=NOW, threshold_minutes=15)

    def test_exactly_at_threshold_not_yet_stale(self) -> None:
        assert not is_stale(NOW - timedelta(minutes=15), now=NOW, threshold_minutes=15)
