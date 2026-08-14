"""Tests for app.analytics.engine: rates with an honest zero-denominator."""

from __future__ import annotations

import pytest

from app.analytics.engine import fleet_availability, success_rate


class TestSuccessRate:
    def test_all_succeeded(self) -> None:
        assert success_rate(10, 0) == 1.0

    def test_all_failed(self) -> None:
        assert success_rate(0, 10) == 0.0

    def test_mixed(self) -> None:
        assert success_rate(3, 1) == 0.75

    def test_zero_attempts_is_none(self) -> None:
        assert success_rate(0, 0) is None

    def test_negative_succeeded_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            success_rate(-1, 0)

    def test_negative_failed_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            success_rate(0, -1)


class TestFleetAvailability:
    def test_all_online(self) -> None:
        assert fleet_availability(10, 10) == 1.0

    def test_none_online(self) -> None:
        assert fleet_availability(0, 10) == 0.0

    def test_zero_total_is_none(self) -> None:
        assert fleet_availability(0, 0) is None

    def test_online_exceeding_total_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot exceed"):
            fleet_availability(11, 10)

    def test_negative_values_raise(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            fleet_availability(-1, 10)
