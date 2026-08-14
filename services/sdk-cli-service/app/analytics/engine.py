"""SDK/CLI adoption analytics with an honest denominator.

**A rate with a zero denominator is `None`, never `0.0` or `1.0`.** Zero
authentication attempts in a window is not a 0% failure rate (nothing
failed) and not a 100% success rate (nothing succeeded either) -- it is
a window with no evidence.
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


def adoption_share(language_download_count: int, total_download_count: int) -> float | None:
    """One language's share of every SDK download, or ``None`` with no
    downloads at all.

    Raises:
        ValueError: When *language_download_count* exceeds
            *total_download_count*, or either is negative.
    """
    if language_download_count < 0 or total_download_count < 0:
        raise ValueError(
            "language_download_count and total_download_count must both be non-negative."
        )
    if language_download_count > total_download_count:
        raise ValueError(
            f"language_download_count ({language_download_count}) cannot exceed "
            f"total_download_count ({total_download_count})."
        )
    if total_download_count == 0:
        return None
    return language_download_count / total_download_count


__all__ = ["adoption_share", "success_rate"]
