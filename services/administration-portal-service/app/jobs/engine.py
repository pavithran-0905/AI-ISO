"""Background job lifecycle transitions and retry backoff.

**Only a ``FAILED`` job is retryable, and only up to the configured
attempt ceiling** -- a ``SUCCEEDED`` job retried again would re-run
completed work; a ``RUNNING`` one retried again would race the attempt
already in flight.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import JobStatus

_S = JobStatus

ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    _S.QUEUED: frozenset({_S.RUNNING, _S.CANCELLED}),
    _S.RUNNING: frozenset({_S.SUCCEEDED, _S.FAILED, _S.CANCELLED}),
    _S.FAILED: frozenset({_S.RETRYING, _S.DEAD_LETTER}),
    _S.RETRYING: frozenset({_S.RUNNING, _S.DEAD_LETTER}),
    _S.SUCCEEDED: frozenset(),
    _S.CANCELLED: frozenset(),
    _S.DEAD_LETTER: frozenset(),
}
"""Every valid next state. ``SUCCEEDED``, ``CANCELLED``, and
``DEAD_LETTER`` are all terminal -- a dead-lettered job needs a new job,
not a resurrection of the old one."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_STATE = "terminal_state"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: JobStatus, target: JobStatus) -> TransitionResult:
    """Whether a job may move from *current* to *target*.

    Both arguments are coerced through :class:`JobStatus` before use,
    since a plain-``String``-typed column can carry a plain ``str``
    rather than the enum instance for a freshly materialized row.
    """
    current = JobStatus(current)
    target = JobStatus(target)
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if not allowed:
        return TransitionResult(
            is_allowed=False,
            refusal=TransitionRefusal.TERMINAL_STATE,
            detail=f"{current.value} is a terminal state; no further transition is possible.",
        )
    if target not in allowed:
        allowed_names = ", ".join(sorted(state.value for state in allowed))
        return TransitionResult(
            is_allowed=False,
            refusal=TransitionRefusal.INVALID_TRANSITION,
            detail=(
                f"{current.value} cannot transition to {target.value}; "
                f"allowed next states are: {allowed_names}."
            ),
        )
    return TransitionResult(
        is_allowed=True, refusal=None, detail=f"{current.value} -> {target.value} is allowed."
    )


@dataclass(frozen=True, slots=True)
class RetryDecision:
    should_retry: bool
    detail: str


def should_retry_job(status: JobStatus, *, attempt_count: int, max_attempts: int) -> RetryDecision:
    """Whether a job should be retried.

    Raises:
        ValueError: On a non-positive *max_attempts*.
    """
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be at least 1; got {max_attempts}.")
    if JobStatus(status) != JobStatus.FAILED:
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


def compute_backoff_seconds(attempt_count: int, *, base_seconds: int) -> float:
    """Exponential backoff before the next retry attempt.

    Raises:
        ValueError: On a negative *attempt_count* or non-positive
            *base_seconds*.
    """
    if attempt_count < 0:
        raise ValueError(f"attempt_count must be non-negative; got {attempt_count}.")
    if base_seconds < 1:
        raise ValueError(f"base_seconds must be at least 1; got {base_seconds}.")
    return float(base_seconds * (2**attempt_count))


__all__ = [
    "ALLOWED_TRANSITIONS",
    "RetryDecision",
    "TransitionRefusal",
    "TransitionResult",
    "compute_backoff_seconds",
    "should_retry_job",
    "validate_transition",
]
