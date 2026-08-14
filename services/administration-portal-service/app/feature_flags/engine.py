"""Feature flag evaluation: kill switch, schedule window, deterministic
percentage rollout bucketing, and version constraints.

**A kill switch always wins.** Once ``is_killed`` is set, no rollout
percentage, schedule, or version constraint can turn a flag back on --
an emergency disable has to be unconditional to be trustworthy.

**Rollout bucketing is deterministic, not random.** The same target and
flag always land in the same bucket, so a percentage rollout never
flickers a feature on and off for the same caller between requests.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

_BUCKET_MODULUS = 10_000
_BUCKET_SCALE = 100.0
_GLOBAL_BUCKET_KEY = "global"


def bucket_fraction(target_ref: str | None, *, flag_name: str) -> float:
    """The deterministic ``[0.0, 100.0)`` bucket a target falls into
    for a given flag.

    ``target_ref is None`` (a ``GLOBAL``-scoped flag with no specific
    target) buckets against a fixed key, so a global flag's rollout
    percentage is still a stable yes/no rather than re-randomized on
    every evaluation.
    """
    key = target_ref if target_ref is not None else _GLOBAL_BUCKET_KEY
    digest = hashlib.sha256(f"{flag_name}:{key}".encode()).hexdigest()
    return (int(digest[:8], 16) % _BUCKET_MODULUS) / (_BUCKET_MODULUS / _BUCKET_SCALE)


def is_within_schedule(
    *, now: datetime, starts_at: datetime | None, ends_at: datetime | None
) -> bool:
    """Whether *now* falls within a flag's scheduled rollout window.

    ``starts_at``/``ends_at`` of ``None`` mean no bound on that side.
    """
    if starts_at is not None and now < starts_at:
        return False
    return not (ends_at is not None and now > ends_at)


def _parse_version(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def satisfies_version_constraint(
    current_version: str | None, *, min_version: str | None, max_version: str | None
) -> bool:
    """Whether *current_version* satisfies a flag's min/max platform
    version constraint.

    ``current_version is None`` (the caller did not report one) always
    satisfies -- an unknown version is not proof of incompatibility.
    """
    if current_version is None:
        return True
    current = _parse_version(current_version)
    if min_version is not None and current < _parse_version(min_version):
        return False
    return not (max_version is not None and current > _parse_version(max_version))


def is_flag_enabled_for_target(
    *,
    is_enabled: bool,
    is_killed: bool,
    rollout_percentage: float,
    starts_at: datetime | None,
    ends_at: datetime | None,
    now: datetime,
    target_ref: str | None,
    flag_name: str,
    current_version: str | None = None,
    min_version: str | None = None,
    max_version: str | None = None,
) -> bool:
    """Whether a feature flag evaluates ``True`` for one target right
    now, folding in every one of docs/070's named rollout controls.
    """
    if is_killed:
        return False
    if not is_enabled:
        return False
    if not is_within_schedule(now=now, starts_at=starts_at, ends_at=ends_at):
        return False
    if not satisfies_version_constraint(
        current_version, min_version=min_version, max_version=max_version
    ):
        return False
    return bucket_fraction(target_ref, flag_name=flag_name) < rollout_percentage


__all__ = [
    "bucket_fraction",
    "is_flag_enabled_for_target",
    "is_within_schedule",
    "satisfies_version_constraint",
]
