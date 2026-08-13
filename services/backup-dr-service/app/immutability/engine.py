"""Immutability state transitions: retention locks and legal holds.

**A retention lock may only be extended, never shortened.** Allowing a
shorter lock would let anyone who can call this function undo a WORM
guarantee by re-applying a shorter one -- the entire reason a lock
exists is to be un-shortenable by the same actor who could otherwise
just delete the archive outright.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.enums import ImmutabilityState


class LockRefusal:
    WOULD_SHORTEN_EXISTING_LOCK = "would_shorten_existing_lock"


@dataclass(frozen=True, slots=True)
class LockOutcome:
    accepted: bool
    new_lock_until: datetime | None
    new_state: ImmutabilityState
    refusal: str | None


def apply_retention_lock(
    *, requested_until: datetime, existing_lock_until: datetime | None
) -> LockOutcome:
    """Apply or extend a retention lock.

    A request that would move the lock *earlier* than one already in
    force is refused outright rather than silently ignored or clamped --
    a caller who asked for an earlier date made a mistake worth
    surfacing, not one worth quietly correcting.
    """
    if existing_lock_until is not None and requested_until < existing_lock_until:
        return LockOutcome(
            accepted=False,
            new_lock_until=existing_lock_until,
            new_state=ImmutabilityState.RETENTION_LOCKED,
            refusal=LockRefusal.WOULD_SHORTEN_EXISTING_LOCK,
        )
    return LockOutcome(
        accepted=True,
        new_lock_until=requested_until,
        new_state=ImmutabilityState.RETENTION_LOCKED,
        refusal=None,
    )


def apply_legal_hold(*, reason: str) -> ImmutabilityState:
    """A legal hold always applies and always outranks a retention lock
    -- see :func:`app.retention.engine.is_deletable`, which checks it
    first and unconditionally."""
    if not reason.strip():
        raise ValueError(
            "A legal hold must state a reason; an unexplained hold cannot be reviewed."
        )
    return ImmutabilityState.LEGAL_HOLD


def release_legal_hold(
    *, retention_lock_until: datetime | None, now: datetime
) -> ImmutabilityState:
    """The state an archive returns to once its legal hold is lifted.

    Falls back to ``RETENTION_LOCKED`` when an unexpired lock is still in
    force underneath the hold that is being released -- releasing a
    legal hold must never accidentally also release a retention lock
    nobody asked to release.
    """
    if retention_lock_until is not None and retention_lock_until > now:
        return ImmutabilityState.RETENTION_LOCKED
    return ImmutabilityState.NONE


__all__ = [
    "LockOutcome",
    "LockRefusal",
    "apply_legal_hold",
    "apply_retention_lock",
    "release_legal_hold",
]
