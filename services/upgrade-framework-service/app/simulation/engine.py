"""Upgrade dry-run simulation: risk assessment and duration
estimation.

Nothing here is persisted -- docs/076's own DATABASE TABLES section has
no simulation-result table, so a simulation's output only ever reaches
the caller directly through ``POST /upgrade/simulate``'s own response,
never a row.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.models.enums import CheckResultStatus

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"


def assess_risk(results: Iterable[CheckResultStatus]) -> str:
    """The overall risk level of a proposed upgrade, from its own
    compatibility and dependency check results: any ``FAILED`` is
    high risk, any ``WARNING`` (with no ``FAILED``) is medium risk,
    an all-``PASSED`` (or empty) set is low risk."""
    statuses = [CheckResultStatus(result) for result in results]
    if any(status == CheckResultStatus.FAILED for status in statuses):
        return RISK_HIGH
    if any(status == CheckResultStatus.WARNING for status in statuses):
        return RISK_MEDIUM
    return RISK_LOW


def estimate_duration_seconds(*, target_count: int, seconds_per_target: float) -> float:
    """The estimated wall-clock duration of upgrading *target_count*
    targets, at *seconds_per_target* each (sequential -- callers using
    a parallel/wave-based strategy divide by their own wave width)."""
    return max(target_count, 0) * max(seconds_per_target, 0.0)


__all__ = ["RISK_HIGH", "RISK_LOW", "RISK_MEDIUM", "assess_risk", "estimate_duration_seconds"]
