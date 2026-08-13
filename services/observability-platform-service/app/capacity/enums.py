"""Vocabulary for capacity forecasting.

Kept separate from ``app.models.enums`` on purpose: those are the values
that go into database columns, these are how the engine talks about a fit.
Mixing them would make every refinement to the maths a schema migration.

The recurring theme is that **a missing number and a zero are different
answers**, and each needs a name. "No trend is distinguishable from
noise" is a real capacity finding; "we could not fit anything" is not;
and neither is "exhausts in 0 days".
"""

from __future__ import annotations

from enum import StrEnum


class ReductionKind(StrEnum):
    """Which statistic of a bucket gets forecast.

    Required with no default at every entry point. Capacity is a
    constraint on the maximum, so a host averaging 40% CPU while pinning
    at 99% nightly is out of capacity now -- and a mean-based fit reports
    60% headroom. The trap is that the mean's residuals are smaller, so
    the wrong reduction comes back with a *tighter* interval and a
    *higher* R-squared: every quality signal the engine reports endorses
    the wrong answer.
    """

    PEAK = "peak"
    P95 = "p95"
    MEAN = "mean"
    MINIMUM = "minimum"


class EstimatorKind(StrEnum):
    """Which line the forecast is built on."""

    OLS = "ols"
    THEIL_SEN = "theil_sen"


class FitClass(StrEnum):
    """What kind of series was fitted."""

    LINEAR = "linear"
    CONSTANT = "constant"
    """Zero variance. The easiest series to forecast, and the one a naive
    ``if sst == 0: r_squared = 0.0`` guard refuses outright."""


class TrendClass(StrEnum):
    """What the slope means, once compared against its own noise."""

    GROWING = "growing"
    DECLINING = "declining"
    FLAT_WITHIN_NOISE = "flat_within_noise"
    """A positive finding, not a failure: the level is measured, and no
    growth is distinguishable from noise."""
    NEGLIGIBLE = "negligible"
    """Statistically real, materially irrelevant -- what stops "exhausted
    in 4,200 days" from being emitted."""


class IntervalMethod(StrEnum):
    """How the band around a prediction was derived."""

    STUDENT_T_PREDICTION = "student_t_prediction"
    RESIDUAL_QUANTILE = "residual_quantile"
    CONSTANT_SERIES = "constant_series"


class ConfidenceLevel(StrEnum):
    """Restricted on purpose -- an arbitrary float invites 99.99% bands
    from 14 points, which the t-distribution will happily produce and
    which mean nothing."""

    EIGHTY = "80"
    NINETY = "90"
    NINETY_FIVE = "95"

    @property
    def two_sided_alpha(self) -> float:
        return 1.0 - int(self.value) / 100.0


class PointSemantics(StrEnum):
    """What the central line of a forecast actually estimates.

    A log-transformed fit exponentiates back to the *median*, not the
    mean. Labelling it "expected" overstates a right-skewed quantity by
    exactly the amount that matters when procuring against it.
    """

    MEAN = "mean"
    MEDIAN = "median"


class TransformKind(StrEnum):
    """Declared by the caller, never chosen by comparing fits.

    Auto-selecting a transform by R-squared is data dredging: the
    reported confidence stops meaning what it says, and near-equal fits
    make the choice depend on float ordering.
    """

    NONE = "none"
    LOG = "log"


class BoundKind(StrEnum):
    """Why a metric has a ceiling."""

    HARD_PHYSICAL = "hard_physical"
    SOFT_TARGET = "soft_target"
    UNBOUNDED = "unbounded"


class CeilingSource(StrEnum):
    """Where the exhaustion ceiling came from, because a forecast against
    a guessed ceiling is a guess."""

    DECLARED = "declared"
    DERIVED_FROM_QUOTA = "derived_from_quota"
    PERCENT_BOUND = "percent_bound"


class SaturationState(StrEnum):
    """Whether the observations are censored by the bound.

    ``CENSORED_AT_BOUND`` is the nastiest case in the engine: a CPU
    pinned at 100% has zero variance and zero slope, so a level model
    reads saturation as stability and reports no risk on a host with none
    left.
    """

    NORMAL = "normal"
    APPROACHING_BOUND = "approaching_bound"
    CENSORED_AT_BOUND = "censored_at_bound"


