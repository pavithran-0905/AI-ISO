"""Regression and interval arithmetic for capacity forecasting.

Two estimators are always computed. OLS is the only one here with a
closed-form prediction interval, which is why it is primary; Theil-Sen
exists because OLS has a breakdown point of 1/n -- **one** point can drag
the line anywhere, and in this domain that point is always the same
thing: a backup spike, an incident where a disk filled and was cleaned, a
load test. When the two disagree materially, the disagreement itself is
the finding.

Everything is pure and deterministic: fixed-order pair generation, an
explicit even-n median rule, no ``set`` anywhere in the numeric path, and
no rounding. Two runs return identical floats.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.capacity.enums import ConfidenceLevel, EstimatorKind, FitClass, IntervalMethod

MIN_POINTS_FOR_FIT = 3
"""``s^2`` divides by ``n - 2``. At n = 2 the fit is perfect by
construction: R-squared 1.0, SSE 0, interval width 0 -- "disk full in
exactly 12 days, plus or minus nothing". The most convincing wrong output
this module could produce."""

MIN_POINTS_FOR_A_DIFFERENCE = 2
"""One point has no successive difference to take."""

MAX_BUCKETS = 400
"""Theil-Sen is O(n^2): 400 buckets is 79,800 pairs, which is nothing.
Above this the caller coarsens the bucket rather than have the engine
quietly perform a million operations."""

MIN_POINTS_FOR_QUANTILE_INTERVAL = 19
"""For a distribution-free interval from the extremes of n residuals,
P(a new residual lands inside) = (n-1)/(n+1). Reaching 0.90 needs n >= 19.
Below that a residual-quantile band cannot achieve its stated coverage,
so it is refused rather than mislabelled."""

RHO_INFLATION_THRESHOLD = 0.3
RHO_CAP = 0.9
"""Caps the AR(1) variance inflation at sqrt(19) ~ 4.36. Uncapped, an
estimate of rho near 1 sends the interval to infinity on the strength of
one noisy statistic."""

COOKS_D_MULTIPLIER = 4.0
"""Cook's distance threshold is 4/n, the conventional screen."""

# fmt: off
_T_TWO_SIDED: dict[ConfidenceLevel, tuple[float, ...]] = {
    # Index 0 is nu = 1. Literal tables rather than a dependency: reviewable,
    # and identical on every platform and library version. Kept as a grid
    # because a 40-line column of bare floats is unreviewable.
    ConfidenceLevel.EIGHTY: (
        3.078, 1.886, 1.638, 1.533, 1.476, 1.440, 1.415, 1.397, 1.383, 1.372,
        1.363, 1.356, 1.350, 1.345, 1.341, 1.337, 1.333, 1.330, 1.328, 1.325,
        1.323, 1.321, 1.319, 1.318, 1.316, 1.315, 1.314, 1.313, 1.311, 1.310,
        1.309, 1.309, 1.308, 1.307, 1.306, 1.306, 1.305, 1.304, 1.304, 1.303,
    ),
    ConfidenceLevel.NINETY: (
        6.314, 2.920, 2.353, 2.132, 2.015, 1.943, 1.895, 1.860, 1.833, 1.812,
        1.796, 1.782, 1.771, 1.761, 1.753, 1.746, 1.740, 1.734, 1.729, 1.725,
        1.721, 1.717, 1.714, 1.711, 1.708, 1.706, 1.703, 1.701, 1.699, 1.697,
        1.696, 1.694, 1.692, 1.691, 1.690, 1.688, 1.687, 1.686, 1.685, 1.684,
    ),
    ConfidenceLevel.NINETY_FIVE: (
        12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
        2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
        2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042,
        2.040, 2.037, 2.035, 2.032, 2.030, 2.028, 2.026, 2.024, 2.023, 2.021,
    ),
}
# fmt: on

_T_TABLE_MAX_DF = 40

_ACKLAM_A = (
    -3.969683028665376e01,
    2.209460984245205e02,
    -2.759285104469687e02,
    1.383577518672690e02,
    -3.066479806614716e01,
    2.506628277459239e00,
)
_ACKLAM_B = (
    -5.447609879822406e01,
    1.615858368580409e02,
    -1.556989798598866e02,
    6.680131188771972e01,
    -1.328068155288572e01,
)
_ACKLAM_CENTRAL_LOW = 0.02425
_ACKLAM_CENTRAL_HIGH = 1.0 - _ACKLAM_CENTRAL_LOW


