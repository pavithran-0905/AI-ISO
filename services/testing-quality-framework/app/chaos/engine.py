"""Chaos experiment recovery validation."""

from __future__ import annotations

from app.models.enums import CheckResultStatus


def is_recovery_within_target(recovery_time_seconds: float, *, target_seconds: float) -> bool:
    """Whether a chaos experiment's own recovery time cleared its
    target."""
    return recovery_time_seconds <= target_seconds


def classify_chaos_result(
    recovery_time_seconds: float, *, target_seconds: float
) -> CheckResultStatus:
    """Classify a chaos experiment's own outcome: recovery within
    target is ``PASSED``; within double the target is ``WARNING``
    (the system recovered, just slower than desired); anything slower
    is ``FAILED``."""
    if is_recovery_within_target(recovery_time_seconds, target_seconds=target_seconds):
        return CheckResultStatus.PASSED
    if recovery_time_seconds <= target_seconds * 2:
        return CheckResultStatus.WARNING
    return CheckResultStatus.FAILED


__all__ = ["classify_chaos_result", "is_recovery_within_target"]
