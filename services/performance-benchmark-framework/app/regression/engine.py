"""Regression and improvement detection against a metric's own baseline.

Whether an increase or a decrease is "bad" depends on the metric's own
direction (latency: lower is better; throughput: higher is better) --
every function here takes ``higher_is_better`` explicitly rather than
assuming one direction.
"""

from __future__ import annotations

from app.models.enums import BenchmarkType, RegressionSeverity, RegressionType

_METRIC_NAME_HINTS: tuple[tuple[str, RegressionType], ...] = (
    ("latency", RegressionType.LATENCY),
    ("throughput", RegressionType.THROUGHPUT),
    ("rps", RegressionType.THROUGHPUT),
    ("qps", RegressionType.THROUGHPUT),
    ("memory", RegressionType.MEMORY),
    ("cpu", RegressionType.CPU),
)

_BENCHMARK_TYPE_FALLBACK: dict[BenchmarkType, RegressionType] = {
    BenchmarkType.API: RegressionType.API,
    BenchmarkType.DATABASE: RegressionType.DATABASE,
    BenchmarkType.WORKFLOW: RegressionType.WORKFLOW,
}

_SEVERITY_RATIO_BREAKPOINTS: tuple[tuple[float, RegressionSeverity], ...] = (
    (0.5, RegressionSeverity.LOW),
    (0.75, RegressionSeverity.MEDIUM),
    (1.0, RegressionSeverity.HIGH),
)


def percent_change(*, baseline: float, current: float) -> float:
    """The signed percent change from *baseline* to *current*.

    A zero baseline with a nonzero current is treated as a full 100%
    change in the current's own direction, rather than raising a
    division error -- the same zero-baseline shape
    ``services/testing-quality-framework``'s own benchmark engine uses.
    """
    if baseline == 0:
        return 0.0 if current == 0 else (100.0 if current > 0 else -100.0)
    return ((current - baseline) / abs(baseline)) * 100.0


def regression_magnitude_percent(
    *, baseline: float, current: float, higher_is_better: bool
) -> float:
    """How much worse *current* is than *baseline*, as a positive
    percentage; zero or negative means no regression. Exposed publicly
    so a caller that has already confirmed ``is_regression`` can record
    the same magnitude it was detected with, rather than recomputing
    it a different way."""
    change = percent_change(baseline=baseline, current=current)
    return -change if higher_is_better else change


def is_regression(
    *, baseline: float, current: float, higher_is_better: bool, warning_threshold_percent: float
) -> bool:
    """Whether *current* has regressed against *baseline* by at least the
    configured warning threshold."""
    magnitude = regression_magnitude_percent(
        baseline=baseline, current=current, higher_is_better=higher_is_better
    )
    return magnitude >= warning_threshold_percent


def is_improvement(
    *, baseline: float, current: float, higher_is_better: bool, improvement_threshold_percent: float
) -> bool:
    """Whether *current* has improved on *baseline* by at least the
    configured improvement threshold."""
    goodness = -regression_magnitude_percent(
        baseline=baseline, current=current, higher_is_better=higher_is_better
    )
    return goodness >= improvement_threshold_percent


def classify_severity(
    *, regression_percent: float, critical_threshold_percent: float
) -> RegressionSeverity:
    """Score a detected regression's own severity, scaled against the
    configured critical threshold: below half of it is ``LOW``, below
    three quarters is ``MEDIUM``, below the threshold itself is
    ``HIGH``, and at or beyond it is ``CRITICAL``."""
    if critical_threshold_percent <= 0:
        return RegressionSeverity.CRITICAL
    ratio = regression_percent / critical_threshold_percent
    for breakpoint, severity in _SEVERITY_RATIO_BREAKPOINTS:
        if ratio < breakpoint:
            return severity
    return RegressionSeverity.CRITICAL


def infer_regression_type(*, metric_name: str, benchmark_type: BenchmarkType) -> RegressionType:
    """Classify which kind of regression a metric measurement belongs
    to: first from the metric's own name (``latency_ms`` names a
    latency regression regardless of what suite it ran in), falling
    back to the benchmark suite's own domain when the name gives no
    hint, and finally to ``LATENCY`` as the generic default."""
    lowered = metric_name.lower()
    for hint, regression_type in _METRIC_NAME_HINTS:
        if hint in lowered:
            return regression_type
    return _BENCHMARK_TYPE_FALLBACK.get(benchmark_type, RegressionType.LATENCY)


__all__ = [
    "classify_severity",
    "infer_regression_type",
    "is_improvement",
    "is_regression",
    "percent_change",
    "regression_magnitude_percent",
]
