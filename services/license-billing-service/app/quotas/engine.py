"""Quota classification: warning thresholds, hard/soft/burst
enforcement.

**A soft quota never refuses; a hard quota refuses only past its burst
allowance.** The two limit kinds docs/069 names exist precisely so a
caller can choose "warn but allow" versus "actually enforce," and this
engine keeps that distinction explicit rather than collapsing both into
one boolean.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models.enums import QuotaLimitKind, QuotaPeriod


class QuotaStatus:
    OK = "ok"
    WARNING = "warning"
    EXCEEDED = "exceeded"


def classify_quota_status(used_value: float, limit_value: float, *, warning_fraction: float) -> str:
    """Classify a quota's current standing.

    Raises:
        ValueError: On a negative *used_value*, or a non-positive
            *limit_value*.
    """
    if used_value < 0:
        raise ValueError(f"used_value must be non-negative; got {used_value}.")
    if limit_value <= 0:
        raise ValueError(f"limit_value must be positive; got {limit_value}.")
    if used_value >= limit_value:
        return QuotaStatus.EXCEEDED
    if used_value >= limit_value * warning_fraction:
        return QuotaStatus.WARNING
    return QuotaStatus.OK


def is_request_allowed(
    used_value: float,
    requested_value: float,
    *,
    limit_value: float,
    limit_kind: QuotaLimitKind,
    burst_limit: float | None,
) -> bool:
    """Whether a request for *requested_value* more usage is allowed
    right now.

    A ``SOFT`` quota always allows the request (it only warns). A
    ``HARD`` quota refuses once ``used_value + requested_value`` would
    exceed ``limit_value`` plus any ``burst_limit`` allowance (``None``
    burst means no allowance beyond the limit).

    Raises:
        ValueError: On a negative *used_value*/*requested_value*, or a
            non-positive *limit_value*.
    """
    if used_value < 0 or requested_value < 0:
        raise ValueError("used_value and requested_value must both be non-negative.")
    if limit_value <= 0:
        raise ValueError(f"limit_value must be positive; got {limit_value}.")
    if QuotaLimitKind(limit_kind) == QuotaLimitKind.SOFT:
        return True
    ceiling = limit_value + (burst_limit or 0.0)
    return used_value + requested_value <= ceiling


def _add_months(moment: datetime, months: int) -> datetime:
    """*moment* advanced by *months* whole calendar months, clamped to
    the target month's actual last day (handles the Jan 31 + 1mo case)."""
    total_months = moment.month - 1 + months
    year = moment.year + total_months // 12
    month = total_months % 12 + 1
    day = min(
        moment.day,
        [
            31,
            29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
            31,
            30,
            31,
            30,
            31,
            31,
            30,
            31,
            30,
            31,
        ][month - 1],
    )
    return moment.replace(year=year, month=month, day=day)


def compute_period_window(period: QuotaPeriod, *, now: datetime) -> tuple[datetime, datetime]:
    """The ``[start, end)`` boundaries of the quota period containing
    *now*.

    Each window starts at midnight in *now*'s own timezone, so a quota
    resets on a calendar boundary rather than a rolling duration from
    whenever it happened to be first requested.
    """
    period = QuotaPeriod(period)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == QuotaPeriod.DAILY:
        return start_of_day, start_of_day + timedelta(days=1)
    if period == QuotaPeriod.WEEKLY:
        week_start = start_of_day - timedelta(days=start_of_day.weekday())
        return week_start, week_start + timedelta(days=7)
    if period == QuotaPeriod.MONTHLY:
        month_start = start_of_day.replace(day=1)
        return month_start, _add_months(month_start, 1)
    year_start = start_of_day.replace(month=1, day=1)
    return year_start, year_start.replace(year=year_start.year + 1)


__all__ = ["QuotaStatus", "classify_quota_status", "compute_period_window", "is_request_allowed"]
