"""Upgrade plan validation: version skew and rollback decisions.

**A version skew check compares catalog rank, never parsed semver.**
Version string formats differ across distributions (``v1.29.4`` vs
``1.29.4-eks-1`` vs a vendor build tag) enough that a shared parser would
be a second place to get distribution quirks wrong;
:class:`~app.models.fleet.ClusterVersion`'s ``skew_rank`` is a single
ordinal this service assigns itself when a version enters the catalog,
so comparing ranks is exact by construction.
"""

from __future__ import annotations

from dataclasses import dataclass


class UpgradeRefusal:
    DOWNGRADE = "downgrade"
    SAME_VERSION = "same_version"
    SKEW_EXCEEDED = "skew_exceeded"


@dataclass(frozen=True, slots=True)
class UpgradePlanValidation:
    is_valid: bool
    refusal: str | None
    skew: int
    detail: str


def validate_upgrade_plan(from_rank: int, to_rank: int, *, max_skew: int) -> UpgradePlanValidation:
    """Whether an upgrade from *from_rank* to *to_rank* is allowed.

    Refuses a downgrade (this engine plans upgrades, not rollbacks -- a
    rollback is a distinct, explicitly-requested operation, never an
    "upgrade" to an older version), a no-op (*same* version), or a jump
    that skips more than *max_skew* catalog steps, mirroring upstream
    Kubernetes' own single-minor-version skew policy generalised across
    distributions.
    """
    skew = to_rank - from_rank
    if skew == 0:
        return UpgradePlanValidation(
            is_valid=False,
            refusal=UpgradeRefusal.SAME_VERSION,
            skew=skew,
            detail="The target version is the same as the current version.",
        )
    if skew < 0:
        return UpgradePlanValidation(
            is_valid=False,
            refusal=UpgradeRefusal.DOWNGRADE,
            skew=skew,
            detail="The target version is older than the current version.",
        )
    if skew > max_skew:
        return UpgradePlanValidation(
            is_valid=False,
            refusal=UpgradeRefusal.SKEW_EXCEEDED,
            skew=skew,
            detail=(
                f"The upgrade spans {skew} catalog version(s), exceeding the maximum "
                f"supported skew of {max_skew}."
            ),
        )
    return UpgradePlanValidation(
        is_valid=True, refusal=None, skew=skew, detail=f"Upgrade spans {skew} version(s)."
    )


def should_roll_back(
    *, pre_validation_passed: bool | None, post_validation_passed: bool | None
) -> bool:
    """Whether a completed upgrade should be rolled back.

    Only an *explicit* post-validation failure (``False``, not ``None``)
    triggers a rollback recommendation -- an upgrade whose post-validation
    was never run is unproven, not proven-bad, and rolling it back on no
    evidence would undo a possibly-successful upgrade for no reason.
    """
    return post_validation_passed is False


__all__ = ["UpgradePlanValidation", "UpgradeRefusal", "should_roll_back", "validate_upgrade_plan"]
