"""Tests for app.diagnostics.engine: latency classification and
overall status aggregation."""

from __future__ import annotations

import pytest

from app.diagnostics.engine import aggregate_overall_status, classify_latency_status
from app.models.enums import HealthCheckStatus


class TestClassifyLatencyStatus:
    def test_low_latency_is_healthy(self) -> None:
        assert (
            classify_latency_status(10, warning_ms=100, critical_ms=500)
            == HealthCheckStatus.HEALTHY
        )

    def test_mid_latency_is_degraded(self) -> None:
        assert (
            classify_latency_status(200, warning_ms=100, critical_ms=500)
            == HealthCheckStatus.DEGRADED
        )

    def test_high_latency_is_unhealthy(self) -> None:
        assert (
            classify_latency_status(600, warning_ms=100, critical_ms=500)
            == HealthCheckStatus.UNHEALTHY
        )

    def test_none_latency_is_unknown(self) -> None:
        assert (
            classify_latency_status(None, warning_ms=100, critical_ms=500)
            == HealthCheckStatus.UNKNOWN
        )

    def test_negative_latency_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            classify_latency_status(-1, warning_ms=100, critical_ms=500)

    def test_critical_not_greater_than_warning_raises(self) -> None:
        with pytest.raises(ValueError, match="greater than"):
            classify_latency_status(10, warning_ms=500, critical_ms=500)


class TestAggregateOverallStatus:
    def test_empty_is_unknown(self) -> None:
        assert aggregate_overall_status([]) == HealthCheckStatus.UNKNOWN

    def test_all_healthy_is_healthy(self) -> None:
        assert (
            aggregate_overall_status([HealthCheckStatus.HEALTHY, HealthCheckStatus.HEALTHY])
            == HealthCheckStatus.HEALTHY
        )

    def test_worst_of_wins(self) -> None:
        assert (
            aggregate_overall_status([HealthCheckStatus.HEALTHY, HealthCheckStatus.DEGRADED])
            == HealthCheckStatus.DEGRADED
        )

    def test_unhealthy_dominates(self) -> None:
        assert (
            aggregate_overall_status(
                [HealthCheckStatus.HEALTHY, HealthCheckStatus.DEGRADED, HealthCheckStatus.UNHEALTHY]
            )
            == HealthCheckStatus.UNHEALTHY
        )

    def test_unknown_is_worse_than_healthy(self) -> None:
        assert (
            aggregate_overall_status([HealthCheckStatus.HEALTHY, HealthCheckStatus.UNKNOWN])
            == HealthCheckStatus.UNKNOWN
        )
