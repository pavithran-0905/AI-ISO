"""Platform analytics rates with an honest denominator.

**A rate with a zero denominator is `None`, never `0.0` or `1.0`.** Zero
health checks run in a window is not 0% availability (nothing failed)
and not 100% (nothing was proven healthy either) -- it is a window with
no evidence.
"""

from __future__ import annotations


def success_rate(succeeded: int, failed: int) -> float | None:
    """The fraction of attempts that succeeded, or ``None`` with no
    attempts.

    Raises:
        ValueError: On a negative count.
    """
    if succeeded < 0 or failed < 0:
        raise ValueError("succeeded and failed must both be non-negative.")
    total = succeeded + failed
    if total == 0:
        return None
    return succeeded / total


def compute_availability_fraction(healthy_checks: int, total_checks: int) -> float | None:
    """The fraction of health checks in a window that came back
    healthy, or ``None`` if no checks ran.

    Raises:
        ValueError: When *healthy_checks* exceeds *total_checks*, or
            either is negative.
    """
    if healthy_checks < 0 or total_checks < 0:
        raise ValueError("healthy_checks and total_checks must both be non-negative.")
    if healthy_checks > total_checks:
        raise ValueError(
            f"healthy_checks ({healthy_checks}) cannot exceed total_checks ({total_checks})."
        )
    if total_checks == 0:
        return None
    return healthy_checks / total_checks


__all__ = ["compute_availability_fraction", "success_rate"]
