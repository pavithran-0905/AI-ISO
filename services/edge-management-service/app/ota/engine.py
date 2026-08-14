"""OTA update plan validation and rollback decisions.

**A version skew check compares catalog rank, never parsed semver** --
version string formats differ enough across device types (a PLC's
firmware numbering has nothing to do with a Raspberry Pi's OS image tag)
that a shared parser would be a second place to get device-type quirks
wrong; each catalog entry's ``skew_rank`` is a single ordinal this
service assigns itself when a version enters the catalog.
"""

from __future__ import annotations

from dataclasses import dataclass


class UpdateRefusal:
    DOWNGRADE = "downgrade"
    SAME_VERSION = "same_version"
    SKEW_EXCEEDED = "skew_exceeded"


@dataclass(frozen=True, slots=True)
class UpdatePlanValidation:
    is_valid: bool
    refusal: str | None
    skew: int
    detail: str


def validate_update_plan(from_rank: int, to_rank: int, *, max_skew: int) -> UpdatePlanValidation:
    """Whether an update from *from_rank* to *to_rank* is allowed.

    Refuses a downgrade (this engine plans forward updates, not
    rollbacks -- a rollback is a distinct, explicitly-requested
    operation), a no-op (*same* version), or a jump that skips more than
    *max_skew* catalog steps.
    """
    skew = to_rank - from_rank
    if skew == 0:
        return UpdatePlanValidation(
            is_valid=False,
            refusal=UpdateRefusal.SAME_VERSION,
            skew=skew,
            detail="The target version is the same as the current version.",
        )
    if skew < 0:
        return UpdatePlanValidation(
            is_valid=False,
            refusal=UpdateRefusal.DOWNGRADE,
            skew=skew,
            detail="The target version is older than the current version.",
        )
    if skew > max_skew:
        return UpdatePlanValidation(
            is_valid=False,
            refusal=UpdateRefusal.SKEW_EXCEEDED,
            skew=skew,
            detail=(
                f"The update spans {skew} catalog version(s), exceeding the maximum "
                f"supported skew of {max_skew}."
            ),
        )
    return UpdatePlanValidation(
        is_valid=True, refusal=None, skew=skew, detail=f"Update spans {skew} version(s)."
    )


def should_roll_back(*, verification_passed: bool | None) -> bool:
    """Whether a completed update should be rolled back.

    Only an *explicit* verification failure (``False``, not ``None``)
    triggers a rollback recommendation -- an update whose post-install
    verification never ran is unproven, not proven-bad.
    """
    return verification_passed is False


__all__ = ["UpdatePlanValidation", "UpdateRefusal", "should_roll_back", "validate_update_plan"]
