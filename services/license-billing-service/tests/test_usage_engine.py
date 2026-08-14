"""Tests for app.usage.engine: usage aggregation and overage
calculation."""

from __future__ import annotations

import pytest

from app.usage.engine import aggregate_quantities, compute_overage


class TestAggregateQuantities:
    def test_sums_quantities(self) -> None:
        assert aggregate_quantities([1.0, 2.0, 3.5]) == 6.5

    def test_empty_sequence_is_zero(self) -> None:
        assert aggregate_quantities([]) == 0.0


class TestComputeOverage:
    def test_under_limit_is_zero(self) -> None:
        assert compute_overage(total_usage=5.0, limit_value=10.0) == 0.0

    def test_over_limit_is_the_difference(self) -> None:
        assert compute_overage(total_usage=15.0, limit_value=10.0) == 5.0

    def test_exactly_at_limit_is_zero(self) -> None:
        assert compute_overage(total_usage=10.0, limit_value=10.0) == 0.0

    def test_negative_usage_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_overage(total_usage=-1.0, limit_value=10.0)

    def test_negative_limit_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_overage(total_usage=1.0, limit_value=-10.0)
