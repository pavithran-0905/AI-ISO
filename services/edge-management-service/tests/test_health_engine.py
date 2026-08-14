"""Tests for app.health.engine: device health aggregation."""

from __future__ import annotations

from app.health.engine import ComponentReading, aggregate_health
from app.models.enums import ComponentHealthStatus as Status
from app.models.enums import DeviceComponent as C
from app.models.enums import DeviceHealthStatus as Health


class TestAggregateHealth:
    def test_no_readings_is_unknown(self) -> None:
        result = aggregate_health([], degraded_threshold=1, unhealthy_threshold=2)
        assert result.overall == Health.UNKNOWN
        assert result.total_count == 0

    def test_all_ok_is_healthy(self) -> None:
        readings = [
            ComponentReading(component=C.CPU, status=Status.OK),
            ComponentReading(component=C.MEMORY, status=Status.OK),
        ]
        result = aggregate_health(readings, degraded_threshold=1, unhealthy_threshold=2)
        assert result.overall == Health.HEALTHY

    def test_one_warning_below_threshold_is_still_healthy(self) -> None:
        readings = [ComponentReading(component=C.CPU, status=Status.WARNING)]
        result = aggregate_health(readings, degraded_threshold=2, unhealthy_threshold=3)
        assert result.overall == Health.HEALTHY

    def test_warning_at_threshold_is_degraded(self) -> None:
        readings = [ComponentReading(component=C.CPU, status=Status.WARNING)]
        result = aggregate_health(readings, degraded_threshold=1, unhealthy_threshold=2)
        assert result.overall == Health.DEGRADED
        assert result.warning_count == 1

    def test_critical_at_threshold_is_unhealthy(self) -> None:
        readings = [
            ComponentReading(component=C.CPU, status=Status.CRITICAL),
            ComponentReading(component=C.MEMORY, status=Status.CRITICAL),
        ]
        result = aggregate_health(readings, degraded_threshold=1, unhealthy_threshold=2)
        assert result.overall == Health.UNHEALTHY
        assert result.critical_count == 2

    def test_string_status_values_are_compared_safely(self) -> None:
        """A reading built from a freshly materialized row carries a
        plain ``str`` for its status column, not the enum instance."""
        readings = [ComponentReading(component=C.CPU, status="critical")]  # type: ignore[arg-type]
        result = aggregate_health(readings, degraded_threshold=1, unhealthy_threshold=1)
        assert result.overall == Health.UNHEALTHY
