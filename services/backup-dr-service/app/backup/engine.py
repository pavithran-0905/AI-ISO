"""Backup chain integrity, deduplication, and scheduling.

**An incremental chain is only as strong as its weakest link, and this
module is where that gets checked before a restore ever needs it.** An
incremental backup is meaningless without every incremental since the
last full applied in order; a chain with a missing or failed link in the
middle is not "mostly restorable," it is not restorable past the break.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.enums import BackupJobStatus, BackupType


@dataclass(frozen=True, slots=True)
class ChainLink:
    """One backup job as the chain-validation engine needs to see it."""

    job_id: str
    backup_type: BackupType
    parent_job_id: str | None
    status: BackupJobStatus
    completed_at: datetime | None


class ChainBreakReason:
    """Why a chain cannot be walked to completion. Typed, not free text."""

    ROOT_NOT_FULL = "root_not_full"
    MISSING_PARENT = "missing_parent"
    PARENT_NOT_COMPLETE = "parent_not_complete"
    CYCLE_DETECTED = "cycle_detected"


@dataclass(frozen=True, slots=True)
class ChainValidation:
    """Whether a chain from a target job back to its full backup is
    intact, and exactly where it breaks if not."""

    is_intact: bool
    chain: tuple[str, ...]
    """Job ids from the full backup to the target job, oldest first. Only
    populated when ``is_intact`` -- a broken chain has no single
    ordering worth presenting as if it were usable."""
    break_reason: str | None
    broken_at_job_id: str | None


def validate_chain(target_job_id: str, jobs: Sequence[ChainLink]) -> ChainValidation:
    """Walk from *target_job_id* back through ``parent_job_id`` to a full
    backup, checking every link is complete.

    A full backup or a snapshot-type backup has no parent and is its own
    chain of one. An incremental or differential chain must terminate at
    a ``FULL`` backup -- terminating at anything else (including running
    out of parent links entirely) is a chain nothing can restore from.
    """
    by_id = {job.job_id: job for job in jobs}
    target = by_id.get(target_job_id)
    if target is None:
        return ChainValidation(
            is_intact=False,
            chain=(),
            break_reason=ChainBreakReason.MISSING_PARENT,
            broken_at_job_id=target_job_id,
        )

    ordered: list[str] = []
    seen: set[str] = set()
    current: ChainLink | None = target
    while current is not None:
        if current.job_id in seen:
            return ChainValidation(
                is_intact=False,
                chain=(),
                break_reason=ChainBreakReason.CYCLE_DETECTED,
                broken_at_job_id=current.job_id,
            )
        seen.add(current.job_id)
        if (
            current.status is not BackupJobStatus.COMPLETED
            and current.status is not BackupJobStatus.VERIFIED
        ):
            return ChainValidation(
                is_intact=False,
                chain=(),
                break_reason=ChainBreakReason.PARENT_NOT_COMPLETE,
                broken_at_job_id=current.job_id,
            )
        ordered.append(current.job_id)

        if current.backup_type in (BackupType.FULL, BackupType.SNAPSHOT, BackupType.CONTINUOUS):
            ordered.reverse()
            return ChainValidation(
                is_intact=True, chain=tuple(ordered), break_reason=None, broken_at_job_id=None
            )

        if current.parent_job_id is None:
            return ChainValidation(
                is_intact=False,
                chain=(),
                break_reason=ChainBreakReason.ROOT_NOT_FULL,
                broken_at_job_id=current.job_id,
            )
        parent = by_id.get(current.parent_job_id)
        if parent is None:
            return ChainValidation(
                is_intact=False,
                chain=(),
                break_reason=ChainBreakReason.MISSING_PARENT,
                broken_at_job_id=current.parent_job_id,
            )
        current = parent

    # Unreachable: the loop only exits via an explicit return above.
    raise AssertionError("validate_chain fell through its own loop")


def compute_checksum(data: bytes, *, algorithm: str = "sha256") -> str:
    """A stable content checksum, for verification and deduplication.

    Raises:
        ValueError: On an unsupported algorithm, rather than silently
            falling back to a different one whose checksum would not
            match a value already stored under the requested name.
    """
    try:
        hasher = hashlib.new(algorithm)
    except ValueError as exc:
        raise ValueError(f"Unsupported checksum algorithm {algorithm!r}.") from exc
    hasher.update(data)
    return hasher.hexdigest()


@dataclass(frozen=True, slots=True)
class DedupeOutcome:
    """Whether a new backup's content is already stored under another job."""

    is_duplicate: bool
    duplicate_of_job_id: str | None


def detect_duplicate(
    checksum: str, size_bytes: int, existing: Sequence[tuple[str, str, int]]
) -> DedupeOutcome:
    """Whether *checksum* + *size_bytes* already exists among *existing*
    ``(job_id, checksum, size_bytes)`` triples.

    Both fields must match: a checksum collision alone is not proof of
    identical content, and checking size costs nothing while remaining
    exactly as fast for the overwhelmingly common non-duplicate case.
    """
    for job_id, other_checksum, other_size in existing:
        if other_checksum == checksum and other_size == size_bytes:
            return DedupeOutcome(is_duplicate=True, duplicate_of_job_id=job_id)
    return DedupeOutcome(is_duplicate=False, duplicate_of_job_id=None)


_FREQUENCY_INTERVALS = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
}


def compute_next_run(frequency: str, *, last_run_at: datetime | None, now: datetime) -> datetime:
    """The next time a schedule should fire.

    A schedule with no prior run fires immediately (``now``) rather than
    waiting a full interval -- a newly created backup schedule should not
    leave its target unprotected for up to a month before its first run.

    Raises:
        ValueError: On ``custom_cron``, which this function does not
            evaluate -- cron parsing belongs to the scheduler framework,
            not duplicated here with its own bugs.
    """
    if frequency == "custom_cron":
        raise ValueError(
            "compute_next_run does not evaluate cron expressions; register the "
            "schedule with shared_core.scheduler instead."
        )
    interval = _FREQUENCY_INTERVALS.get(frequency)
    if interval is None:
        raise ValueError(f"Unknown schedule frequency {frequency!r}.")
    if last_run_at is None:
        return now
    next_run = last_run_at + interval
    # A schedule that fell behind (the worker was down for two days)
    # catches up to "now plus one interval" rather than firing a backlog
    # of missed runs back to back, which would flood the target with
    # redundant backups the moment the worker comes back.
    return next_run if next_run > now else now + interval


__all__ = [
    "ChainBreakReason",
    "ChainLink",
    "ChainValidation",
    "DedupeOutcome",
    "compute_checksum",
    "compute_next_run",
    "detect_duplicate",
    "validate_chain",
]