def normal_quantile(p: float) -> float:
    """Inverse standard normal CDF, central region only.

    Acklam's rational approximation, |error| < 1.15e-9. Only the central
    branch is implemented because every quantile this module needs (0.90,
    0.95, 0.975) lives there; the tail branches would be unreachable code
    carrying their own opportunity to be wrong.

    Raises:
        ValueError: Outside the central region, rather than silently
            returning a tail approximation that was never written.
    """
    if not _ACKLAM_CENTRAL_LOW <= p <= _ACKLAM_CENTRAL_HIGH:
        raise ValueError(
            f"normal_quantile implements the central region only; {p} is outside "
            f"[{_ACKLAM_CENTRAL_LOW}, {_ACKLAM_CENTRAL_HIGH}]."
        )
    q = p - 0.5
    r = q * q
    numerator = (
        (
            (((_ACKLAM_A[0] * r + _ACKLAM_A[1]) * r + _ACKLAM_A[2]) * r + _ACKLAM_A[3]) * r
            + _ACKLAM_A[4]
        )
        * r
        + _ACKLAM_A[5]
    ) * q
    denominator = (
        (((_ACKLAM_B[0] * r + _ACKLAM_B[1]) * r + _ACKLAM_B[2]) * r + _ACKLAM_B[3]) * r
        + _ACKLAM_B[4]
    ) * r + 1.0
    return numerator / denominator


def t_quantile(confidence: ConfidenceLevel, degrees_of_freedom: int) -> float:
    """Two-sided critical value of Student's t.

    Table lookup to nu = 40, Cornish-Fisher expansion above it. The
    boundary is chosen where the expansion is within 0.001 of truth; below
    nu ~ 10 it is off by several percent, which is exactly why the table
    exists.

    Raises:
        ValueError: On nu < 1, which means the fit had no residual
            degrees of freedom and should have been refused earlier.
    """
    if degrees_of_freedom < 1:
        raise ValueError(
            f"t has no critical value at {degrees_of_freedom} degrees of freedom; "
            "a fit with fewer than 3 points should have been refused."
        )
    table = _T_TWO_SIDED[confidence]
    if degrees_of_freedom <= _T_TABLE_MAX_DF:
        return table[degrees_of_freedom - 1]

    z = normal_quantile(1.0 - confidence.two_sided_alpha / 2.0)
    nu = float(degrees_of_freedom)
    z3, z5, z7 = z**3, z**5, z**7
    return (
        z
        + (z3 + z) / (4.0 * nu)
        + (5.0 * z5 + 16.0 * z3 + 3.0 * z) / (96.0 * nu**2)
        + (3.0 * z7 + 19.0 * z5 + 17.0 * z3 - 15.0 * z) / (384.0 * nu**3)
    )


def _median(values: Sequence[float]) -> float:
    """Median with an explicit even-n rule and no ``set`` in sight."""
    ordered = sorted(values)
    count = len(ordered)
    middle = count // 2
    if count % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


@dataclass(frozen=True, slots=True)
class Interval:
    """A range, and what kind of range it is.

    ``method`` is carried because a prediction interval and a confidence
    interval look identical in JSON and mean entirely different things.
    """

    lower: float
    upper: float
    confidence: ConfidenceLevel
    method: IntervalMethod

    @property
    def width(self) -> float:
        return self.upper - self.lower


@dataclass(frozen=True, slots=True)
class LinearFit:
    """A fitted line with everything needed to judge it.

    ``r_squared`` is ``None`` -- never 0.0, never 1.0 -- when the series
    has no variance. A perfectly flat resource is the easiest forecast
    there is, and the usual ``if sst == 0: return 0.0`` guard then trips
    an R-squared floor and refuses it.
    """

    slope: float
    intercept: float
    n: int
    x_centroid: float
    sxx: float
    sse: float
    sst: float
    residual_std: float
    residuals: tuple[float, ...]
    estimator: EstimatorKind
    fit_class: FitClass
    r_squared: float | None
    adjusted_r_squared: float | None
    residual_cv: float | None
    se_slope: float | None
    t_slope: float | None
    durbin_watson: float | None
    rho_estimate: float | None
    variance_inflation: float

    def predict(self, x: float) -> float:
        return self.intercept + self.slope * x

    @property
    def degrees_of_freedom(self) -> int:
        return self.n - 2


