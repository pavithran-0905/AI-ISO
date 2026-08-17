"""Production certification risk scoring and expiration."""

from __future__ import annotations

from datetime import datetime


def compute_risk_score(
    *, hardening_rate: float, compliance_rate: float, readiness_rate: float
) -> float:
    """A 0-100 risk score from three 0-1 "goodness" rates: the
    equal-weighted average of how far each falls short of perfect,
    scaled to a percentage. A target that passed every hardening
    check, every compliance control, and every readiness check scores
    zero risk."""
    shortfall = 1.0 - ((hardening_rate + compliance_rate + readiness_rate) / 3.0)
    return max(0.0, min(100.0, shortfall * 100.0))


def should_grant(risk_score: float, *, threshold: float) -> bool:
    """Whether a computed risk score is low enough to grant
    certification."""
    return risk_score <= threshold


def is_expired(*, expires_at: datetime | None, now: datetime) -> bool:
    """Whether a certification's own expiration date has passed. A
    certification with no expiration date never expires."""
    if expires_at is None:
        return False
    return now >= expires_at


__all__ = ["compute_risk_score", "is_expired", "should_grant"]
