"""Tests for app.analytics.engine: success rates, compliance rates, growth rate."""

from __future__ import annotations

import pytest

from app.analytics.engine import ComplianceRate, storage_growth_rate, success_rate


class TestSuccessRate:
    def test_zero_attempts_is_none(self) -> None:
        assert success_rate(0, 0) is None

    def test_all_succeeded(self) -> None:
        assert success_rate(10, 0) == 1.0

    def test_all_failed(self) -> None:
        assert success_rate(0, 10) == 0.0

    def test_mixed(self) -> None:
        assert success_rate(3, 1) == 0.75

    def test_negative_succeeded_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            success_rate(-1, 0)

    def test_negative_failed_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            success_rate(0, -1)


class TestComplianceRate:
    def test_rate_excludes_not_measured(self) -> None:
        rate = ComplianceRate(met=3, violated=1, not_measured=100)
        assert rate.rate == 0.75

    def test_zero_measured_rate_is_none(self) -> None:
        rate = ComplianceRate(met=0, violated=0, not_measured=5)
        assert rate.rate is None

    def test_all_met(self) -> None:
        rate = ComplianceRate(met=5, violated=0, not_measured=0)
        assert rate.rate == 1.0


class TestStorageGrowthRate:
    def test_zero_previous_is_none(self) -> None:
        assert storage_growth_rate(1000, 0) is None

    def test_growth(self) -> None:
        assert storage_growth_rate(1500, 1000) == 0.5

    def test_shrinkage(self) -> None:
        assert storage_growth_rate(500, 1000) == -0.5

    def test_no_change(self) -> None:
        assert storage_growth_rate(1000, 1000) == 0.0
