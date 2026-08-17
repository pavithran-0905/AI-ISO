"""Rollup analytics: hardening score and an equal-weighted overall
production readiness score."""

from __future__ import annotations


def hardening_score(passed_count: int, total_count: int) -> float:
    """The fraction of hardening checks currently passing. An honest
    zero when nothing has run yet."""
    if total_count <= 0:
        return 0.0
    return passed_count / total_count


def production_readiness_score(
    *,
    hardening_rate: float,
    compliance_rate: float,
    operational_readiness_rate: float,
    dr_rate: float,
) -> float:
    """An equal-weighted average of hardening, compliance, operational
    readiness, and disaster recovery rates -- the same three/four-way
    average shape every prior AI-IOS analytics engine in this build
    uses."""
    return (hardening_rate + compliance_rate + operational_readiness_rate + dr_rate) / 4.0


def is_production_ready(score: float, *, threshold: float) -> bool:
    """Whether an overall production readiness score clears the
    configured threshold."""
    return score >= threshold


__all__ = ["hardening_score", "is_production_ready", "production_readiness_score"]
