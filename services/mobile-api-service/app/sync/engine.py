"""Synchronization job/queue lifecycle, conflict detection, and retry
backoff.

Covers offline mode, delta synchronization, and the retry policy in one
module -- those are facets of one state machine (a queued offline
action moving toward being applied), not three separate ones.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.models.enums import ConflictResolutionStrategy, SyncJobStatus, SyncQueueStatus

_J = SyncJobStatus
_Q = SyncQueueStatus

JOB_TRANSITIONS: dict[SyncJobStatus, frozenset[SyncJobStatus]] = {
    _J.PENDING: frozenset({_J.RUNNING}),
    _J.RUNNING: frozenset({_J.COMPLETED, _J.FAILED}),
    _J.COMPLETED: frozenset(),
    _J.FAILED: frozenset(),
}

QUEUE_TRANSITIONS: dict[SyncQueueStatus, frozenset[SyncQueueStatus]] = {
    _Q.QUEUED: frozenset({_Q.PROCESSING}),
    _Q.PROCESSING: frozenset({_Q.APPLIED, _Q.CONFLICT, _Q.FAILED}),
    _Q.CONFLICT: frozenset({_Q.APPLIED, _Q.FAILED}),
    _Q.FAILED: frozenset({_Q.QUEUED}),
    _Q.APPLIED: frozenset(),
}
"""``FAILED -> QUEUED`` is the retry path (bounded by
``is_retry_eligible``); ``CONFLICT -> APPLIED/FAILED`` is a resolved
conflict moving on; ``APPLIED`` is the one truly terminal state."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def _validate(
    current: Any, target: Any, table: Mapping[Any, frozenset[Any]], enum_cls: type[StrEnum]
) -> TransitionResult:
    current_state = enum_cls(current)
    target_state = enum_cls(target)
    allowed = table.get(current_state, frozenset())
    if not allowed:
        return TransitionResult(
            is_allowed=False,
            refusal=TransitionRefusal.TERMINAL_STATE,
            detail=f"{current_state.value} is a terminal state; no further transition is possible.",
        )
    if target_state not in allowed:
        allowed_names = ", ".join(sorted(state.value for state in allowed))
        return TransitionResult(
            is_allowed=False,
            refusal=TransitionRefusal.INVALID_TRANSITION,
            detail=(
                f"{current_state.value} cannot transition to {target_state.value}; "
                f"allowed next states are: {allowed_names}."
            ),
        )
    return TransitionResult(
        is_allowed=True,
        refusal=None,
        detail=f"{current_state.value} -> {target_state.value} is allowed.",
    )


def validate_job_transition(current: SyncJobStatus, target: SyncJobStatus) -> TransitionResult:
    """Whether a sync job may move from *current* to *target*."""
    return _validate(current, target, JOB_TRANSITIONS, SyncJobStatus)


def validate_queue_transition(
    current: SyncQueueStatus, target: SyncQueueStatus
) -> TransitionResult:
    """Whether a queued offline action may move from *current* to
    *target*."""
    return _validate(current, target, QUEUE_TRANSITIONS, SyncQueueStatus)


def detect_conflict(*, client_updated_at: datetime, server_updated_at: datetime | None) -> bool:
    """Whether applying a client's queued action would clobber a
    server-side change the client never saw.

    A server row with no prior update (``server_updated_at is None``)
    has nothing for the client to conflict with.
    """
    if server_updated_at is None:
        return False
    return server_updated_at > client_updated_at


def resolve_conflict(
    strategy: ConflictResolutionStrategy,
    *,
    client_updated_at: datetime,
    server_updated_at: datetime,
) -> bool:
    """Whether the *client's* queued action should win the conflict.

    ``MANUAL`` never auto-resolves -- the caller must treat a ``False``
    return under ``MANUAL`` as "still needs a human," not as "server
    won."
    """
    strategy = ConflictResolutionStrategy(strategy)
    if strategy == ConflictResolutionStrategy.CLIENT_WINS:
        return True
    if strategy == ConflictResolutionStrategy.SERVER_WINS:
        return False
    return client_updated_at > server_updated_at


def is_retry_eligible(*, retry_count: int, max_retry_count: int) -> bool:
    """Whether a failed queue item has retries left."""
    return retry_count < max_retry_count


def compute_backoff_seconds(*, retry_count: int, base_seconds: int) -> int:
    """Exponential backoff: ``base * 2^retry_count``, uncapped -- the
    caller's own sweep interval is the natural ceiling on how often
    this is even evaluated."""
    return int(base_seconds * (2**retry_count))


__all__ = [
    "JOB_TRANSITIONS",
    "QUEUE_TRANSITIONS",
    "TransitionRefusal",
    "TransitionResult",
    "compute_backoff_seconds",
    "detect_conflict",
    "is_retry_eligible",
    "resolve_conflict",
    "validate_job_transition",
    "validate_queue_transition",
]
