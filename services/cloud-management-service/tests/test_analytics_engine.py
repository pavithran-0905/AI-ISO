"""Tests for app.analytics.engine: rates with an honest zero-denominator."""

from __future__ import annotations

import pytest

from app.analytics.engine import compliance_rate, success_rate


class TestSuccessRate:
    def test_all_succeeded(self) -> None:
        assert success_rate(10, 0) == 1.0

    def test_all_failed(self) -> None:
        assert success_rate(0, 10) == 0.0

    def test_zero_attempts_is_none(self) -> None:
        assert success_rate(0, 0) is None

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            success_rate(-1, 0)


class TestComplianceRate:
    def test_all_compliant(self) -> None:
        assert compliance_rate(10, 10) == 1.0

    def test_none_compliant(self) -> None:
        assert compliance_rate(0, 10) == 0.0

    def test_zero_total_is_none(self) -> None:
        assert compliance_rate(0, 0) is None

    def test_compliant_exceeding_total_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot exceed"):
            compliance_rate(11, 10)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compliance_rate(-1, 10)
