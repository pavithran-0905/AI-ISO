"""Store-and-forward retry queue backoff.

**Backoff grows exponentially and is capped, never unbounded.** An
uncapped exponential backoff on a device that reconnects after days
offline would leave it waiting hours for its next retry long after
connectivity actually returned.
"""

from __future__ import annotations


def compute_backoff_seconds(
    attempt_count: int, *, base_seconds: float, max_seconds: float
) -> float:
    """The delay before the next retry attempt, per standard exponential
    backoff: ``base * 2^attempt``, capped at *max_seconds*.

    Raises:
        ValueError: On a negative *attempt_count*, or non-positive
            *base_seconds*/*max_seconds*.
    """
    if attempt_count < 0:
        raise ValueError(f"attempt_count must be non-negative; got {attempt_count}.")
    if base_seconds <= 0 or max_seconds <= 0:
        raise ValueError("base_seconds and max_seconds must both be positive.")
    delay = base_seconds * (2.0**attempt_count)
    return min(delay, max_seconds)


def should_drop_message(queue_depth: int, *, max_queue_depth: int) -> bool:
    """Whether the store-and-forward queue is full enough that the
    oldest message should be dropped to make room for a new one.

    Raises:
        ValueError: On a non-positive *max_queue_depth*.
    """
    if max_queue_depth < 1:
        raise ValueError(f"max_queue_depth must be at least 1; got {max_queue_depth}.")
    return queue_depth >= max_queue_depth


__all__ = ["compute_backoff_seconds", "should_drop_message"]