class SeasonalityAssessment(StrEnum):
    """Three states, not two.

    With two weeks of daily data each weekday is seen twice, so a weekly
    effect has standard error 0.707s and must exceed 1.41s to be seen --
    which a realistic cycle will not. The engine therefore cannot say "no
    seasonality" at that length; it says it does not know.
    """

    WEEKLY_DETECTED = "weekly_detected"
    NONE_DETECTED = "none_detected"
    INDETERMINATE = "indeterminate"


class ForecastValidity(StrEnum):
    """How far the emitted trajectory can be trusted."""

    FULL_HORIZON = "full_horizon"
    TRUNCATED_AT_BOUND = "truncated_at_bound"
    TRUNCATED_AT_HISTORY_LIMIT = "truncated_at_history_limit"


class ForecastQualifier(StrEnum):
    """Caveats attached to a forecast that is still worth reporting.

    Distinct from a refusal: these say "here is the answer, and here is
    what would make you read it differently".
    """

    LOW_EXPLANATORY_POWER = "low_explanatory_power"
    OUTLIER_SENSITIVE = "outlier_sensitive"
    HIGH_INFLUENCE_POINTS = "high_influence_points"
    SEASONALITY_UNASSESSED = "seasonality_unassessed"
    AUTOCORRELATION_INFLATED = "autocorrelation_inflated"
    SUSPECT_STALE_SOURCE = "suspect_stale_source"
    """Zero variance across several populated buckets. A metric that never
    changes at all is more often a dead exporter than a stable resource,
    and "perfectly stable, high confidence" about a dead exporter is the
    exact failure this engine exists to prevent."""
    APPROACHING_BOUND = "approaching_bound"
    SHORT_HISTORY = "short_history"
    MODEL_RISK_UNQUANTIFIED = "model_risk_unquantified"
    """On every extrapolated point. The interval quantifies sampling error
    in the line; it says nothing about the risk that linearity stops
    holding, which is unbounded and unmeasurable from the data."""


class RefusalReason(StrEnum):
    """Why no forecast could be made. Always paired with a remedy."""

    INSUFFICIENT_HISTORY = "insufficient_history"
    INSUFFICIENT_COVERAGE = "insufficient_coverage"
    DEGENERATE_X = "degenerate_x"
    DEGREES_OF_FREEDOM = "degrees_of_freedom"
    HORIZON_EXCEEDS_HISTORY = "horizon_exceeds_history"
    LEVEL_SHIFT_SUSPECTED = "level_shift_suspected"
    COUNTER_SERIES = "counter_series"
    SATURATED_LEVEL = "saturated_level"
    LOG_REQUIRES_POSITIVE = "log_requires_positive"
    REDUCTION_UNAVAILABLE = "reduction_unavailable"
    TOO_MANY_BUCKETS = "too_many_buckets"


class ExhaustionStatus(StrEnum):
    """Why a resource does or does not have a date attached.

    Every member exists because the numeric encoding of it is worse:
    ``inf`` is invalid JSON and sorts to the top of an urgency-ranked
    dashboard, so the healthiest resource pages the on-call; ``maxsize``
    renders as the year 275760; ``0`` reads as "exhausted now".
    """

    WILL_EXHAUST = "will_exhaust"
    RISK_WITHIN_HORIZON = "risk_within_horizon"
    """The upper band crosses but the point forecast does not. The case
    that matters most for planning, and the one a naive
    ``if forecast > ceiling`` collapses into "no risk"."""
    ALREADY_EXHAUSTED = "already_exhausted"
    NO_TREND = "no_trend"
    DECLINING = "declining"
    NOT_WITHIN_HORIZON = "not_within_horizon"
    UNBOUNDED_METRIC = "unbounded_metric"
    INDETERMINATE = "indeterminate"


class OrderByStatus(StrEnum):
    """Whether the procurement date is still in the future."""

    SCHEDULED = "scheduled"
    OVERDUE = "overdue"
    """Reported with the computed past date rather than ``None`` -- "you
    should have ordered three weeks ago" is the most actionable thing
    this engine produces."""
    NOT_APPLICABLE = "not_applicable"


__all__ = [
    "BoundKind",
    "CeilingSource",
    "ConfidenceLevel",
    "EstimatorKind",
    "ExhaustionStatus",
    "FitClass",
    "ForecastQualifier",
    "ForecastValidity",
    "IntervalMethod",
    "OrderByStatus",
    "PointSemantics",
    "ReductionKind",
    "RefusalReason",
    "SaturationState",
    "SeasonalityAssessment",
    "TransformKind",
    "TrendClass",
]
