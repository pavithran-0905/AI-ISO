"""Post-install/post-upgrade verification aggregation.

Reuses ``app.preflight.engine.aggregate_check_results`` unmodified --
both preflight and post-install verification are "many named checks,
one overall outcome" problems with an identical worst-of-N rule."""

from __future__ import annotations

from collections.abc import Iterable

from app.models.enums import CheckResultStatus
from app.preflight.engine import aggregate_check_results, is_ready


def compute_verification_outcome(results: Iterable[CheckResultStatus]) -> CheckResultStatus:
    """The overall outcome of a set of post-install/post-upgrade
    verification checks."""
    return aggregate_check_results(results)


def is_deployment_verified(overall: CheckResultStatus) -> bool:
    """Whether a deployment passed verification well enough to be
    considered live -- the same "not FAILED" bar preflight uses."""
    return is_ready(overall)


__all__ = ["compute_verification_outcome", "is_deployment_verified"]
