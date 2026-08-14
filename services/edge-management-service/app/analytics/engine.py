"""Fleet analytics: rates with an honest denominator.

**A rate with a zero denominator is `None`, never `0.0` or `1.0`.** Zero
updates attempted in a window is not a 0% success rate (nothing failed)
and not a 100% one (nothing succeeded either) -- it is a window with no
evidence.
"""

from __future__ import annotations


def success_rate(succeeded: int, failed: int) -> float | None:
    """The fraction of attempts that succeeded, or ``None`` with no
    attempts.

    Raises:
        ValueError: On a negative count, which cannot be a real tally.
    """
    if succeeded < 0 or failed < 0:
        raise ValueError("succeeded and failed must both be non-negative.")
    total = succeeded + failed
    if total == 0:
        return None
    return succeeded / total


def fleet_availability(online: int, total: int) -> float | None:
    """The fraction of the fleet currently online.

    Raises:
        ValueError: When *online* exceeds *total*, or either is
            negative.
    """
    if online < 0 or total < 0:
        raise ValueError("online and total must both be non-negative.")
    if online > total:
        raise ValueError(f"online ({online}) cannot exceed total ({total}).")
    if total == 0:
        return None
    return online / total


__all__ = ["fleet_availability", "success_rate"]
