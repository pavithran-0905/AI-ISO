"""Correlation, with every way it manufactures confidence guarded.

**Spearman, not Pearson.** On latency data a single spike creates the
correlation outright; a rank coefficient bounds any one point's leverage
by its rank displacement.

**No zero-filling.** During a collection gap every series drops to zero
at once and every service correlates with every other at rho near 1 -- a
monitoring outage renders as total systemic failure with perfect
agreement everywhere, and the top candidate is whichever service sorts
first. Buckets carry an observed mask and unpaired buckets are deleted
pairwise.

**A threshold that moves with n.** A fixed 0.7 is noise over nine buckets
and meaningless significance over five hundred.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.rca.enums import Unmeasurable

MIN_POINTS_FOR_CORRELATION = 2
"""Two points define a line and correlate perfectly; nothing below this
is a measurement."""

MIN_POINTS_FOR_AUTOCORRELATION = 3
"""A lag-1 series needs at least two pairs to say anything."""

MIN_PAIRED_BUCKETS = 8
"""At n = 8 the critical rho is 0.974. Below this the test has no power,
so a coefficient would be decoration."""

ALPHA = 0.01
Z_TWO_SIDED = 2.576
"""z for alpha = 0.01, feeding ``rho_crit(n) = 2.576 / sqrt(n - 1)``."""

MIN_RHO_FLOOR = 0.50
"""rho^2 = 0.25 of shared rank variance -- roughly the point at which
co-movement is visible to a human looking at the two charts."""

MIN_JACCARD = 0.50
"""The exact value when the sparser activity set is a subset of a denser
one twice its size."""

AUTOCORR_DIFFERENCE_AT = 0.80
"""Above this lag-1 autocorrelation the effective sample size collapses
to about 0.22n, invalidating the critical value by more than 2x. Two
independently trending series sit at rho = 0.95 with no relation
whatever, and step-function fixtures never expose it."""

MAX_LAG_CAP = 5
"""Beyond n/4 the shifted sample differs too much for coefficients across
lags to be comparable."""

PLATFORM_GAP_FRACTION = 0.50
"""More than half the instrumented estate silent in one bucket is a
collector failure before it is an outage."""


def rho_critical(n: int) -> float:
    """Significance threshold for Spearman's rho at ``n`` paired buckets.

    Floored at :data:`MIN_RHO_FLOOR` so a large sample cannot make a
    trivially small correlation "significant" and therefore actionable.
    """
    if n < MIN_PAIRED_BUCKETS:
        return 1.0
    return max(MIN_RHO_FLOOR, Z_TWO_SIDED / math.sqrt(n - 1))


@dataclass(frozen=True, slots=True)
class Series:
    """A bucketed signal with an explicit observation mask.

    ``observed`` is what keeps a collection gap from being read as a
    simultaneous drop to zero across the whole estate.
    """

    service: str
    values: tuple[float, ...]
    observed: tuple[bool, ...]
    bucket_seconds: float

    def __post_init__(self) -> None:
        if len(self.values) != len(self.observed):
            raise ValueError(
                f"Series for {self.service!r} has {len(self.values)} values and "
                f"{len(self.observed)} mask entries."
            )

    @property
    def active_buckets(self) -> frozenset[int]:
        return frozenset(
            index
            for index, (value, seen) in enumerate(zip(self.values, self.observed, strict=True))
            if seen and value > 0
        )


@dataclass(frozen=True, slots=True)
class CorrelationResult:
    """A coefficient, or a typed reason there is not one.

    ``coefficient`` and ``unmeasurable`` are mutually exclusive and one
    of them is always set. ``bucket_seconds`` travels with the result
    because a correlation is co-occurrence at bucket resolution and must
    never be read as precedence.
    """

    service: str
    coefficient: float | None
    paired_buckets: int
    excluded_buckets: int
    bucket_seconds: float
    lag_buckets: int
    lag_ambiguous: bool
    differenced: bool
    unmeasurable: Unmeasurable | None
    p_value: float | None = None
    adjusted_p_value: float | None = None
    significant: bool = False

    @property
    def is_measured(self) -> bool:
        return self.coefficient is not None


def _rank(values: Sequence[float]) -> list[float]:
    """Ranks with ties averaged, which is what makes Spearman valid."""
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        average = (position + end) / 2.0 + 1.0
        for index in order[position : end + 1]:
            ranks[index] = average
        position = end + 1
    return ranks


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    x_mean = math.fsum(xs) / len(xs)
    y_mean = math.fsum(ys) / len(ys)
    sxx = math.fsum((x - x_mean) ** 2 for x in xs)
    syy = math.fsum((y - y_mean) ** 2 for y in ys)
    if sxx <= 0.0 or syy <= 0.0:
        return None
    sxy = math.fsum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    return sxy / math.sqrt(sxx * syy)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Rank correlation. ``None`` when either side has no spread."""
    if len(xs) < MIN_POINTS_FOR_CORRELATION:
        return None
    return _pearson(_rank(xs), _rank(ys))


