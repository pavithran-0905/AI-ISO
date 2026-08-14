"""Tests for app.capacity.engine: utilization, severity, growth rate."""

from __future__ import annotations

import pytest

from app.capacity.engine import (
    CapacitySeverity,
    classify_utilization,
    compute_utilization,
    growth_rate,
)


class TestComputeUtilization:
    def test_zero_total_is_none(self) -> None:
        assert compute_utilization(0, 0) is None

    def test_half_used(self) -> None:
        assert compute_utilization(100, 50) == 0.5

    def test_fully_used(self) -> None:
        assert compute_utilization(100, 100) == 1.0

    def test_negative_total_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_utilization(-1, 0)

    def test_negative_used_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_utilization(10, -1)


class TestClassifyUtilization:
    def test_none_is_unknown(self) -> None:
        result = classify_utilization(None, warning_threshold=0.8, critical_threshold=0.9)
        assert result.severity == CapacitySeverity.UNKNOWN

    def test_low_is_ok(self) -> None:
        result = classify_utilization(0.3, warning_threshold=0.8, critical_threshold=0.9)
        assert result.severity == CapacitySeverity.OK

    def test_at_warning_threshold(self) -> None:
        result = classify_utilization(0.8, warning_threshold=0.8, critical_threshold=0.9)
        assert result.severity == CapacitySeverity.WARNING

    def test_at_critical_threshold(self) -> None:
        result = classify_utilization(0.9, warning_threshold=0.8, critical_threshold=0.9)
        assert result.severity == CapacitySeverity.CRITICAL

    def test_invalid_threshold_ordering_raises(self) -> None:
        with pytest.raises(ValueError, match="must exceed"):
            classify_utilization(0.5, warning_threshold=0.9, critical_threshold=0.9)


class TestGrowthRate:
    def test_zero_previous_is_none(self) -> None:
        assert growth_rate(100, 0) is None

    def test_growth(self) -> None:
        assert growth_rate(150, 100) == 0.5

    def test_shrinkage(self) -> None:
        assert growth_rate(50, 100) == -0.5
