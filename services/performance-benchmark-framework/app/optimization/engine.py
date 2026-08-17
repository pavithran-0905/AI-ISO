"""Optimization recommendation impact scoring.

A recommendation's ``impact_score`` is derived from how large the
underlying regression or capacity gap is -- not invented, so it always
traces back to a concrete measured fact.
"""

from __future__ import annotations

from app.models.enums import OptimizationCategory, RegressionType

_MIN_SCORE = 0.0
_MAX_SCORE = 100.0
_HIGH_IMPACT_THRESHOLD = 50.0

_REGRESSION_TYPE_CATEGORY: dict[RegressionType, OptimizationCategory] = {
    RegressionType.DATABASE: OptimizationCategory.QUERY,
    RegressionType.WORKFLOW: OptimizationCategory.WORKFLOW,
    RegressionType.API: OptimizationCategory.API,
    RegressionType.CPU: OptimizationCategory.INFRASTRUCTURE,
    RegressionType.MEMORY: OptimizationCategory.INFRASTRUCTURE,
}


def compute_impact_score(*, magnitude_percent: float, category_weight: float = 1.0) -> float:
    """Score how much impact acting on a recommendation would have,
    bounded to ``[0, 100]``.

    *magnitude_percent* is the size of the underlying regression or
    capacity gap that prompted the recommendation; *category_weight*
    lets a category the platform considers more urgent (e.g. scaling
    ahead of a capacity breach) outrank an equally-sized one that
    isn't.
    """
    score = abs(magnitude_percent) * category_weight
    return max(_MIN_SCORE, min(_MAX_SCORE, score))


def is_high_impact(impact_score: float, *, threshold: float = _HIGH_IMPACT_THRESHOLD) -> bool:
    """Whether a recommendation's own impact score crosses the
    high-impact threshold."""
    return impact_score >= threshold


def category_for_regression(regression_type: RegressionType) -> OptimizationCategory:
    """Map a detected regression's own kind to the optimization
    category most likely to fix it. ``LATENCY`` and ``THROUGHPUT`` --
    generic, cross-cutting metrics -- fall back to ``INFRASTRUCTURE``,
    the same default any regression type without a more specific
    category maps to."""
    return _REGRESSION_TYPE_CATEGORY.get(regression_type, OptimizationCategory.INFRASTRUCTURE)


__all__ = ["category_for_regression", "compute_impact_score", "is_high_impact"]
