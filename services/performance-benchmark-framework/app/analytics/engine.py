"""Rollup analytics: success rate, SLO compliance rate, and an
equal-weighted overall performance score."""

from __future__ import annotations


def success_rate(succeeded_count: int, total_count: int) -> float:
    """The fraction of benchmark runs that succeeded. An honest zero
    when nothing ran yet, not a fabricated 100%."""
    if total_count <= 0:
        return 0.0
    return succeeded_count / total_count


def slo_compliance_rate(compliant_count: int, total_count: int) -> float:
    """The fraction of evaluated SLOs currently in compliance. A
    vacuous 100% when no SLO has been evaluated -- there is nothing to
    be non-compliant with yet."""
    if total_count <= 0:
        return 1.0
    return compliant_count / total_count


def regression_free_rate(regression_count: int, benchmark_run_count: int) -> float:
    """The fraction of benchmark runs that did *not* trigger a
    regression. A vacuous 100% when nothing ran yet."""
    if benchmark_run_count <= 0:
        return 1.0
    return max(0.0, 1.0 - (regression_count / benchmark_run_count))


def performance_score(
    *,
    success_rate_value: float,
    slo_compliance_rate_value: float,
    regression_free_rate_value: float,
) -> float:
    """An equal-weighted average of run success, SLO compliance, and
    regression-free rate -- the same three-way-average shape
    ``services/testing-quality-framework``'s own quality score uses."""
    return (success_rate_value + slo_compliance_rate_value + regression_free_rate_value) / 3.0


__all__ = ["performance_score", "regression_free_rate", "slo_compliance_rate", "success_rate"]