def lag_one_autocorrelation(values: Sequence[float]) -> float | None:
    """How much each bucket predicts the next one."""
    if len(values) < MIN_POINTS_FOR_AUTOCORRELATION:
        return None
    return _pearson(values[:-1], values[1:])


def difference(values: Sequence[float]) -> list[float]:
    """First differences, which remove a shared trend."""
    return [values[i] - values[i - 1] for i in range(1, len(values))]


def jaccard(
    left: frozenset[int], right: frozenset[int]
) -> tuple[float | None, Unmeasurable | None]:
    """Overlap of two activity sets.

    Empty against empty is ``None``, not 1.0. Two services that were both
    silent all window agree about nothing; scoring them as identical puts
    a pair with no evidence at the top of the ranking.
    """
    union = left | right
    if not union:
        return None, Unmeasurable.BOTH_SERIES_NEVER_ACTIVE
    return len(left & right) / len(union), None


def _paired(left: Series, right: Series, *, lag: int = 0) -> tuple[list[float], list[float], int]:
    """Buckets where both series were observed, offset by ``lag``.

    Pairwise deletion rather than imputation: a bucket nobody measured
    contributes nothing rather than contributing a zero.
    """
    xs: list[float] = []
    ys: list[float] = []
    excluded = 0
    for index in range(len(left.values)):
        shifted = index + lag
        if shifted < 0 or shifted >= len(right.values):
            continue
        if left.observed[index] and right.observed[shifted]:
            xs.append(left.values[index])
            ys.append(right.values[shifted])
        else:
            excluded += 1
    return xs, ys, excluded


