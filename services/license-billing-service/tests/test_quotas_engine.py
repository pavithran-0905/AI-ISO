"""Tests for app.quotas.engine: quota status classification, request
admission, and period window computation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.models.enums import QuotaLimitKind, QuotaPeriod
from app.quotas.engine import (
    QuotaStatus,
    classify_quota_status,
    compute_period_window,
    is_request_allowed,
)


class TestClassifyQuotaStatus:
    def test_low_usage_is_ok(self) -> None:
        assert classify_quota_status(10, 100, warning_fraction=0.8) == QuotaStatus.OK

    def test_high_usage_is_warning(self) -> None:
        assert classify_quota_status(85, 100, warning_fraction=0.8) == QuotaStatus.WARNING

    def test_at_limit_is_exceeded(self) -> None:
        assert classify_quota_status(100, 100, warning_fraction=0.8) == QuotaStatus.EXCEEDED

    def test_over_limit_is_exceeded(self) -> None:
        assert classify_quota_status(150, 100, warning_fraction=0.8) == QuotaStatus.EXCEEDED

    def test_negative_used_value_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            classify_quota_status(-1, 100, warning_fraction=0.8)

    def test_non_positive_limit_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            classify_quota_status(0, 0, warning_fraction=0.8)


class TestIsRequestAllowed:
    def test_soft_quota_always_allows(self) -> None:
        assert is_request_allowed(
            1_000, 1_000, limit_value=10, limit_kind=QuotaLimitKind.SOFT, burst_limit=None
        )

    def test_hard_quota_allows_within_limit(self) -> None:
        assert is_request_allowed(
            5, 5, limit_value=10, limit_kind=QuotaLimitKind.HARD, burst_limit=None
        )

    def test_hard_quota_refuses_past_limit(self) -> None:
        assert not is_request_allowed(
            8, 5, limit_value=10, limit_kind=QuotaLimitKind.HARD, burst_limit=None
        )

    def test_hard_quota_allows_within_burst(self) -> None:
        assert is_request_allowed(
            9, 3, limit_value=10, limit_kind=QuotaLimitKind.HARD, burst_limit=5
        )

    def test_hard_quota_refuses_past_burst(self) -> None:
        assert not is_request_allowed(
            14, 3, limit_value=10, limit_kind=QuotaLimitKind.HARD, burst_limit=5
        )

    def test_negative_used_value_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            is_request_allowed(
                -1, 1, limit_value=10, limit_kind=QuotaLimitKind.HARD, burst_limit=None
            )

    def test_non_positive_limit_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            is_request_allowed(
                1, 1, limit_value=0, limit_kind=QuotaLimitKind.HARD, burst_limit=None
            )


class TestComputePeriodWindow:
    def test_daily_window(self) -> None:
        now = datetime(2026, 3, 15, 14, 30, tzinfo=UTC)
        start, end = compute_period_window(QuotaPeriod.DAILY, now=now)
        assert start == datetime(2026, 3, 15, tzinfo=UTC)
        assert end == datetime(2026, 3, 16, tzinfo=UTC)

    def test_weekly_window_starts_monday(self) -> None:
        now = datetime(2026, 3, 18, tzinfo=UTC)  # a Wednesday
        start, end = compute_period_window(QuotaPeriod.WEEKLY, now=now)
        assert start.weekday() == 0
        assert (end - start).days == 7
        assert start <= now < end

    def test_monthly_window(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=UTC)
        start, end = compute_period_window(QuotaPeriod.MONTHLY, now=now)
        assert start == datetime(2026, 3, 1, tzinfo=UTC)
        assert end == datetime(2026, 4, 1, tzinfo=UTC)

    def test_monthly_window_rolls_over_year(self) -> None:
        now = datetime(2026, 12, 15, tzinfo=UTC)
        start, end = compute_period_window(QuotaPeriod.MONTHLY, now=now)
        assert start == datetime(2026, 12, 1, tzinfo=UTC)
        assert end == datetime(2027, 1, 1, tzinfo=UTC)

    def test_annual_window(self) -> None:
        now = datetime(2026, 6, 1, tzinfo=UTC)
        start, end = compute_period_window(QuotaPeriod.ANNUAL, now=now)
        assert start == datetime(2026, 1, 1, tzinfo=UTC)
        assert end == datetime(2027, 1, 1, tzinfo=UTC)

    def test_window_always_contains_now(self) -> None:
        now = datetime(2026, 3, 15, 14, 30, tzinfo=UTC)
        for period in QuotaPeriod:
            start, end = compute_period_window(period, now=now)
            assert start <= now < end
