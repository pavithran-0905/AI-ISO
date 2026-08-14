"""Tests for app.analytics.engine: rates with an honest denominator."""

from __future__ import annotations

import pytest

from app.analytics.engine import compute_availability_fraction, success_rate


class TestSuccessRate:
    def test_computes_fraction(self) -> None:
        assert success_rate(8, 2) == 0.8

    def test_no_attempts_is_none(self) -> None:
        assert success_rate(0, 0) is None

    def test_negative_succeeded_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            success_rate(-1, 0)

    def test_negative_failed_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            success_rate(0, -1)


class TestComputeAvailabilityFraction:
    def test_computes_fraction(self) -> None:
        assert compute_availability_fraction(9, 10) == 0.9

    def test_no_checks_is_none(self) -> None:
        assert compute_availability_fraction(0, 0) is None

    def test_negative_healthy_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_availability_fraction(-1, 10)

    def test_negative_total_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_availability_fraction(1, -10)

    def test_healthy_exceeding_total_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot exceed"):
            compute_availability_fraction(10, 5)
