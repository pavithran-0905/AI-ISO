"""Backup retention: tiering and deletion, with immutability as an
absolute veto.

**Immutability and legal hold are checked before age, never after.** A
retention sweep that computed "this archive is past its retention
period" and only then discovered a legal hold would still be the kind of
codebase where the order is easy to get backwards during a refactor;
every planning function here takes the lock state as a required
parameter precisely so there is no path that forgets to ask.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.enums import ImmutabilityState, RetentionTier


@dataclass(frozen=True, slots=True)
class RetentionPolicySpec:
    """A validated retention policy, ready to be turned into actions.

    Raises:
        ValueError: When ``archive_after_days`` is not strictly before
            ``retention_days`` -- a policy that archives on or after the
            day it would also delete has no tier transition to make.
    """

    retention_days: int
    archive_after_days: int
    is_enabled: bool = True

    def __post_init__(self) -> None:
        if self.archive_after_days >= self.retention_days:
            raise ValueError(
                f"archive_after_days ({self.archive_after_days}) must be strictly "
                f"before retention_days ({self.retention_days}); a policy that "
                "archives at or after its own deletion point has no tier to move "
                "through."
            )


@dataclass(frozen=True, slots=True)
class ArchiveRecord:
    """One archive as the retention engine needs to see it."""

    archive_id: str
    archived_at: datetime
    tier: RetentionTier
    immutability_state: ImmutabilityState
    retention_lock_until: datetime | None
    legal_hold: bool


class RetentionVeto:
    """Why an otherwise-eligible archive was not touched. Typed, so a
    caller can tell "locked" from "not old enough" apart."""

    LEGAL_HOLD = "legal_hold"
    RETENTION_LOCKED = "retention_locked"


def is_deletable(archive: ArchiveRecord, *, now: datetime) -> tuple[bool, str | None]:
    """Whether *archive* may be deleted right now, ignoring age.

    Returns ``(True, None)`` when nothing blocks deletion, or
    ``(False, reason)`` naming the veto. Legal hold is checked first and
    unconditionally: an expired retention lock does not matter if a
    legal hold is also in effect, and the reverse ordering could read as
    "the lock expired, so it's fine" when it is not.
    """
    if archive.legal_hold:
        return False, RetentionVeto.LEGAL_HOLD
    if archive.retention_lock_until is not None and archive.retention_lock_until > now:
        return False, RetentionVeto.RETENTION_LOCKED
    return True, None


@dataclass(frozen=True, slots=True)
class TierAction:
    archive_id: str
    from_tier: RetentionTier
    to_tier: RetentionTier


@dataclass(frozen=True, slots=True)
class DeleteAction:
    archive_id: str


@dataclass(frozen=True, slots=True)
class VetoedAction:
    """An archive that qualified for deletion by age but was blocked."""

    archive_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class RetentionPlan:
    """What a sweep should do, or why it did nothing."""

    tier_actions: tuple[TierAction, ...]
    delete_actions: tuple[DeleteAction, ...]
    vetoed: tuple[VetoedAction, ...]
    refused: str | None

    @property
    def is_noop(self) -> bool:
        return not self.tier_actions and not self.delete_actions


def plan_retention(
    policy: RetentionPolicySpec, archives: list[ArchiveRecord], *, now: datetime
) -> RetentionPlan:
    """Decide what a retention sweep may do to *archives* under *policy*."""
    if not policy.is_enabled:
        return RetentionPlan(tier_actions=(), delete_actions=(), vetoed=(), refused="disabled")

    archive_cutoff = now - timedelta(days=policy.archive_after_days)
    delete_cutoff = now - timedelta(days=policy.retention_days)

    tier_actions: list[TierAction] = []
    delete_actions: list[DeleteAction] = []
    vetoed: list[VetoedAction] = []

    for archive in archives:
        if archive.archived_at <= delete_cutoff:
            deletable, reason = is_deletable(archive, now=now)
            if deletable:
                delete_actions.append(DeleteAction(archive_id=archive.archive_id))
            else:
                assert reason is not None
                vetoed.append(VetoedAction(archive_id=archive.archive_id, reason=reason))
            continue
        if archive.archived_at <= archive_cutoff and archive.tier is RetentionTier.HOT:
            tier_actions.append(
                TierAction(
                    archive_id=archive.archive_id,
                    from_tier=archive.tier,
                    to_tier=RetentionTier.ARCHIVE,
                )
            )

    return RetentionPlan(
        tier_actions=tuple(tier_actions),
        delete_actions=tuple(delete_actions),
        vetoed=tuple(vetoed),
        refused=None,
    )


__all__ = [
    "ArchiveRecord",
    "DeleteAction",
    "RetentionPlan",
    "RetentionPolicySpec",
    "RetentionVeto",
    "TierAction",
    "VetoedAction",
    "is_deletable",
    "plan_retention",
]
