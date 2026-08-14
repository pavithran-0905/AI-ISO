"""Synchronization outcome classification and conflict resolution.

**A sync that never completed is never silently treated as
successful.** The outcome of a sync attempt is always one of a fixed set
of typed states, and a conflict is resolved by an explicit strategy,
never by picking a side implicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.enums import ConflictResolutionStrategy, SyncStatus


class ConflictWinner:
    SERVER = "server"
    DEVICE = "device"
    UNRESOLVED = "unresolved"


def resolve_conflict(
    strategy: ConflictResolutionStrategy,
    *,
    server_updated_at: datetime,
    device_updated_at: datetime,
) -> str:
    """Which side wins a detected sync conflict, per *strategy*.

    ``MANUAL`` never resolves automatically -- it always returns
    ``UNRESOLVED``, since a strategy that exists specifically to defer to
    a human must never silently pick a side on its own.
    """
    # ``==``, never ``is`` -- *strategy* may have been read from a
    # freshly materialized ORM row, which carries a plain ``str`` rather
    # than the enum instance for a plain-``String``-typed column.
    if strategy == ConflictResolutionStrategy.SERVER_WINS:
        return ConflictWinner.SERVER
    if strategy == ConflictResolutionStrategy.DEVICE_WINS:
        return ConflictWinner.DEVICE
    if strategy == ConflictResolutionStrategy.LAST_WRITE_WINS:
        if device_updated_at > server_updated_at:
            return ConflictWinner.DEVICE
        return ConflictWinner.SERVER
    return ConflictWinner.UNRESOLVED


def is_sync_overdue(
    last_completed_at: datetime | None, *, now: datetime, threshold_minutes: int
) -> bool:
    """Whether a device has gone too long without a completed sync.

    ``last_completed_at is None`` (never synced at all) is always
    overdue -- there is no prior success to measure staleness from.
    """
    if last_completed_at is None:
        return True
    return now - last_completed_at > timedelta(minutes=threshold_minutes)


@dataclass(frozen=True, slots=True)
class RetryDecision:
    should_retry: bool
    detail: str


def should_retry_sync(
    status: SyncStatus, *, attempt_count: int, max_attempts: int
) -> RetryDecision:
    """Whether a failed sync should be retried.

    Only ``FAILED`` is retryable here -- a ``CONFLICT`` needs resolution
    first (see :func:`resolve_conflict`), not a blind repeat of the same
    attempt that will conflict again.

    Raises:
        ValueError: On a non-positive *max_attempts*.
    """
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be at least 1; got {max_attempts}.")
    if status != SyncStatus.FAILED:
        return RetryDecision(
            should_retry=False, detail=f"Status {status} is not retryable by this decision."
        )
    if attempt_count >= max_attempts:
        return RetryDecision(
            should_retry=False,
            detail=f"Already attempted {attempt_count} time(s), at the maximum of {max_attempts}.",
        )
    return RetryDecision(
        should_retry=True, detail=f"Attempt {attempt_count + 1} of {max_attempts}."
    )


__all__ = [
    "ConflictWinner",
    "RetryDecision",
    "is_sync_overdue",
    "resolve_conflict",
    "should_retry_sync",
]
