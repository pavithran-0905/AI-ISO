"""Capacity forecasting (docs/064 "CAPACITY PLANNING").

The structural decision this module is built around: **there are two
different negatives and they are different types.** A
:class:`ForecastRefused` says nothing could be concluded and carries the
specific thing that would unblock it. A :class:`Forecast` whose trend is
``FLAT_WITHIN_NOISE`` is a *positive* answer -- the level is measured and
no growth is distinguishable from noise. Encoding the first as ``None``
fields inside the second is how the distinction dies at the template,
where ``days_until_exhaustion = None`` renders as ``0`` or an em dash and
an operator reads "imminent" or "fine" depending on the CSS.

The rest follows from refusing to state more than the data supports:
every extrapolated point carries a band, no band is ever a bare point,
and no path produces a ``Forecast`` without a fit behind it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.capacity.buckets import BucketedPoint, CoverageReport, assess_coverage
from app.capacity.enums import (
    BoundKind,
    CeilingSource,
    ConfidenceLevel,
    EstimatorKind,
    ExhaustionStatus,
    FitClass,
    ForecastQualifier,
    ForecastValidity,
    IntervalMethod,
    OrderByStatus,
    PointSemantics,
    ReductionKind,
    RefusalReason,
    SaturationState,
    SeasonalityAssessment,
    TransformKind,
    TrendClass,
)
from app.capacity.regression import (
    MAX_BUCKETS,
    MIN_POINTS_FOR_FIT,
    MIN_POINTS_FOR_QUANTILE_INTERVAL,
    InfluencePoint,
    Interval,
    LinearFit,
    fit_from_line,
    influential_points,
    median_absolute_successive_difference,
    ols_fit,
    prediction_interval,
    residual_quantile_interval,
    slope_confidence_interval,
    t_quantile,
    theil_sen_fit,
)

MIN_BUCKETS_FOR_CLAIM = 14
"""Two weeks of daily buckets. The arithmetic behind it: with evenly
spaced unit buckets ``Sxx = n(n^2-1)/12``, so at n = 14 a trend must
exceed 0.145 residual standard deviations per day to be claimed at all,
against 0.048 at n = 28. Doubling the history makes the engine 3x more
sensitive to a real trend -- which is why "just forecast from what we
have" is not a neutral choice."""

MIN_BUCKETS_FOR_SEASONAL_CLAIM = 28
"""A weekday effect estimated from m observations has standard error
s/sqrt(m). At 14 days each weekday is seen twice, so an effect must
exceed 1.41s to be detected -- more than a realistic weekly cycle. At 28
days it is 1.0s. Below this the engine says it does not know."""

MIN_COVERAGE = 0.8
MAX_GAP_RATIO = 0.2

LEVEL_SHIFT_MASD_MULTIPLIER = 10.0
"""About 6.7 sigma for Gaussian differences: a one-in-1e11 event, so a
discontinuity rather than noise."""

LEVEL_SHIFT_PERSISTENCE = 3
"""Buckets that must stay at the new level before a jump counts as a
step rather than a spike."""

SATURATION_BUCKET_RATIO = 0.2
SATURATION_LEVEL_RATIO = 0.99

SLOPE_DIVERGENCE_LIMIT = 0.5
LOW_R_SQUARED = 0.30
SEASONAL_WINDOW = 7
STALE_SOURCE_MIN_BUCKETS = 3


@dataclass(frozen=True, slots=True)
class MetricBound:
    """A ceiling the metric physically cannot pass, or a target it should
    not."""

    lower: float | None = None
    upper: float | None = None
    kind: BoundKind = BoundKind.UNBOUNDED


@dataclass(frozen=True, slots=True)
class FitEvidence:
    """Everything needed to disagree with the forecast.

    Published in full rather than summarised into a score, because a
    single "confidence: 0.82" cannot be argued with and a Durbin-Watson
    of 0.4 alongside a list of influential timestamps can.
    """

    n_usable: int
    reduction: ReductionKind
    estimator: EstimatorKind
    estimator_reason: str
    fit_class: FitClass
    r_squared: float | None
    adjusted_r_squared: float | None
    residual_std: float
    residual_cv: float | None
    t_slope: float | None
    slope_significant: bool
    durbin_watson: float | None
    rho_estimate: float | None
    variance_inflation: float
    slope_divergence: float | None
    coverage: CoverageReport
    seasonality: SeasonalityAssessment
    saturation: SaturationState
    influential_points: tuple[InfluencePoint, ...]
    assumptions_unverified: tuple[str, ...]
    peak_to_mean_divergence: float | None


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    """One projected bucket.

    Carries both the clipped and unclipped values. Keeping only the
    clipped one destroys information: a consumer computing
    ``headroom = 100 - forecast`` gets 0.0 and cannot tell whether the
    model said 100.4 or 340.
    """

    at: datetime
    index: int
    value: float
    value_raw: float
    clipped: bool
    interval: Interval


