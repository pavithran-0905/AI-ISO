"""Recovery time/point objective validation."""

from __future__ import annotations


def rto_met(*, actual_recovery_seconds: float, target_rto_seconds: float) -> bool:
    """Whether an actual recovery time met its own recovery time
    objective (RTO)."""
    return actual_recovery_seconds <= target_rto_seconds


def rpo_met(*, actual_data_loss_seconds: float, target_rpo_seconds: float) -> bool:
    """Whether actual data loss met its own recovery point objective
    (RPO)."""
    return actual_data_loss_seconds <= target_rpo_seconds


__all__ = ["rpo_met", "rto_met"]
