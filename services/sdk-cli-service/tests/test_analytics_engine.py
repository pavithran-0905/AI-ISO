"""Tests for app.analytics.engine: adoption analytics with an honest
denominator."""

from __future__ import annotations

import pytest

from app.analytics.engine import adoption_share, success_rate


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


class TestAdoptionShare:
    def test_computes_fraction(self) -> None:
        assert adoption_share(3, 10) == 0.3

    def test_no_downloads_is_none(self) -> None:
        assert adoption_share(0, 0) is None

    def test_negative_language_count_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            adoption_share(-1, 10)

    def test_negative_total_count_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            adoption_share(1, -10)

    def test_language_exceeding_total_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot exceed"):
            adoption_share(10, 5)