@dataclass(frozen=True, slots=True)
class ForecastRefused:
    """No claim could be made, and what would change that.

    A persisted, displayable value -- not an exception. The caller has
    something to show a user and something to act on.
    """

    reason: RefusalReason
    remedy: str
    evidence: FitEvidence | None = None

    @property
    def is_forecast(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Forecast:
    """A projection with its uncertainty and its caveats attached."""

    points: tuple[ForecastPoint, ...]
    fit: LinearFit
    trend_class: TrendClass
    validity: ForecastValidity
    point_semantics: PointSemantics
    interval_method: IntervalMethod
    interval_meaning: str
    confidence: ConfidenceLevel
    bucket: timedelta
    last_observed_at: datetime
    last_observed_value: float
    qualifiers: tuple[ForecastQualifier, ...]
    evidence: FitEvidence

    @property
    def is_forecast(self) -> bool:
        return True

    def at_horizon(self) -> ForecastPoint | None:
        return self.points[-1] if self.points else None


ForecastOutcome = Forecast | ForecastRefused


@dataclass(frozen=True, slots=True)
class ForecastRequest:
    """What to forecast, and every assumption stated as an input.

    ``reduction`` has no default on purpose. Capacity is a constraint on
    the maximum; a mean-based fit on a host that pins nightly reports
    headroom that does not exist, and does so with a *better* R-squared
    and a *tighter* interval than the correct fit. Making the caller
    choose is the only defence that survives review.
    """

    points: Sequence[BucketedPoint]
    reduction: ReductionKind
    bucket: timedelta
    horizon_buckets: int
    confidence: ConfidenceLevel = ConfidenceLevel.NINETY
    transform: TransformKind = TransformKind.NONE
    bound: MetricBound = field(default_factory=MetricBound)
    is_counter: bool = False
    materiality: float = 0.0
    min_buckets_for_claim: int = MIN_BUCKETS_FOR_CLAIM


def _usable(points: Sequence[BucketedPoint], reduction: ReductionKind) -> list[BucketedPoint]:
    return [point for point in points if point.is_measured and point.reduce(reduction) is not None]


def _moving_average(values: Sequence[float], window: int) -> list[float | None]:
    """Centered moving average; ``None`` where the window does not fit."""
    half = window // 2
    result: list[float | None] = []
    for index in range(len(values)):
        if index < half or index >= len(values) - half:
            result.append(None)
        else:
            result.append(math.fsum(values[index - half : index + half + 1]) / window)
    return result


def assess_seasonality(
    indices: Sequence[int], values: Sequence[float], *, period: int = SEASONAL_WINDOW
) -> SeasonalityAssessment:
    """Whether a weekly cycle is present, absent, or unassessable.

    The third state exists because a short history cannot distinguish
    "no cycle" from "a cycle too small to see with this many samples",
    and reporting the first when the truth is the second is how a flat
    service comes to show 2% daily growth.
    """
    if len(values) < MIN_BUCKETS_FOR_SEASONAL_CLAIM:
        return SeasonalityAssessment.INDETERMINATE

    overall = math.fsum(values) / len(values)
    groups: dict[int, list[float]] = {}
    for index, value in zip(indices, values, strict=True):
        groups.setdefault(index % period, []).append(value)

    spread = math.sqrt(math.fsum((value - overall) ** 2 for value in values) / (len(values) - 1))
    if spread <= 0.0:
        return SeasonalityAssessment.NONE_DETECTED

    for members in groups.values():
        effect = abs(math.fsum(members) / len(members) - overall)
        if effect > 2.0 * spread / math.sqrt(len(members)):
            return SeasonalityAssessment.WEEKLY_DETECTED
    return SeasonalityAssessment.NONE_DETECTED


def detect_level_shift(
    values: Sequence[float], *, persistence: int = LEVEL_SHIFT_PERSISTENCE
) -> int | None:
    """Index where the series steps to a new level and stays there.

    Catches a collector switching units mid-window (bytes to MB on a
    redeploy injects a step of 1e6 while R-squared stays respectable) and
    counter resets in the negative direction. The engine will not average
    across a discontinuity and call the result a trend.

    **The persistence check is not optional.** A one-day spike and a
    permanent step produce the same successive difference, so a
    magnitude-only test refuses the series on any single outlier -- and
    the Christmas backup that filled the disk is then a refusal instead
    of the influential point it should be, which is the exact warning
    this engine is supposed to preserve. A step is defined by the level
    *not* returning, so that is what gets measured.
    """
    scale = median_absolute_successive_difference(values)
    if scale is None or scale <= 0.0:
        return None
    limit = LEVEL_SHIFT_MASD_MULTIPLIER * scale

    for index in range(1, len(values)):
        if abs(values[index] - values[index - 1]) <= limit:
            continue
        before = values[max(0, index - persistence) : index]
        after = values[index : index + persistence]
        if len(after) < persistence:
            # Not enough of the series left to tell a step from a spike.
            # Falls through to the influence machinery, which reports it
            # rather than discarding the whole window.
            continue
        if abs(_median_of(after) - _median_of(before)) > limit / 2.0:
            return index
    return None


def _median_of(values: Sequence[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def assess_saturation(values: Sequence[float], bound: MetricBound) -> SaturationState:
    """Whether the observations are pinned against the ceiling.

    A CPU held at 100% for a week has zero variance and zero slope, so a
    level model reads saturation as stability and reports no capacity
    risk on a host with none left. Once pinned, the quantity still
    growing is the *duration* of saturation, not the level.
    """
    if bound.upper is None or not values:
        return SaturationState.NORMAL
    at_bound = sum(1 for value in values if value >= SATURATION_LEVEL_RATIO * bound.upper)
    ratio = at_bound / len(values)
    if ratio >= SATURATION_BUCKET_RATIO:
        return SaturationState.CENSORED_AT_BOUND
    if at_bound > 0:
        return SaturationState.APPROACHING_BOUND
    return SaturationState.NORMAL


def _trim_to_whole_weeks(points: Sequence[BucketedPoint]) -> list[BucketedPoint]:
    """Drop the oldest partial week.

    Fitting a non-whole-week window does not merely add noise, it
    manufactures a slope: a 10-day window starting Monday holds 8 weekdays
    and 2 weekend days, and the surplus weekdays sit at the high-x end, so
    OLS attributes the composition change to the trend. For a 30% weekday
    premium that is roughly 2% of level per day of spurious growth -- a
    6x claim over 90 days, on a service that never grew, with a healthy
    R-squared.
    """
    excess = len(points) % SEASONAL_WINDOW
    return list(points[excess:]) if excess else list(points)


def _horizon_cap(n_usable: int) -> int:
    """Half the usable history, in buckets.

    Self-tightening by design: the leverage term at a horizon of n/2 is
    12/n, so short histories get both short horizons and wide bands. The
    cap is needed on top of the band because the band quantifies sampling
    error in the line and says nothing about the risk that linearity
    stops holding -- which is unbounded and unmeasurable from the data.
    """
    return n_usable // 2


def forecast_series(request: ForecastRequest) -> ForecastOutcome:  # noqa: PLR0911, PLR0912
    """Fit, judge, and project -- or refuse with a remedy.

    The gates run in the order that produces the most useful refusal:
    input kind, then quantity, then coverage, then structural breaks,
    then the fit itself.
    """
    if request.is_counter:
        return ForecastRefused(
            reason=RefusalReason.COUNTER_SERIES,
            remedy=(
                "Rate-convert the counter upstream. A reset to zero reads as a "
                "large negative slope and yields a confident 'never exhausts'."
            ),
        )
    if request.horizon_buckets < 1:
        raise ValueError(f"horizon_buckets must be at least 1; got {request.horizon_buckets}.")

    usable = _usable(request.points, request.reduction)
    if len(usable) < MIN_POINTS_FOR_FIT:
        return ForecastRefused(
            reason=RefusalReason.DEGREES_OF_FREEDOM,
            remedy=(
                f"{len(usable)} usable buckets; a residual variance needs at least "
                f"{MIN_POINTS_FOR_FIT}. At two points the fit is perfect by "
                "construction and the interval has zero width."
            ),
        )
    if len(usable) > MAX_BUCKETS:
        return ForecastRefused(
            reason=RefusalReason.TOO_MANY_BUCKETS,
            remedy=f"Coarsen the bucket width; {len(usable)} exceeds {MAX_BUCKETS}.",
        )

    ys_raw: list[float] = [
        float(value)
        for value in (point.reduce(request.reduction) for point in usable)
        if value is not None
    ]

    if request.transform is TransformKind.LOG and any(value <= 0.0 for value in ys_raw):
        return ForecastRefused(
            reason=RefusalReason.LOG_REQUIRES_POSITIVE,
            remedy=(
                "A log fit needs strictly positive values; the series contains "
                "zero or negative samples."
            ),
        )

    coverage = assess_coverage(request.points)
    if coverage.ratio < MIN_COVERAGE:
        return ForecastRefused(
            reason=RefusalReason.INSUFFICIENT_COVERAGE,
            remedy=(
                f"Coverage is {coverage.ratio:.0%}, below {MIN_COVERAGE:.0%}. "
                f"{coverage.total_buckets - coverage.measured_buckets} of "
                f"{coverage.total_buckets} buckets were never measured."
            ),
        )
    if coverage.largest_gap_ratio > MAX_GAP_RATIO:
        return ForecastRefused(
            reason=RefusalReason.INSUFFICIENT_COVERAGE,
            remedy=(
                f"The largest gap spans {coverage.largest_gap_buckets} buckets "
                f"({coverage.largest_gap_ratio:.0%} of the window). This is two "
                "series with a guess between them, not one series."
            ),
        )

    shift_at = detect_level_shift(ys_raw)
    if shift_at is not None:
        return ForecastRefused(
            reason=RefusalReason.LEVEL_SHIFT_SUSPECTED,
            remedy=(
                f"A discontinuity at {usable[shift_at].bucket_start.isoformat()} "
                "exceeds ten times the median successive difference. Split the "
                "series or declare an excluded window; averaging across a step "
                "and calling it a trend is not something this engine will do."
            ),
        )

    saturation = assess_saturation(ys_raw, request.bound)
    if saturation is SaturationState.CENSORED_AT_BOUND:
        return ForecastRefused(
            reason=RefusalReason.SATURATED_LEVEL,
            remedy=(
                f"At least {SATURATION_BUCKET_RATIO:.0%} of buckets sit at "
                f"{SATURATION_LEVEL_RATIO:.0%} of the ceiling. The level is "
                "censored, so its flat slope means saturation rather than "
                "stability. Forecast time-spent-at-bound instead, which is not "
                "censored."
            ),
        )

    seasonality = assess_seasonality([point.index for point in usable], ys_raw)
    fitted = usable
    if seasonality in (
        SeasonalityAssessment.WEEKLY_DETECTED,
        SeasonalityAssessment.INDETERMINATE,
    ):
        fitted = _trim_to_whole_weeks(usable)
        if len(fitted) < MIN_POINTS_FOR_FIT:
            fitted = list(usable)

    xs = [float(point.index) for point in fitted]
    ys = [float(point.reduce(request.reduction) or 0.0) for point in fitted]
    if request.transform is TransformKind.LOG:
        ys = [math.log(value) for value in ys]

    # Measured against what is actually fitted, not what arrived: whole-week
    # trimming can drop up to six buckets, and a claim floor that counts
    # buckets the regression never saw is not a floor.
    if len(fitted) < request.min_buckets_for_claim:
        return ForecastRefused(
            reason=RefusalReason.INSUFFICIENT_HISTORY,
            remedy=(
                f"{request.min_buckets_for_claim - len(fitted)} more buckets are "
                f"needed; {len(fitted)} of {request.min_buckets_for_claim} after "
                "trimming to whole weeks. At this "
                "length the smallest detectable trend is larger than the trend "
                "being looked for."
            ),
        )

    horizon_cap = _horizon_cap(len(fitted))
    if request.horizon_buckets > horizon_cap:
        return ForecastRefused(
            reason=RefusalReason.HORIZON_EXCEEDS_HISTORY,
            remedy=(
                f"A {request.horizon_buckets}-bucket horizon from {len(fitted)} "
                f"buckets of history exceeds the n/2 cap of {horizon_cap}. The "
                "band would quantify sampling error only, while the real risk is "
                "that linearity stops holding."
            ),
        )

    try:
        primary, divergence, reason = _choose_estimator(xs, ys, request, seasonality)
    except ValueError as error:
        return ForecastRefused(
            reason=RefusalReason.DEGENERATE_X,
            remedy=str(error),
        )

    return _assemble(
        request=request,
        fitted=fitted,
        usable=usable,
        fit=primary,
        divergence=divergence,
        estimator_reason=reason,
        coverage=coverage,
        seasonality=seasonality,
        saturation=saturation,
        xs=xs,
        ys_raw=ys_raw,
    )


def _choose_estimator(
    xs: Sequence[float],
    ys: Sequence[float],
    request: ForecastRequest,
    seasonality: SeasonalityAssessment,
) -> tuple[LinearFit, float | None, str]:
    """Fit both estimators and pick, recording why.

    When weekly seasonality is in play the slope is taken from a 7-point
    centered moving average -- which annihilates a period-7 signal
    exactly -- while the error scale comes from the raw points about that
    line. Taking the scale from the smoothed series instead understates
    the interval by about sqrt(7); see
    :func:`app.capacity.regression.fit_from_line`.
    """
    ols = ols_fit(xs, ys)
    if seasonality is SeasonalityAssessment.WEEKLY_DETECTED:
        smoothed = _moving_average(ys, SEASONAL_WINDOW)
        paired = [(x, value) for x, value in zip(xs, smoothed, strict=True) if value is not None]
        if len(paired) >= MIN_POINTS_FOR_FIT:
            smooth_fit = ols_fit([x for x, _ in paired], [v for _, v in paired])
            ols = fit_from_line(
                smooth_fit.slope,
                smooth_fit.intercept,
                xs,
                ys,
                estimator=EstimatorKind.OLS,
            )

    sen = theil_sen_fit(xs, ys)
    scale = max(abs(sen.slope), request.materiality)
    divergence = abs(ols.slope - sen.slope) / scale if scale > 0.0 else None
    influential = influential_points(xs, ols)

    if divergence is not None and divergence > SLOPE_DIVERGENCE_LIMIT:
        return (
            sen,
            divergence,
            f"OLS and Theil-Sen slopes differ by {divergence:.0%} of the robust "
            "slope, so the least-squares line is being led by a few points.",
        )
    if influential:
        return (
            sen,
            divergence,
            f"{len(influential)} point(s) exceed Cook's 4/n influence screen; the "
            "robust line is reported and the points are listed rather than removed.",
        )
    return ols, divergence, "OLS and Theil-Sen agree; the parametric interval applies."


def _assemble(
    *,
    request: ForecastRequest,
    fitted: Sequence[BucketedPoint],
    usable: Sequence[BucketedPoint],
    fit: LinearFit,
    divergence: float | None,
    estimator_reason: str,
    coverage: CoverageReport,
    seasonality: SeasonalityAssessment,
    saturation: SaturationState,
    xs: Sequence[float],
    ys_raw: Sequence[float],
) -> ForecastOutcome:
    """Build the forecast, its qualifiers, and its projected points."""
    qualifiers: list[ForecastQualifier] = []
    trend, significant = _classify_trend(fit, request)

    if fit.estimator is EstimatorKind.THEIL_SEN:
        qualifiers.append(ForecastQualifier.OUTLIER_SENSITIVE)
        if fit.n < MIN_POINTS_FOR_QUANTILE_INTERVAL:
            return ForecastRefused(
                reason=RefusalReason.INSUFFICIENT_HISTORY,
                remedy=(
                    f"The robust estimator is required here, and its "
                    f"distribution-free band needs {MIN_POINTS_FOR_QUANTILE_INTERVAL} "
                    f"points to reach {request.confidence.value}% coverage; there "
                    f"are {fit.n}."
                ),
            )
    influential = influential_points(xs, fit)
    if influential:
        qualifiers.append(ForecastQualifier.HIGH_INFLUENCE_POINTS)
    if fit.r_squared is not None and fit.r_squared < LOW_R_SQUARED and significant:
        qualifiers.append(ForecastQualifier.LOW_EXPLANATORY_POWER)
    if seasonality is SeasonalityAssessment.INDETERMINATE:
        qualifiers.append(ForecastQualifier.SEASONALITY_UNASSESSED)
    if fit.variance_inflation > 1.0:
        qualifiers.append(ForecastQualifier.AUTOCORRELATION_INFLATED)
    if fit.fit_class is FitClass.CONSTANT and len(usable) >= STALE_SOURCE_MIN_BUCKETS:
        qualifiers.append(ForecastQualifier.SUSPECT_STALE_SOURCE)
    if saturation is SaturationState.APPROACHING_BOUND:
        qualifiers.append(ForecastQualifier.APPROACHING_BOUND)
    if len(usable) < MIN_BUCKETS_FOR_SEASONAL_CLAIM:
        qualifiers.append(ForecastQualifier.SHORT_HISTORY)
    qualifiers.append(ForecastQualifier.MODEL_RISK_UNQUANTIFIED)

    mean_divergence = _peak_to_mean_divergence(fitted, request)
    evidence = FitEvidence(
        n_usable=len(usable),
        reduction=request.reduction,
        estimator=fit.estimator,
        estimator_reason=estimator_reason,
        fit_class=fit.fit_class,
        r_squared=fit.r_squared,
        adjusted_r_squared=fit.adjusted_r_squared,
        residual_std=fit.residual_std,
        residual_cv=fit.residual_cv,
        t_slope=fit.t_slope,
        slope_significant=significant,
        durbin_watson=fit.durbin_watson,
        rho_estimate=fit.rho_estimate,
        variance_inflation=fit.variance_inflation,
        slope_divergence=divergence,
        coverage=coverage,
        seasonality=seasonality,
        saturation=saturation,
        influential_points=influential,
        assumptions_unverified=(
            "errors are independent across buckets",
            "error variance is constant across the horizon",
            "the linear relationship continues to hold beyond the observed window",
        ),
        peak_to_mean_divergence=mean_divergence,
    )

    last = fitted[-1]
    last_value = float(last.reduce(request.reduction) or 0.0)
    points, validity = _project(request, fit, fitted, trend)
    method = (
        IntervalMethod.RESIDUAL_QUANTILE
        if fit.estimator is EstimatorKind.THEIL_SEN
        else (
            IntervalMethod.CONSTANT_SERIES
            if fit.fit_class is FitClass.CONSTANT
            else IntervalMethod.STUDENT_T_PREDICTION
        )
    )
    semantics = (
        PointSemantics.MEDIAN if request.transform is TransformKind.LOG else PointSemantics.MEAN
    )
    return Forecast(
        points=points,
        fit=fit,
        trend_class=trend,
        validity=validity,
        point_semantics=semantics,
        interval_method=method,
        interval_meaning=(
            f"If the model's assumptions hold to this horizon, "
            f"{request.confidence.value}% of future single-bucket observations fall "
            f"inside this band. The upper edge is a one-sided "
            f"{100 - (100 - int(request.confidence.value)) // 2}% bound, which is "
            f"what the exhaustion date is read from."
        ),
        confidence=request.confidence,
        bucket=request.bucket,
        last_observed_at=last.bucket_start,
        last_observed_value=(
            last_value if request.transform is TransformKind.NONE else float(ys_raw[-1])
        ),
        qualifiers=tuple(qualifiers),
        evidence=evidence,
    )


def _classify_trend(fit: LinearFit, request: ForecastRequest) -> tuple[TrendClass, bool]:
    """Judge the slope against its own noise, not against R-squared.

    R-squared is the wrong gate: a series growing 100 GB/day with 1 GB of
    noise has R-squared near 1, and one growing 0.001 GB/day with the same
    noise has R-squared near 0 -- but "no meaningful growth" is a perfectly
    good answer for the second, and refusing to answer is not.
    """
    if fit.fit_class is FitClass.CONSTANT:
        return TrendClass.FLAT_WITHIN_NOISE, False
    if fit.t_slope is None:
        return TrendClass.FLAT_WITHIN_NOISE, False

    critical = t_quantile(ConfidenceLevel.NINETY_FIVE, fit.degrees_of_freedom)
    significant = abs(fit.t_slope) >= critical
    if not significant:
        return TrendClass.FLAT_WITHIN_NOISE, False

    projected_change = abs(fit.slope) * request.horizon_buckets
    if projected_change < request.materiality:
        return TrendClass.NEGLIGIBLE, True
    return (TrendClass.GROWING if fit.slope > 0 else TrendClass.DECLINING), True


def _peak_to_mean_divergence(
    points: Sequence[BucketedPoint], request: ForecastRequest
) -> float | None:
    """How much faster the peak is growing than the mean.

    A peak outrunning the mean is increasing burstiness -- a capacity
    event that a level forecast alone will not show.
    """
    if request.reduction is ReductionKind.MEAN:
        return None
    pairs = [(float(point.index), point.reduce(request.reduction), point.mean) for point in points]
    usable = [
        (x, reduced, mean) for x, reduced, mean in pairs if reduced is not None and mean is not None
    ]
    if len(usable) < MIN_POINTS_FOR_FIT:
        return None
    xs = [x for x, _, _ in usable]
    try:
        reduced_fit = ols_fit(xs, [value for _, value, _ in usable])
        mean_fit = ols_fit(xs, [value for _, _, value in usable])
    except ValueError:
        return None
    return reduced_fit.slope - mean_fit.slope


def _project(
    request: ForecastRequest,
    fit: LinearFit,
    fitted: Sequence[BucketedPoint],
    trend: TrendClass,
) -> tuple[tuple[ForecastPoint, ...], ForecastValidity]:
    """Emit the trajectory, stopping where the model stops being true.

    No points are emitted past the earliest bound crossing: the linear
    model is known-false beyond a hard ceiling, so the crossing *is* the
    answer, and continuing the line gives the "CPU 143% on March 4th"
    that a downstream date is then read off.
    """
    last = fitted[-1]
    upper = request.bound.upper
    lower = request.bound.lower
    points: list[ForecastPoint] = []
    validity = ForecastValidity.FULL_HORIZON

    for step in range(1, request.horizon_buckets + 1):
        index = last.index + step
        interval = _interval_at(fit, float(index), request.confidence)
        raw = fit.predict(float(index))
        if request.transform is TransformKind.LOG:
            raw = math.exp(raw)
            interval = Interval(
                lower=math.exp(interval.lower),
                upper=math.exp(interval.upper),
                confidence=interval.confidence,
                method=interval.method,
            )

        clipped_value = raw
        if upper is not None:
            clipped_value = min(clipped_value, upper)
        if lower is not None:
            clipped_value = max(clipped_value, lower)

        points.append(
            ForecastPoint(
                at=last.bucket_start + request.bucket * step,
                index=index,
                value=clipped_value,
                value_raw=raw,
                clipped=clipped_value != raw,
                interval=interval,
            )
        )
        if (
            upper is not None
            and request.bound.kind is BoundKind.HARD_PHYSICAL
            and interval.upper >= upper
            and trend is TrendClass.GROWING
        ):
            validity = ForecastValidity.TRUNCATED_AT_BOUND
            break

    return tuple(points), validity


def _interval_at(fit: LinearFit, x: float, confidence: ConfidenceLevel) -> Interval:
    """The right band for whichever estimator is primary."""
    if fit.fit_class is FitClass.CONSTANT:
        return Interval(
            lower=fit.intercept,
            upper=fit.intercept,
            confidence=confidence,
            method=IntervalMethod.CONSTANT_SERIES,
        )
    if fit.estimator is EstimatorKind.THEIL_SEN:
        return residual_quantile_interval(fit, x=x, confidence=confidence)
    return prediction_interval(fit, x=x, confidence=confidence)


@dataclass(frozen=True, slots=True)
class ExhaustionEstimate:
    """When a resource runs out, if that question has an answer.

    Every day field is ``None`` unless a crossing genuinely exists. Not
    ``inf`` (invalid JSON, and it sorts to the top of an urgency-ranked
    dashboard so the healthiest resource pages the on-call), not
    ``maxsize`` (renders as the year 275760), not ``0`` (reads as
    "exhausted now").
    """

    status: ExhaustionStatus
    days_point: float | None
    days_earliest: float | None
    days_latest: float | None
    exhaustion_at: datetime | None
    earliest_at: datetime | None
    ceiling: float | None
    ceiling_source: CeilingSource
    headroom_now: float | None
    resolution_days: float
    rationale: str


def estimate_exhaustion(  # noqa: PLR0911 - one return per ExhaustionStatus, by design
    forecast: Forecast,
    *,
    ceiling: float | None,
    ceiling_source: CeilingSource = CeilingSource.DECLARED,
) -> ExhaustionEstimate:
    """When the upper band, then the point forecast, reach the ceiling.

    The band crossing is found by scanning the emitted trajectory rather
    than solving ``(ceiling - intercept)/(slope - t*SE_slope)``. That
    shortcut is everywhere and wrong twice: it uses a confidence band on
    the *slope* instead of a prediction band on an *observation*, and it
    ignores the intercept's covariance with the slope. Because the true
    upper bound is a hyperbola, the shortcut's date is systematically
    *later* than the truth -- it under-warns, which is the direction that
    costs an outage.
    """
    bucket_days = forecast.bucket.total_seconds() / 86400.0
    if ceiling is None:
        return ExhaustionEstimate(
            status=ExhaustionStatus.UNBOUNDED_METRIC,
            days_point=None,
            days_earliest=None,
            days_latest=None,
            exhaustion_at=None,
            earliest_at=None,
            ceiling=None,
            ceiling_source=ceiling_source,
            headroom_now=None,
            resolution_days=bucket_days,
            rationale="No ceiling is declared for this metric, so exhaustion is undefined.",
        )

    headroom = ceiling - forecast.last_observed_value
    if forecast.last_observed_value >= ceiling:
        return ExhaustionEstimate(
            status=ExhaustionStatus.ALREADY_EXHAUSTED,
            days_point=0.0,
            days_earliest=0.0,
            days_latest=0.0,
            exhaustion_at=forecast.last_observed_at,
            earliest_at=forecast.last_observed_at,
            ceiling=ceiling,
            ceiling_source=ceiling_source,
            headroom_now=headroom,
            resolution_days=bucket_days,
            rationale=(
                f"The last observed value {forecast.last_observed_value:.4g} is at or "
                f"above the ceiling {ceiling:.4g}. This is a measurement, not a "
                "forecast."
            ),
        )

    if forecast.trend_class in (TrendClass.FLAT_WITHIN_NOISE, TrendClass.NEGLIGIBLE):
        status = ExhaustionStatus.NO_TREND
        rationale = (
            "No growth is distinguishable from noise, so no crossing exists to "
            "date. This is an answer, not a failure to compute one."
            if forecast.trend_class is TrendClass.FLAT_WITHIN_NOISE
            else "The trend is real but too small to matter over this horizon."
        )
        return _no_crossing(status, ceiling, ceiling_source, headroom, bucket_days, rationale)

    if forecast.trend_class is TrendClass.DECLINING:
        return _no_crossing(
            ExhaustionStatus.DECLINING,
            ceiling,
            ceiling_source,
            headroom,
            bucket_days,
            "Usage is falling; the ceiling is not approached from this trajectory.",
        )

    point_cross = next((point for point in forecast.points if point.value_raw >= ceiling), None)
    band_cross = next((point for point in forecast.points if point.interval.upper >= ceiling), None)

    if point_cross is None and band_cross is None:
        return _no_crossing(
            ExhaustionStatus.NOT_WITHIN_HORIZON,
            ceiling,
            ceiling_source,
            headroom,
            bucket_days,
            (
                f"Neither the projection nor its upper band reaches {ceiling:.4g} "
                f"within the {len(forecast.points)}-bucket horizon. Extrapolating "
                "further was refused, so the answer is genuinely unknown rather "
                "than 'no risk'."
            ),
        )

    def days_to(point: ForecastPoint | None) -> float | None:
        if point is None:
            return None
        return (point.at - forecast.last_observed_at).total_seconds() / 86400.0

    if point_cross is None:
        return ExhaustionEstimate(
            status=ExhaustionStatus.RISK_WITHIN_HORIZON,
            days_point=None,
            days_earliest=days_to(band_cross),
            days_latest=None,
            exhaustion_at=None,
            earliest_at=band_cross.at if band_cross else None,
            ceiling=ceiling,
            ceiling_source=ceiling_source,
            headroom_now=headroom,
            resolution_days=bucket_days,
            rationale=(
                f"The projection stays below {ceiling:.4g}, but the upper band "
                f"reaches it. Plausible-but-unlikely is a planning fact; collapsing "
                "it into 'no risk' is how capacity incidents happen."
            ),
        )

    return ExhaustionEstimate(
        status=ExhaustionStatus.WILL_EXHAUST,
        days_point=days_to(point_cross),
        days_earliest=days_to(band_cross),
        days_latest=None,
        exhaustion_at=point_cross.at,
        earliest_at=band_cross.at if band_cross else None,
        ceiling=ceiling,
        ceiling_source=ceiling_source,
        headroom_now=headroom,
        resolution_days=bucket_days,
        rationale=(
            f"The projection reaches {ceiling:.4g} at "
            f"{point_cross.at.date().isoformat()}; the upper band reaches it at "
            f"{band_cross.at.date().isoformat() if band_cross else 'the same time'}. "
            f"Display no finer than {bucket_days:g} day(s) -- the bucket width is "
            "the resolution the data actually has."
        ),
    )


def _no_crossing(
    status: ExhaustionStatus,
    ceiling: float,
    source: CeilingSource,
    headroom: float,
    bucket_days: float,
    rationale: str,
) -> ExhaustionEstimate:
    return ExhaustionEstimate(
        status=status,
        days_point=None,
        days_earliest=None,
        days_latest=None,
        exhaustion_at=None,
        earliest_at=None,
        ceiling=ceiling,
        ceiling_source=source,
        headroom_now=headroom,
        resolution_days=bucket_days,
        rationale=rationale,
    )


@dataclass(frozen=True, slots=True)
class GrowthTrend:
    """The rate of change, expressed the ways a planner asks for it."""

    trend_class: TrendClass
    slope_per_day: float | None
    slope_confidence_interval: Interval | None
    relative_growth_per_30d: float | None
    time_to_plus_50pct_days: float | None
    doubling_time_days: float | None


def growth_trend(forecast: Forecast, *, materiality: float = 0.0) -> GrowthTrend:
    """Rate of change, with the level-relative figures suppressed when the
    level is too small to divide by.

    ``doubling_time_days`` is ``None`` for linear fits, and that is not an
    omission: a linear trend's doubling time depends on the current level,
    so it is not a property of the trend at all. ``ln2/slope`` is
    dimensionally wrong and produces confident garbage.
    """
    fit = forecast.fit
    bucket_days = forecast.bucket.total_seconds() / 86400.0
    if forecast.trend_class is TrendClass.FLAT_WITHIN_NOISE:
        return GrowthTrend(
            trend_class=forecast.trend_class,
            slope_per_day=None,
            slope_confidence_interval=slope_confidence_interval(
                fit, confidence=forecast.confidence
            ),
            relative_growth_per_30d=None,
            time_to_plus_50pct_days=None,
            doubling_time_days=None,
        )

    per_day = fit.slope / bucket_days
    level = forecast.last_observed_value
    level_known = abs(level) > max(materiality, 0.0)

    relative = per_day * 30.0 / level if level_known else None
    to_plus_50 = (0.5 * level) / per_day if level_known and per_day > 0.0 else None
    doubling = (
        math.log(2.0) / per_day
        if forecast.point_semantics is PointSemantics.MEDIAN and per_day > 0.0
        else None
    )
    return GrowthTrend(
        trend_class=forecast.trend_class,
        slope_per_day=per_day,
        slope_confidence_interval=slope_confidence_interval(fit, confidence=forecast.confidence),
        relative_growth_per_30d=relative,
        time_to_plus_50pct_days=to_plus_50,
        doubling_time_days=doubling,
    )


@dataclass(frozen=True, slots=True)
class CapacityPlan:
    """What to buy, how much, and when to order it."""

    required_capacity_at_horizon: Interval | None
    recommended_provision: float | None
    headroom_policy: float
    lead_time_days: int
    order_by: datetime | None
    order_by_status: OrderByStatus
    rationale: str


def plan_capacity(
    forecast: Forecast,
    exhaustion: ExhaustionEstimate,
    *,
    headroom_policy: float,
    lead_time_days: int,
    now: datetime,
) -> CapacityPlan:
    """Turn a forecast into a procurement decision.

    Provisioning is sized against the *upper* band, not the point: the
    point is where usage lands half the time, and buying for that is
    buying for a coin flip.
    """
    horizon = forecast.at_horizon()
    if horizon is None:
        return CapacityPlan(
            required_capacity_at_horizon=None,
            recommended_provision=None,
            headroom_policy=headroom_policy,
            lead_time_days=lead_time_days,
            order_by=None,
            order_by_status=OrderByStatus.NOT_APPLICABLE,
            rationale="The forecast emitted no points, so there is nothing to size.",
        )

    recommended = horizon.interval.upper * (1.0 + headroom_policy)
    if exhaustion.earliest_at is None:
        return CapacityPlan(
            required_capacity_at_horizon=horizon.interval,
            recommended_provision=recommended,
            headroom_policy=headroom_policy,
            lead_time_days=lead_time_days,
            order_by=None,
            order_by_status=OrderByStatus.NOT_APPLICABLE,
            rationale=(
                f"No crossing within the horizon ({exhaustion.status.value}), so no "
                "order date follows. The sizing figure still applies if you are "
                "provisioning anyway."
            ),
        )

    order_by = exhaustion.earliest_at - timedelta(days=lead_time_days)
    overdue = order_by < now
    return CapacityPlan(
        required_capacity_at_horizon=horizon.interval,
        recommended_provision=recommended,
        headroom_policy=headroom_policy,
        lead_time_days=lead_time_days,
        order_by=order_by,
        order_by_status=OrderByStatus.OVERDUE if overdue else OrderByStatus.SCHEDULED,
        rationale=(
            f"Earliest credible exhaustion {exhaustion.earliest_at.date().isoformat()} "
            f"minus {lead_time_days} days of lead time gives "
            f"{order_by.date().isoformat()}"
            + (f", which is {(now - order_by).days} days in the past." if overdue else ".")
        ),
    )


__all__ = [
    "LEVEL_SHIFT_MASD_MULTIPLIER",
    "MIN_BUCKETS_FOR_CLAIM",
    "MIN_BUCKETS_FOR_SEASONAL_CLAIM",
    "MIN_COVERAGE",
    "CapacityPlan",
    "ExhaustionEstimate",
    "FitEvidence",
    "Forecast",
    "ForecastOutcome",
    "ForecastPoint",
    "ForecastRefused",
    "ForecastRequest",
    "GrowthTrend",
    "MetricBound",
    "assess_saturation",
    "assess_seasonality",
    "detect_level_shift",
    "estimate_exhaustion",
    "forecast_series",
    "growth_trend",
    "plan_capacity",
]
