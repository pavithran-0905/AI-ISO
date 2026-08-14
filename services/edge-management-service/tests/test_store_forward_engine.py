"""Tests for app.store_forward.engine: retry backoff and queue overflow."""

from __future__ import annotations

import pytest

from app.store_forward.engine import compute_backoff_seconds, should_drop_message


class TestComputeBackoffSeconds:
    def test_first_attempt_uses_base_delay(self) -> None:
        assert compute_backoff_seconds(0, base_seconds=5.0, max_seconds=3600.0) == 5.0

    def test_grows_exponentially(self) -> None:
        assert compute_backoff_seconds(3, base_seconds=5.0, max_seconds=3600.0) == 40.0

    def test_capped_at_max_seconds(self) -> None:
        assert compute_backoff_seconds(20, base_seconds=5.0, max_seconds=3600.0) == 3600.0

    def test_negative_attempt_count_raises(self) -> None:
        with pytest.raises(ValueError, match="attempt_count"):
            compute_backoff_seconds(-1, base_seconds=5.0, max_seconds=3600.0)

    def test_non_positive_base_seconds_raises(self) -> None:
        with pytest.raises(ValueError, match="base_seconds"):
            compute_backoff_seconds(0, base_seconds=0.0, max_seconds=3600.0)

    def test_non_positive_max_seconds_raises(self) -> None:
        with pytest.raises(ValueError, match="base_seconds"):
            compute_backoff_seconds(0, base_seconds=5.0, max_seconds=0.0)

    def test_returns_a_float(self) -> None:
        result = compute_backoff_seconds(2, base_seconds=1.0, max_seconds=100.0)
        assert isinstance(result, float)


class TestShouldDropMessage:
    def test_under_capacity_does_not_drop(self) -> None:
        assert not should_drop_message(5, max_queue_depth=10)

    def test_at_capacity_drops(self) -> None:
        assert should_drop_message(10, max_queue_depth=10)

    def test_over_capacity_drops(self) -> None:
        assert should_drop_message(11, max_queue_depth=10)

    def test_non_positive_max_queue_depth_raises(self) -> None:
        with pytest.raises(ValueError, match="max_queue_depth"):
            should_drop_message(0, max_queue_depth=0)
