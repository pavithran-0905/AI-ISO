"""Tests for app.analytics.engine: fleet rates with an honest denominator."""

from __future__ import annotations

import pytest

from app.analytics.engine import ComplianceRate, fleet_availability, success_rate


class TestSuccessRate:
    def test_zero_attempts_is_none(self) -> None:
        assert success_rate(0, 0) is None

    def test_mixed(self) -> None:
        assert success_rate(3, 1) == 0.75

    def test_all_succeeded(self) -> None:
        assert success_rate(5, 0) == 1.0

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            success_rate(-1, 0)


class TestComplianceRate:
    def test_excludes_not_assessed_from_rate(self) -> None:
        rate = ComplianceRate(compliant=3, non_compliant=1, not_assessed=100)
        assert rate.rate == 0.75

    def test_zero_assessed_rate_is_none(self) -> None:
        rate = ComplianceRate(compliant=0, non_compliant=0, not_assessed=10)
        assert rate.rate is None


class TestFleetAvailability:
    def test_zero_total_is_none(self) -> None:
        assert fleet_availability(0, 0) is None

    def test_partial_availability(self) -> None:
        assert fleet_availability(8, 10) == 0.8

    def test_full_availability(self) -> None:
        assert fleet_availability(10, 10) == 1.0

    def test_healthy_exceeding_total_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot exceed"):
            fleet_availability(11, 10)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            fleet_availability(-1, 10)
