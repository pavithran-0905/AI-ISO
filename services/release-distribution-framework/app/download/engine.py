"""Download rate computation."""

from __future__ import annotations


def downloads_per_day(*, download_count: int, window_hours: float) -> float:
    """The average download rate per day over a window. A
    non-positive window yields an honest zero rather than dividing by
    zero."""
    if window_hours <= 0:
        return 0.0
    return download_count / (window_hours / 24.0)


__all__ = ["downloads_per_day"]