def _durbin_watson(residuals: Sequence[float]) -> tuple[float, float] | None:
    """Durbin-Watson statistic and the implied AR(1) rho.

    Resource series are strongly autocorrelated -- today's disk usage is
    yesterday's plus a little -- and OLS residuals from autocorrelated
    data are much smaller than the true one-step-ahead error. The interval
    is then too narrow, by 3x at rho = 0.8, and no ordinary test notices.
    """
    denominator = sum(value * value for value in residuals)
    if denominator <= 0.0:
        return None
    numerator = sum((residuals[i] - residuals[i - 1]) ** 2 for i in range(1, len(residuals)))
    statistic = numerator / denominator
    return statistic, 1.0 - statistic / 2.0


def variance_inflation_for(rho: float | None) -> float:
    """AR(1) effective-sample-size inflation, capped.

    A widening a reviewer can reproduce, rather than a fudge factor.
    """
    if rho is None or rho <= RHO_INFLATION_THRESHOLD:
        return 1.0
    capped = min(rho, RHO_CAP)
    return math.sqrt((1.0 + capped) / (1.0 - capped))


def fit_from_line(
    slope: float,
    intercept: float,
    xs: Sequence[float],
    ys: Sequence[float],
    *,
    estimator: EstimatorKind,
    r_squared_applies: bool = True,
) -> LinearFit:
    """Build a :class:`LinearFit` for a given line against given data.

    Separated out because of one specific trap. When weekly seasonality
    is removed by fitting on a 7-point moving average, adjacent smoothed
    points share six of seven terms (correlation 6/7), so residuals taken
    *from the smoothed series* understate the true single-bucket error by
    about sqrt(7) = 2.65x. The interval is then 2.65x too narrow and
    every test still passes. So: the slope comes from the smoothed
    series, and the error scale comes from the raw points about that
    line. This function is how those two halves are joined.
    """
    n = len(xs)
    x_mean = math.fsum(xs) / n
    y_mean = math.fsum(ys) / n
    sxx = math.fsum((x - x_mean) ** 2 for x in xs)
    sst = math.fsum((y - y_mean) ** 2 for y in ys)

    residuals = tuple(y - (intercept + slope * x) for x, y in zip(xs, ys, strict=True))
    sse = math.fsum(residual * residual for residual in residuals)
    residual_std = math.sqrt(sse / (n - 2))
    constant = sst <= 0.0

    r_squared = None if constant or not r_squared_applies else 1.0 - sse / sst
    adjusted = None if r_squared is None else 1.0 - (1.0 - r_squared) * (n - 1) / (n - 2)
    autocorrelation = _durbin_watson(residuals)
    rho = autocorrelation[1] if autocorrelation else None
    se_slope = residual_std / math.sqrt(sxx) if residual_std > 0.0 and sxx > 0.0 else None
    return LinearFit(
        slope=slope,
        intercept=intercept,
        n=n,
        x_centroid=x_mean,
        sxx=sxx,
        sse=sse,
        sst=sst,
        residual_std=residual_std,
        residuals=residuals,
        estimator=estimator,
        fit_class=FitClass.CONSTANT if constant else FitClass.LINEAR,
        r_squared=r_squared,
        adjusted_r_squared=adjusted,
        residual_cv=residual_std / abs(y_mean) if abs(y_mean) > 0.0 else None,
        se_slope=se_slope,
        t_slope=None if se_slope is None else slope / se_slope,
        durbin_watson=autocorrelation[0] if autocorrelation else None,
        rho_estimate=rho,
        variance_inflation=variance_inflation_for(rho),
    )


