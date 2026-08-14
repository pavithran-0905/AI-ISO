"""Fleet analytics: rates with an honest denominator.

**A rate with a zero denominator is `None`, never `0.0` or `1.0`.** Zero
resources discovered in a window is not a 0% discovery rate (nothing
failed) and not a 100% one (nothing succeeded either) -- it is a window
with no evidence.
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


def compliance_rate(compliant: int, total_assessed: int) -> float | None:
    """The fraction of assessed accounts that are compliant.

    Raises:
        ValueError: When *compliant* exceeds *total_assessed*, or
            either is negative.
    """
    if compliant < 0 or total_assessed < 0:
        raise ValueError("compliant and total_assessed must both be non-negative.")
    if compliant > total_assessed:
        raise ValueError(
            f"compliant ({compliant}) cannot exceed total_assessed ({total_assessed})."
        )
    if total_assessed == 0:
        return None
    return compliant / total_assessed


__all__ = ["compliance_rate", "success_rate"]