def correlate(
    candidate: Series,
    symptom: Series,
    *,
    max_lag: int | None = None,
) -> CorrelationResult:
    """Spearman correlation between a candidate and a symptom series.

    Lags are searched, and **counted**: scanning ten lags and reporting
    the best is ten tests presented as one, and it always yields an
    attractive number. When the winner is within one standard error of
    the runner-up the result is marked ``lag_ambiguous``.

    Strongly autocorrelated inputs are first-differenced before
    correlating, because two independently trending series otherwise
    agree at rho near 0.95 while sharing no mechanism at all.
    """
    if candidate.bucket_seconds != symptom.bucket_seconds:
        raise ValueError(
            f"Cannot correlate series bucketed at {candidate.bucket_seconds}s and "
            f"{symptom.bucket_seconds}s; the coefficients would not be comparable."
        )

    xs, ys, excluded = _paired(candidate, symptom)
    if len(xs) < MIN_PAIRED_BUCKETS:
        return CorrelationResult(
            service=candidate.service,
            coefficient=None,
            paired_buckets=len(xs),
            excluded_buckets=excluded,
            bucket_seconds=candidate.bucket_seconds,
            lag_buckets=0,
            lag_ambiguous=False,
            differenced=False,
            unmeasurable=Unmeasurable.TOO_FEW_PAIRED_BUCKETS,
        )

    differenced = False
    for series in (xs, ys):
        autocorrelation = lag_one_autocorrelation(series)
        if autocorrelation is not None and autocorrelation >= AUTOCORR_DIFFERENCE_AT:
            differenced = True
            break

    cap = MAX_LAG_CAP if max_lag is None else max_lag
    limit = max(0, min(cap, len(xs) // 4))
    scored: list[tuple[float, int]] = []
    for lag in range(-limit, limit + 1):
        lag_xs, lag_ys, _ = _paired(candidate, symptom, lag=lag)
        if len(lag_xs) < MIN_PAIRED_BUCKETS:
            continue
        if differenced:
            lag_xs, lag_ys = difference(lag_xs), difference(lag_ys)
        value = spearman(lag_xs, lag_ys)
        if value is not None:
            scored.append((value, lag))

    if not scored:
        return CorrelationResult(
            service=candidate.service,
            coefficient=None,
            paired_buckets=len(xs),
            excluded_buckets=excluded,
            bucket_seconds=candidate.bucket_seconds,
            lag_buckets=0,
            lag_ambiguous=False,
            differenced=differenced,
            unmeasurable=Unmeasurable.ONE_SERIES_CONSTANT,
        )

    # Ties broken by the smaller absolute lag, then the earlier lag, so the
    # same inputs always name the same lag.
    scored.sort(key=lambda item: (-abs(item[0]), abs(item[1]), item[1]))
    best_value, best_lag = scored[0]
    standard_error = 1.0 / math.sqrt(len(xs) - 1)
    ambiguous = len(scored) > 1 and abs(abs(scored[1][0]) - abs(best_value)) < standard_error

    return CorrelationResult(
        service=candidate.service,
        coefficient=best_value,
        paired_buckets=len(xs),
        excluded_buckets=excluded,
        bucket_seconds=candidate.bucket_seconds,
        lag_buckets=best_lag,
        lag_ambiguous=ambiguous,
        differenced=differenced,
        unmeasurable=None,
        p_value=_approximate_p(best_value, len(xs)),
    )


def _approximate_p(coefficient: float, n: int) -> float:
    """Two-sided p from the large-sample normal approximation.

    Approximate on purpose, and labelled so: an exact permutation test
    would be defensible too, but a figure carried to four decimals here
    would imply a precision the bucketing does not have.
    """
    if n < MIN_POINTS_FOR_AUTOCORRELATION:
        return 1.0
    z = abs(coefficient) * math.sqrt(n - 1)
    return math.erfc(z / math.sqrt(2.0))


def holm_adjust(
    results: Sequence[CorrelationResult], *, alpha: float = ALPHA
) -> tuple[CorrelationResult, ...]:
    """Holm-Bonferroni across every comparison made.

    Two hundred candidates at alpha = 0.01 yields about two spurious
    significants per incident, and they look exactly like real ones.
    Every test in the suite tests one pair, so nothing catches it.
    """
    measured = [result for result in results if result.p_value is not None]
    unmeasured = [result for result in results if result.p_value is None]
    ordered = sorted(measured, key=lambda item: (item.p_value or 1.0, item.service))
    total = len(ordered)

    adjusted: list[CorrelationResult] = []
    running = 0.0
    still_significant = True
    for rank, result in enumerate(ordered):
        raw = result.p_value or 1.0
        value = min(1.0, max(running, raw * (total - rank)))
        running = value
        threshold = value <= alpha
        still_significant = still_significant and threshold
        critical = rho_critical(result.paired_buckets)
        adjusted.append(
            CorrelationResult(
                service=result.service,
                coefficient=result.coefficient,
                paired_buckets=result.paired_buckets,
                excluded_buckets=result.excluded_buckets,
                bucket_seconds=result.bucket_seconds,
                lag_buckets=result.lag_buckets,
                lag_ambiguous=result.lag_ambiguous,
                differenced=result.differenced,
                unmeasurable=None,
                p_value=raw,
                adjusted_p_value=value,
                significant=(
                    still_significant
                    and result.coefficient is not None
                    and abs(result.coefficient) >= critical
                ),
            )
        )
    return tuple(adjusted + unmeasured)


def expected_false_positives(comparisons: int, *, alpha: float = ALPHA) -> float:
    """How many significant results this many tests produce by chance."""
    return comparisons * alpha


def detect_platform_gaps(series: Sequence[Series]) -> tuple[int, ...]:
    """Buckets where most of the instrumented estate went silent at once.

    Surfaced as its own finding rather than analysed: a collector failure
    that reads as a simultaneous estate-wide outage is the single most
    misleading input this engine can receive.
    """
    if not series:
        return ()
    length = len(series[0].values)
    gaps: list[int] = []
    for index in range(length):
        silent = sum(
            1 for item in series if index < len(item.observed) and not item.observed[index]
        )
        if silent / len(series) > PLATFORM_GAP_FRACTION:
            gaps.append(index)
    return tuple(gaps)


def symptom_specificity(
    fingerprint_baseline_buckets: int, total_baseline_buckets: int
) -> float | None:
    """How unusual a symptom is, outside the incident window.

    Without it the chattiest service wins every incident, because high
    signal volume correlates with everything.
    """
    if total_baseline_buckets <= 0:
        return None
    return 1.0 - fingerprint_baseline_buckets / total_baseline_buckets


__all__ = [
    "ALPHA",
    "AUTOCORR_DIFFERENCE_AT",
    "MAX_LAG_CAP",
    "MIN_JACCARD",
    "MIN_PAIRED_BUCKETS",
    "MIN_RHO_FLOOR",
    "PLATFORM_GAP_FRACTION",
    "CorrelationResult",
    "Series",
    "correlate",
    "detect_platform_gaps",
    "difference",
    "expected_false_positives",
    "holm_adjust",
    "jaccard",
    "lag_one_autocorrelation",
    "rho_critical",
    "spearman",
    "symptom_specificity",
]