def ols_fit(xs: Sequence[float], ys: Sequence[float]) -> LinearFit:
    """Ordinary least squares via the centered two-pass formulas.

    The computational form ``Sxx = sum(x^2) - sum(x)^2/n`` is avoided
    deliberately. With epoch seconds it subtracts two numbers near 3e18
    that agree in their first ten digits, and the slope comes out visibly
    wrong on perfectly clean data. Callers pass integer bucket indices
    *and* this function centers -- both defences, because either alone
    leaves the trap in place for the next editor.

    Raises:
        ValueError: On fewer than three points or zero spread in x. Both
            are refusals the caller must surface, not fits to attempt.
    """
    if len(xs) != len(ys):
        raise ValueError(f"x and y differ in length: {len(xs)} vs {len(ys)}.")
    n = len(xs)
    if n < MIN_POINTS_FOR_FIT:
        raise ValueError(
            f"{n} points cannot support a fit; s^2 divides by n - 2 and at n = 2 "
            "the residual variance is zero by construction."
        )

    x_mean = math.fsum(xs) / n
    y_mean = math.fsum(ys) / n
    sxx = math.fsum((x - x_mean) ** 2 for x in xs)
    if sxx <= 0.0:
        raise ValueError("Every point shares one x; there is no slope to estimate.")

    sxy = math.fsum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    sst = math.fsum((y - y_mean) ** 2 for y in ys)
    constant = sst <= 0.0
    slope = 0.0 if constant else sxy / sxx
    intercept = y_mean if constant else y_mean - slope * x_mean
    return fit_from_line(slope, intercept, xs, ys, estimator=EstimatorKind.OLS)


def theil_sen_fit(xs: Sequence[float], ys: Sequence[float]) -> LinearFit:
    """Median-of-pairwise-slopes fit.

    Asymptotic breakdown point 29.3%: roughly three points in ten can be
    arbitrarily corrupted before the line moves. Pairs are generated in
    fixed index order and the median uses an explicit even-n rule, because
    an engine whose contract is determinism must not depend on iteration
    order anywhere.

    Raises:
        ValueError: On fewer than three points, more than
            :data:`MAX_BUCKETS`, or no distinct x values.
    """
    if len(xs) != len(ys):
        raise ValueError(f"x and y differ in length: {len(xs)} vs {len(ys)}.")
    n = len(xs)
    if n < MIN_POINTS_FOR_FIT:
        raise ValueError(f"{n} points cannot support a fit.")
    if n > MAX_BUCKETS:
        raise ValueError(
            f"{n} buckets exceeds the {MAX_BUCKETS} cap ({n * (n - 1) // 2} pairs); "
            "coarsen the bucket width rather than fitting this many."
        )

    slopes = [
        (ys[j] - ys[i]) / (xs[j] - xs[i])
        for i in range(n)
        for j in range(i + 1, n)
        if xs[j] != xs[i]
    ]
    if not slopes:
        raise ValueError("Every point shares one x; there is no slope to estimate.")

    slope = _median(slopes)
    intercept = _median([y - slope * x for x, y in zip(xs, ys, strict=True)])
    # R-squared is withheld: it is maximised by the least-squares line by
    # construction, so quoting it for a different line invites a comparison
    # that always favours OLS regardless of which fit is the better answer.
    return fit_from_line(
        slope,
        intercept,
        xs,
        ys,
        estimator=EstimatorKind.THEIL_SEN,
        r_squared_applies=False,
    )


def prediction_interval(
    fit: LinearFit,
    *,
    x: float,
    confidence: ConfidenceLevel = ConfidenceLevel.NINETY,
    inflation: float | None = None,
) -> Interval:
    """A band on a *new single observation* at ``x``.

    The ``1.0 +`` under the square root is the entire point. Without it
    this is a confidence band on the fitted mean line, whose width tends
    to zero as n grows -- so more data would make the claim narrower and
    more wrong. With it the band converges to +/- t*s and never collapses.
    Both plot beautifully; nothing in an ordinary test distinguishes them.

    The invariant that does distinguish them, asserted below: **width at
    the centroid is always at least 2*t*s**.

    Meaning, exactly: if the linear model with independent,
    equal-variance, normally distributed errors is correct *and continues
    to hold to this horizon*, this fraction of future single-bucket
    observations at this horizon fall inside the band. Every clause is an
    assumption the data cannot confirm.
    """
    factor = fit.variance_inflation if inflation is None else inflation
    scale = fit.residual_std * factor
    leverage = 1.0 + 1.0 / fit.n + (x - fit.x_centroid) ** 2 / fit.sxx
    standard_error = scale * math.sqrt(leverage)
    half_width = t_quantile(confidence, fit.degrees_of_freedom) * standard_error

    # invariant: at x == x_centroid, leverage > 1, so half_width > t * scale.
    center = fit.predict(x)
    return Interval(
        lower=center - half_width,
        upper=center + half_width,
        confidence=confidence,
        method=IntervalMethod.STUDENT_T_PREDICTION,
    )


