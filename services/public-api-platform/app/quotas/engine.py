"""Quota period-window computation and consumption checks."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models.enums import QuotaResetPolicy

_DAYS_PER_WEEK = 7
_DECEMBER = 12


def _add_months(value: datetime, months: int) -> datetime:
    """Add *months* calendar months to *value*, clamping the day into
    the target month's own valid range (Jan 31 + 1 month -> Feb 28/29,
    never a raw ``ValueError`` from a nonexistent Feb 31)."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, _days_in_month(year, month))
    return value.replace(year=year, month=month, day=day)


def _days_in_month(year: int, month: int) -> int:
    next_month_start = (
        datetime(year + 1, 1, 1) if month == _DECEMBER else datetime(year, month + 1, 1)
    )
    return (next_month_start - datetime(year, month, 1)).days


def compute_period_window(
    reset_policy: QuotaResetPolicy, *, now: datetime
) -> tuple[datetime, datetime]:
    """The current reset period's ``[start, end)`` for *reset_policy*,
    anchored to *now*'s own calendar day (never the current
    in-progress instant, so a quota window is always a whole day/week/
    month)."""
    reset_policy = QuotaResetPolicy(reset_policy)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if reset_policy == QuotaResetPolicy.DAILY:
        return day_start, day_start + timedelta(days=1)
    if reset_policy == QuotaResetPolicy.WEEKLY:
        week_start = day_start - timedelta(days=day_start.weekday())
        return week_start, week_start + timedelta(days=_DAYS_PER_WEEK)
    month_start = day_start.replace(day=1)
    return month_start, _add_months(month_start, 1)


def is_quota_exceeded(*, used_value: int, limit_value: int) -> bool:
    """Whether consumption has reached or exceeded the quota's own
    limit."""
    return used_value >= limit_value


def is_quota_warning(*, used_value: int, limit_value: int, threshold_percent: float) -> bool:
    """Whether consumption has crossed the warning threshold but has
    not yet exceeded the limit -- the point at which "Quota Warning"
    should be notified, distinct from actually being exceeded."""
    if limit_value <= 0:
        return False
    if is_quota_exceeded(used_value=used_value, limit_value=limit_value):
        return False
    return (used_value / limit_value) * 100 >= threshold_percent


__all__ = [
    "compute_period_window",
    "is_quota_exceeded",
    "is_quota_warning",
]
