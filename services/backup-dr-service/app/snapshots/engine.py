"""Snapshot catalog: expiration and per-target retention counting.

**Expiration is computed, never trusted from a stored flag alone.** A
snapshot's ``expires_at`` is set once at creation; whether it has
*actually* expired is a function of that timestamp and the current
instant, recomputed every time it matters, so a worker that has not run
in a while does not leave stale snapshots reading as fresh.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SnapshotRecord:
    """One snapshot as the catalog engine needs to see it."""

    snapshot_id: str
    target_id: str
    created_at_source: datetime
    expires_at: datetime | None
    is_validated: bool


def is_expired(snapshot: SnapshotRecord, *, now: datetime) -> bool:
    """Whether *snapshot* has passed its expiry.

    ``expires_at is None`` means "kept until explicitly deleted" -- never
    expired by the passage of time alone.
    """
    return snapshot.expires_at is not None and snapshot.expires_at <= now


def expired_snapshots(
    snapshots: Sequence[SnapshotRecord], *, now: datetime
) -> tuple[SnapshotRecord, ...]:
    """Every snapshot in *snapshots* that has passed its expiry."""
    return tuple(snapshot for snapshot in snapshots if is_expired(snapshot, now=now))


@dataclass(frozen=True, slots=True)
class QuotaEnforcement:
    """Which of a target's snapshots exceed its retention count, and
    which are kept.

    Oldest-first eviction: the newest snapshots are what a caller is
    most likely to restore from, so a quota enforcement that evicted
    those instead would defeat the reason snapshots exist.
    """

    kept: tuple[SnapshotRecord, ...]
    evicted: tuple[SnapshotRecord, ...]


def enforce_quota(snapshots: Sequence[SnapshotRecord], *, max_per_target: int) -> QuotaEnforcement:
    """Which snapshots for one target exceed *max_per_target*, oldest
    evicted first.

    Raises:
        ValueError: On a non-positive quota, which could never keep
            anything and is almost certainly a misconfiguration rather
            than an intent to evict every snapshot immediately.
    """
    if max_per_target < 1:
        raise ValueError(f"max_per_target must be at least 1; got {max_per_target}.")
    ordered = sorted(snapshots, key=lambda snapshot: snapshot.created_at_source, reverse=True)
    kept = ordered[:max_per_target]
    evicted = ordered[max_per_target:]
    return QuotaEnforcement(kept=tuple(kept), evicted=tuple(evicted))


def validation_backlog(
    snapshots: Sequence[SnapshotRecord], *, now: datetime, max_age: datetime | None = None
) -> tuple[SnapshotRecord, ...]:
    """Snapshots that are not validated and have not expired -- the
    queue a validation sweep should work through, newest first so the
    most likely to actually be restored from get checked first."""
    candidates = [
        snapshot
        for snapshot in snapshots
        if not snapshot.is_validated and not is_expired(snapshot, now=now)
    ]
    return tuple(sorted(candidates, key=lambda snapshot: snapshot.created_at_source, reverse=True))


__all__ = [
    "QuotaEnforcement",
    "SnapshotRecord",
    "enforce_quota",
    "expired_snapshots",
    "is_expired",
    "validation_backlog",
]