def residual_quantile_interval(
    fit: LinearFit, *, x: float, confidence: ConfidenceLevel = ConfidenceLevel.NINETY
) -> Interval:
    """A distribution-free band for a Theil-Sen line.

    Theil-Sen has no closed-form prediction interval, so the band is the
    empirical spread of its own residuals. That needs more points than the
    parametric version, not fewer.

    Raises:
        ValueError: Below :data:`MIN_POINTS_FOR_QUANTILE_INTERVAL`, where
            the stated coverage is not achievable from the sample at all.
    """
    if fit.n < MIN_POINTS_FOR_QUANTILE_INTERVAL:
        raise ValueError(
            f"{fit.n} residuals cannot support a distribution-free "
            f"{confidence.value}% band; (n-1)/(n+1) reaches 0.90 only at n >= "
            f"{MIN_POINTS_FOR_QUANTILE_INTERVAL}."
        )
    ordered = sorted(fit.residuals)
    tail = confidence.two_sided_alpha / 2.0
    lower_rank = max(0, math.floor(tail * (fit.n - 1)))
    upper_rank = min(fit.n - 1, math.ceil((1.0 - tail) * (fit.n - 1)))
    center = fit.predict(x)
    return Interval(
        lower=center + ordered[lower_rank],
        upper=center + ordered[upper_rank],
        confidence=confidence,
        method=IntervalMethod.RESIDUAL_QUANTILE,
    )


def slope_confidence_interval(
    fit: LinearFit, *, confidence: ConfidenceLevel = ConfidenceLevel.NINETY
) -> Interval | None:
    """A confidence interval on the slope -- a different object from the
    prediction interval, and typed as such so the two cannot be confused
    once serialized."""
    if fit.se_slope is None:
        return None
    half = t_quantile(confidence, fit.degrees_of_freedom) * fit.se_slope
    return Interval(
        lower=fit.slope - half,
        upper=fit.slope + half,
        confidence=confidence,
        method=IntervalMethod.STUDENT_T_PREDICTION,
    )


@dataclass(frozen=True, slots=True)
class InfluencePoint:
    """A single observation that is deciding the slope on its own."""

    index: int
    leverage: float
    cooks_distance: float
    residual: float


def influential_points(
    xs: Sequence[float], fit: LinearFit, *, threshold: float | None = None
) -> tuple[InfluencePoint, ...]:
    """Points whose Cook's distance exceeds 4/n.

    Reported, never removed. The Christmas backup that filled the disk is
    not noise -- it is the annual event that needed planning for, and a
    forecaster that deletes its outliers deletes its own warning.
    """
    if fit.residual_std <= 0.0 or fit.sxx <= 0.0:
        return ()
    cutoff = COOKS_D_MULTIPLIER / fit.n if threshold is None else threshold
    variance = fit.residual_std**2
    found: list[InfluencePoint] = []
    for index, (x, residual) in enumerate(zip(xs, fit.residuals, strict=True)):
        leverage = 1.0 / fit.n + (x - fit.x_centroid) ** 2 / fit.sxx
        if leverage >= 1.0:
            continue
        distance = (residual**2 / (2.0 * variance)) * leverage / (1.0 - leverage) ** 2
        if distance > cutoff:
            found.append(
                InfluencePoint(
                    index=index,
                    leverage=leverage,
                    cooks_distance=distance,
                    residual=residual,
                )
            )
    return tuple(found)


def median_absolute_successive_difference(values: Sequence[float]) -> float | None:
    """MASD -- the scale a level shift is measured against.

    For Gaussian differences ``median|delta| = 0.6745 * sigma_delta``, so
    the 10x screen used by the engine is about 6.7 sigma: a one-in-1e11
    event, therefore a discontinuity rather than noise.
    """
    if len(values) < MIN_POINTS_FOR_A_DIFFERENCE:
        return None
    return _median([abs(values[i] - values[i - 1]) for i in range(1, len(values))])


__all__ = [
    "COOKS_D_MULTIPLIER",
    "MAX_BUCKETS",
    "MIN_POINTS_FOR_FIT",
    "MIN_POINTS_FOR_QUANTILE_INTERVAL",
    "InfluencePoint",
    "Interval",
    "LinearFit",
    "fit_from_line",
    "influential_points",
    "median_absolute_successive_difference",
    "normal_quantile",
    "ols_fit",
    "prediction_interval",
    "residual_quantile_interval",
    "slope_confidence_interval",
    "t_quantile",
    "theil_sen_fit",
    "variance_inflation_for",
]
