"""Backup verification: checksum comparison and sample-restore selection.

**A checksum match is the only thing that produces a `PASSED` verdict.**
Everything else -- a missing expected checksum, an algorithm this
service does not recognise -- is a refusal to judge, not a pass. A
verification framework that defaults an ambiguous case to "passed" is
worse than no verification, because it is trusted exactly as much as a
real one.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.models.enums import VerificationStatus


class VerificationRefusal:
    NO_EXPECTED_CHECKSUM = "no_expected_checksum"


@dataclass(frozen=True, slots=True)
class ChecksumVerdict:
    status: VerificationStatus
    refusal: str | None
    detail: str


def verify_checksum(*, expected: str | None, actual: str) -> ChecksumVerdict:
    """Compare an archive's actual checksum against the one recorded at
    backup time."""
    if expected is None:
        return ChecksumVerdict(
            status=VerificationStatus.SKIPPED,
            refusal=VerificationRefusal.NO_EXPECTED_CHECKSUM,
            detail="No checksum was recorded at backup time; nothing to compare against.",
        )
    if expected.lower() == actual.lower():
        return ChecksumVerdict(
            status=VerificationStatus.PASSED,
            refusal=None,
            detail="Checksum matches the value recorded at backup time.",
        )
    return ChecksumVerdict(
        status=VerificationStatus.FAILED,
        refusal=None,
        detail=(
            f"Checksum mismatch: expected {expected}, computed {actual}. The archive "
            "is corrupted, truncated, or was tampered with."
        ),
    )


def compute_checksum(data: bytes, *, algorithm: str = "sha256") -> str:
    """The same operation :mod:`app.backup.engine` uses at write time --
    kept as its own entry point here so verification never has to import
    the backup module purely for this one function."""
    try:
        hasher = hashlib.new(algorithm)
    except ValueError as exc:
        raise ValueError(f"Unsupported checksum algorithm {algorithm!r}.") from exc
    hasher.update(data)
    return hasher.hexdigest()


@dataclass(frozen=True, slots=True)
class VerifiableArchive:
    """One archive as the sampling engine needs to see it."""

    archive_id: str
    last_verified_at: datetime | None


def select_sample(
    archives: Sequence[VerifiableArchive],
    *,
    fraction: float,
    max_age: datetime,
) -> tuple[VerifiableArchive, ...]:
    """Which archives a periodic verification sweep should sample.

    Every archive not verified since *max_age* is included unconditionally
    -- a periodic sweep exists specifically to bound how long an archive
    can go unverified, so "overdue" is never subject to the sample
    fraction. The fraction applies only to spreading load across archives
    that are merely due for their *next* routine check, oldest-verified
    first.

    Raises:
        ValueError: On a fraction outside ``[0, 1]``.
    """
    if not 0.0 <= fraction <= 1.0:
        raise ValueError(f"fraction must be in [0, 1]; got {fraction}.")

    never_verified = [a for a in archives if a.last_verified_at is None]
    overdue = [
        a for a in archives if a.last_verified_at is not None and a.last_verified_at <= max_age
    ]
    routine_due = sorted(
        (a for a in archives if a.last_verified_at is not None and a.last_verified_at > max_age),
        key=lambda a: a.last_verified_at,  # type: ignore[arg-type,return-value]
    )
    sample_count = round(len(routine_due) * fraction)
    sampled_routine = routine_due[:sample_count]

    seen: set[str] = set()
    result: list[VerifiableArchive] = []
    for archive in (*never_verified, *overdue, *sampled_routine):
        if archive.archive_id not in seen:
            seen.add(archive.archive_id)
            result.append(archive)
    return tuple(result)


__all__ = [
    "ChecksumVerdict",
    "VerifiableArchive",
    "VerificationRefusal",
    "compute_checksum",
    "select_sample",
    "verify_checksum",
]
