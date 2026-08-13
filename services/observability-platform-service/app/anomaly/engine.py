"""Anomaly detection (docs/064 "ANOMALY DETECTION").

Deterministic, explainable, and the same answer twice. No model: the
spec's DO NOT IMPLEMENT list rules out commercial observability SaaS, and
an operator woken at 3am by a detector that cannot say *why* will stop
trusting it long before it is ever right.

**Mean and standard deviation are the wrong tools here.** Infrastructure
metrics are heavy-tailed and seasonal, and both statistics are dominated
by the very outliers being looked for -- one 100x spike inflates sigma
enough that the next three real spikes fall inside 3-sigma. This module
uses the median and the *median absolute deviation*, which have a
breakdown point of 50%: half the data can be arbitrarily corrupted before
the estimate moves.

**The baseline excludes the most recent window.** A live incident is
always at the *end* of the series, and once it covers more than half of
it the median moves inside the incident. The detector then not only stops
flagging the outage -- it starts flagging the healthy period before it as
anomalous, inverting the verdict at exactly the moment someone is
reading it.

**Every detection says what was expected and what arrived.** A bare
boolean is not actionable; "6.2 robust deviations above a median of 120ms
built from 2016 samples" is.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.models.enums import AnomalyMethod, AnomalySeverity, AnomalyShape

MAD_TO_SIGMA = 1.4826
"""Scales a median absolute deviation to be comparable with a standard
deviation for normally distributed data. Without it a robust z-score is
about 1.48x smaller than the classical one and every threshold borrowed
from sigma-based practice fires far too late."""

DEFAULT_ROBUST_THRESHOLD = 3.5
"""Robust z above which a point is anomalous. 3.5 rather than 3.0 because
MAD-based scores on real infrastructure metrics are heavier-tailed than
the normal distribution the classical figure assumes, and 3.0 produces a
steady drip of false positives on any metric with a daily shape."""

MIN_HISTORY_POINTS = 30
"""Below this, no statistical claim is honest. The engine refuses rather
than producing a detection from six samples."""

MIN_SEASONAL_CYCLES = 3
"""Complete cycles required before a seasonal comparison is made. Two is
enough to see a pattern and not enough to distinguish it from a
coincidence."""

LEVEL_SHIFT_MIN_POINTS = 5
"""Consecutive deviating points that make a level shift rather than a
spike. The two need different responses: a spike that has recovered needs
none."""

MIN_DOMINANCE = 0.6
"""Share of samples that must sit on one exact value before a series is
treated as holding a discrete level -- see
:func:`detect_level_departure`."""

LEVEL_DEAD_BAND = 1e-6
"""Relative difference from the held level below which a sample counts as
the same level. Stops float noise in the last decimal place from reading
as a level change."""

MIN_POINTS_FOR_A_SPAN = 2
"""Below this there is no elapsed time to measure cycles against."""

MIN_MAD_FLOOR = 1e-9
"""Below this a spread estimate is treated as zero. Dividing by it yields
infinity for any departure at all, which would report a metric that moved
from 5 to 5.0000000001 as infinitely anomalous."""

SEVERITY_BANDS: tuple[tuple[float, AnomalySeverity], ...] = (
    (10.0, AnomalySeverity.CRITICAL),
    (6.0, AnomalySeverity.HIGH),
    (4.5, AnomalySeverity.MEDIUM),
)
"""Robust-z bands, most severe first. Anything above the detection
threshold but below the lowest band is ``LOW``."""


@dataclass(frozen=True, slots=True)
class Point:
    """One timestamped sample."""

    at: datetime
    value: float


@dataclass(frozen=True, slots=True)
class Baseline:
    """What "normal" was, and how much evidence it rests on.

    ``mad`` is the *scaled* median absolute deviation, already multiplied
    by :data:`MAD_TO_SIGMA`, so callers never have to remember whether the
    scaling has been applied.
    """

    median: float
    mad: float
    sample_count: int
    low: float
    high: float
    is_degenerate: bool
    spread_source: str = "mad"

    @property
    def is_usable(self) -> bool:
        return self.sample_count >= MIN_HISTORY_POINTS and not self.is_degenerate


@dataclass(frozen=True, slots=True)
class Detection:
    """One anomaly, with the evidence for it."""

    at: datetime
    observed: float
    expected: float | None
    expected_low: float | None
    expected_high: float | None
    deviation: float | None
    method: AnomalyMethod
    shape: AnomalyShape
    severity: AnomalySeverity
    baseline_sample_count: int
    rationale: str


@dataclass(frozen=True, slots=True)
class DetectionOutcome:
    """What a detection pass concluded, including concluding nothing.

    A refusal is a first-class result. ``refusal_reason`` is set exactly
    when no claim could be made, and it says what was missing -- a caller
    that cannot tell "nothing is wrong" from "I could not look" will
    eventually assume the first.
    """

    detections: list[Detection] = field(default_factory=list)
    baseline: Baseline | None = None
    evaluated_points: int = 0
    refusal_reason: str | None = None

    @property
    def could_evaluate(self) -> bool:
        return self.refusal_reason is None


def compute_baseline(
    values: Sequence[float], *, threshold: float = DEFAULT_ROBUST_THRESHOLD
) -> Baseline:
    """The robust centre and spread of *values*.

    Uses median and MAD rather than mean and standard deviation. A single
    100x spike moves the mean by 100/n and the standard deviation by far
    more; it moves the median by at most one rank.

    **A MAD of zero is reported as degenerate rather than patched.** It
    means more than half the samples sit on exactly the median -- routine
    for integer gauges like replica count or queue depth. Substituting the
    mean absolute deviation there looks like a fix and is not: that
    statistic inflates with the very contamination it would have to
    survive, so a one-sample blip stays visible while a twenty-sample
    outage hides itself, which is the mean-and-sigma failure this module
    exists to avoid. Discrete-level series belong to
    :func:`detect_level_departure`, which needs no scale estimate at all.
    """
    if not values:
        return Baseline(
            median=0.0,
            mad=0.0,
            sample_count=0,
            low=0.0,
            high=0.0,
            is_degenerate=True,
            spread_source="none",
        )

    median = statistics.median(values)
    absolute_deviations = [abs(value - median) for value in values]
    mad = statistics.median(absolute_deviations) * MAD_TO_SIGMA
    degenerate = mad < MIN_MAD_FLOOR
    return Baseline(
        median=median,
        mad=mad,
        sample_count=len(values),
        low=median - threshold * mad,
        high=median + threshold * mad,
        is_degenerate=degenerate,
        spread_source="none" if degenerate else "mad",
    )


def robust_z(value: float, baseline: Baseline) -> float | None:
    """How many robust deviations *value* sits from the baseline centre.

    ``None`` for a degenerate baseline. A constant series has no spread,
    and reporting an infinite z-score for a metric that moved from 5 to
    5.0001 is worse than admitting the test does not apply.
    """
    if baseline.is_degenerate or baseline.mad < MIN_MAD_FLOOR:
        return None
    return (value - baseline.median) / baseline.mad


def _severity_for(deviation: float) -> AnomalySeverity:
    magnitude = abs(deviation)
    for cutoff, severity in SEVERITY_BANDS:
        if magnitude >= cutoff:
            return severity
    return AnomalySeverity.LOW


def detect_statistical(
    points: Sequence[Point],
    *,
    threshold: float = DEFAULT_ROBUST_THRESHOLD,
    min_history: int = MIN_HISTORY_POINTS,
    exclude_recent: int = 0,
    baseline: Baseline | None = None,
) -> DetectionOutcome:
    """Points that sit outside the robust expectation.

    ``exclude_recent`` trailing points are still *evaluated* but do not
    contribute to what "normal" means. Set it to at least the length of an
    incident you would consider plausible; leaving it at zero means a long
    enough outage eventually defines itself as the baseline.

    Pass an explicit ``baseline`` to score against a period established
    elsewhere -- a known-good week, say -- rather than against the series
    being scored.
    """
    if len(points) < min_history:
        return DetectionOutcome(
            evaluated_points=0,
            refusal_reason=(
                f"{len(points)} points is below the {min_history} needed for a "
                "statistical claim. This is not a statement that nothing is wrong."
            ),
        )
    if exclude_recent < 0:
        raise ValueError(f"exclude_recent must not be negative; got {exclude_recent}.")

    ordered = sorted(points, key=lambda point: point.at)
    if baseline is None:
        retained = ordered[: len(ordered) - exclude_recent] if exclude_recent else ordered
        if len(retained) < min_history:
            return DetectionOutcome(
                evaluated_points=len(ordered),
                refusal_reason=(
                    f"Excluding the {exclude_recent} most recent points leaves "
                    f"{len(retained)} for the baseline, below the {min_history} "
                    "required. Widen the history window rather than trusting a "
                    "baseline this thin."
                ),
            )
        baseline = compute_baseline([point.value for point in retained], threshold=threshold)

    if baseline.is_degenerate:
        return DetectionOutcome(
            baseline=baseline,
            evaluated_points=len(ordered),
            refusal_reason=(
                f"More than half the baseline samples sit on exactly "
                f"{baseline.median:.4g}, so there is no spread to measure a "
                "departure against. A metric that holds discrete levels is served "
                "by detect_level_departure(), which needs no scale estimate."
            ),
        )

    detections: list[Detection] = []
    for point in ordered:
        deviation = robust_z(point.value, baseline)
        if deviation is None or abs(deviation) < threshold:
            continue
        detections.append(
            Detection(
                at=point.at,
                observed=point.value,
                expected=baseline.median,
                expected_low=baseline.low,
                expected_high=baseline.high,
                deviation=deviation,
                method=AnomalyMethod.ROBUST_ZSCORE,
                shape=AnomalyShape.SPIKE if deviation > 0 else AnomalyShape.DIP,
                severity=_severity_for(deviation),
                baseline_sample_count=baseline.sample_count,
                rationale=(
                    f"{point.value:.4g} is {deviation:+.2f} robust deviations from a "
                    f"median of {baseline.median:.4g} (spread {baseline.mad:.4g} via "
                    f"{baseline.spread_source}) built from "
                    f"{baseline.sample_count} samples."
                ),
            )
        )
    return DetectionOutcome(detections=detections, baseline=baseline, evaluated_points=len(ordered))


def detect_level_departure(
    points: Sequence[Point],
    *,
    min_history: int = MIN_HISTORY_POINTS,
    min_dominance: float = MIN_DOMINANCE,
    dead_band: float = LEVEL_DEAD_BAND,
) -> DetectionOutcome:
    """Departures from a level the metric otherwise holds exactly.

    For series like replica count, queue depth, or leader count, where the
    value sits on one integer for hours at a time. There is no meaningful
    spread to score against -- the MAD is zero by construction -- and the
    question is not "how many deviations" but "it held at 3 for an hour
    and then read 0".

    Reports ``deviation=None`` deliberately: no distance in a distribution
    was measured, and inventing one would misrepresent the evidence.
    Applies only when one exact value covers ``min_dominance`` of the
    samples, so a continuous metric falls through to a refusal rather than
    a wrong answer.
    """
    if len(points) < min_history:
        return DetectionOutcome(
            evaluated_points=0,
            refusal_reason=(
                f"{len(points)} points is below the {min_history} needed to "
                "establish a held level."
            ),
        )

    ordered = sorted(points, key=lambda point: point.at)
    counts: dict[float, int] = {}
    for point in ordered:
        counts[point.value] = counts.get(point.value, 0) + 1
    level, held = max(counts.items(), key=lambda item: (item[1], -item[0]))
    dominance = held / len(ordered)

    if dominance < min_dominance:
        return DetectionOutcome(
            evaluated_points=len(ordered),
            refusal_reason=(
                f"The most common value covers only {dominance:.0%} of samples, "
                f"below the {min_dominance:.0%} that makes this a held level. This "
                "is a continuous metric; use detect_statistical()."
            ),
        )

    tolerance = max(abs(level) * dead_band, MIN_MAD_FLOOR)
    detections = [
        Detection(
            at=point.at,
            observed=point.value,
            expected=level,
            expected_low=level,
            expected_high=level,
            deviation=None,
            method=AnomalyMethod.LEVEL_SHIFT,
            shape=AnomalyShape.SPIKE if point.value > level else AnomalyShape.DIP,
            severity=AnomalySeverity.MEDIUM,
            baseline_sample_count=held,
            rationale=(
                f"The metric held at {level:.4g} for {held} of {len(ordered)} samples "
                f"({dominance:.0%}) and read {point.value:.4g} here."
            ),
        )
        for point in ordered
        if abs(point.value - level) > tolerance
    ]
    return DetectionOutcome(detections=detections, evaluated_points=len(ordered))


def detect_threshold(
    points: Sequence[Point],
    *,
    upper: float | None = None,
    lower: float | None = None,
) -> DetectionOutcome:
    """Points breaching a configured bound.

    No history requirement: a threshold is a stated policy rather than a
    statistical inference, and it applies to the first sample. The
    ``deviation`` is ``None`` for the same reason -- a breach is a fact
    about a configured line, not a distance in a distribution.

    Raises:
        ValueError: When neither bound is given, which is a rule that can
            never fire and would sit in a config file looking like
            coverage.
    """
    if upper is None and lower is None:
        raise ValueError(
            "A threshold rule needs an upper bound, a lower bound, or both; "
            "one with neither can never fire."
        )
    if upper is not None and lower is not None and lower > upper:
        raise ValueError(
            f"The lower bound ({lower}) is above the upper bound ({upper}), so no "
            "value can satisfy this rule."
        )

    detections: list[Detection] = []
    for point in sorted(points, key=lambda item: item.at):
        breached_high = upper is not None and point.value > upper
        breached_low = lower is not None and point.value < lower
        if not (breached_high or breached_low):
            continue
        bound = upper if breached_high else lower
        detections.append(
            Detection(
                at=point.at,
                observed=point.value,
                expected=None,
                expected_low=lower,
                expected_high=upper,
                deviation=None,
                method=AnomalyMethod.THRESHOLD,
                shape=AnomalyShape.SPIKE if breached_high else AnomalyShape.DIP,
                severity=AnomalySeverity.MEDIUM,
                baseline_sample_count=0,
                rationale=(
                    f"{point.value:.4g} breached the configured "
                    f"{'upper' if breached_high else 'lower'} bound of {bound:.4g}."
                ),
            )
        )
    return DetectionOutcome(detections=detections, evaluated_points=len(points))


def detect_seasonal(
    points: Sequence[Point],
    *,
    period: timedelta,
    threshold: float = DEFAULT_ROBUST_THRESHOLD,
    min_cycles: int = MIN_SEASONAL_CYCLES,
    tolerance: timedelta | None = None,
) -> DetectionOutcome:
    """Points that deviate from the same phase of previous cycles.

    A metric with a daily shape is not anomalous at its nightly trough --
    it is anomalous when its nightly trough is twice as deep as the last
    three nights. Comparing against the global distribution flags every
    night; comparing against the same hour of previous days flags the one
    that changed.
    """
    if period <= timedelta(0):
        raise ValueError(f"A seasonal period must be positive; got {period!r}.")

    ordered = sorted(points, key=lambda point: point.at)
    if len(ordered) < MIN_POINTS_FOR_A_SPAN:
        return DetectionOutcome(
            evaluated_points=len(ordered),
            refusal_reason="A single point cannot establish a cycle.",
        )

    span = ordered[-1].at - ordered[0].at
    cycles = span / period
    if cycles < min_cycles:
        return DetectionOutcome(
            evaluated_points=len(ordered),
            refusal_reason=(
                f"{cycles:.1f} cycles of history is below the {min_cycles} needed "
                "before a seasonal pattern can be told from a coincidence."
            ),
        )

    window = tolerance or period * 0.02
    detections: list[Detection] = []
    for index, point in enumerate(ordered):
        peers = _same_phase_peers(ordered, index, period=period, tolerance=window)
        if len(peers) < min_cycles - 1:
            continue
        baseline = compute_baseline(peers, threshold=threshold)
        deviation = robust_z(point.value, baseline)

        if baseline.is_degenerate:
            # Previous cycles all hit the same value at this phase -- a nightly
            # batch that processes exactly 1000 records, say. Skipping here
            # would blind the detector to the most predictable metrics it has;
            # scoring it would require a spread that does not exist. Report the
            # departure with no deviation attached.
            if abs(point.value - baseline.median) <= max(
                abs(baseline.median) * LEVEL_DEAD_BAND, MIN_MAD_FLOOR
            ):
                continue
            rationale = (
                f"Previous cycles all read {baseline.median:.4g} at this phase "
                f"({baseline.sample_count} samples); this one read {point.value:.4g}."
            )
            severity = AnomalySeverity.MEDIUM
        elif deviation is None or abs(deviation) < threshold:
            continue
        else:
            rationale = (
                f"{point.value:.4g} is {deviation:+.2f} robust deviations from the "
                f"median of {baseline.sample_count} samples at the same phase of "
                f"previous cycles ({baseline.median:.4g})."
            )
            severity = _severity_for(deviation)

        detections.append(
            Detection(
                at=point.at,
                observed=point.value,
                expected=baseline.median,
                expected_low=baseline.low,
                expected_high=baseline.high,
                deviation=deviation,
                method=AnomalyMethod.SEASONAL,
                shape=AnomalyShape.SEASONAL_DEVIATION,
                severity=severity,
                baseline_sample_count=baseline.sample_count,
                rationale=rationale,
            )
        )
    return DetectionOutcome(detections=detections, evaluated_points=len(ordered))


def _same_phase_peers(
    points: Sequence[Point], index: int, *, period: timedelta, tolerance: timedelta
) -> list[float]:
    """Values from earlier cycles at the same phase as ``points[index]``."""
    target = points[index].at
    peers: list[float] = []
    for offset, point in enumerate(points):
        if offset == index or point.at >= target:
            continue
        delta = target - point.at
        cycles = delta / period
        nearest = round(cycles)
        if nearest < 1:
            continue
        phase_error = abs(delta - period * nearest)
        if phase_error <= tolerance:
            peers.append(point.value)
    return peers


@dataclass(frozen=True, slots=True)
class ShapeVerdict:
    """What shape a run of deviating points makes."""

    shape: AnomalyShape
    start: datetime
    end: datetime
    point_count: int
    is_ongoing: bool
    rationale: str


def classify_shape(
    points: Sequence[Point],
    detections: Sequence[Detection],
    *,
    level_shift_min: int = LEVEL_SHIFT_MIN_POINTS,
) -> list[ShapeVerdict]:
    """Group detections into runs and name each run's shape.

    A spike that recovered, a level shift that is still in effect, and a
    trend are three different findings with three different responses.
    Reporting all of them as "anomaly" discards the only part an operator
    can act on.
    """
    if not detections:
        return []

    ordered_points = sorted(points, key=lambda point: point.at)
    last_at = ordered_points[-1].at if ordered_points else None
    ordered = sorted(detections, key=lambda item: item.at)
    index_of = {point.at: position for position, point in enumerate(ordered_points)}

    runs: list[list[Detection]] = [[ordered[0]]]
    for detection in ordered[1:]:
        previous = runs[-1][-1]
        adjacent = (
            detection.at in index_of
            and previous.at in index_of
            and index_of[detection.at] - index_of[previous.at] == 1
        )
        same_direction = (detection.deviation or 0) * (previous.deviation or 0) >= 0
        if adjacent and same_direction:
            runs[-1].append(detection)
        else:
            runs.append([detection])

    verdicts: list[ShapeVerdict] = []
    for run in runs:
        ongoing = last_at is not None and run[-1].at == last_at
        if len(run) >= level_shift_min:
            shape = AnomalyShape.LEVEL_SHIFT
            rationale = (
                f"{len(run)} consecutive deviating points: the level changed and "
                f"{'has not returned' if ongoing else 'later returned'}."
            )
        else:
            shape = run[0].shape
            rationale = (
                f"{len(run)} deviating point(s), "
                f"{'still in effect' if ongoing else 'already recovered'}."
            )
        verdicts.append(
            ShapeVerdict(
                shape=shape,
                start=run[0].at,
                end=run[-1].at,
                point_count=len(run),
                is_ongoing=ongoing,
                rationale=rationale,
            )
        )
    return verdicts


@dataclass(frozen=True, slots=True)
class TrendVerdict:
    """Whether a series is drifting, and how confidently."""

    has_trend: bool
    slope_per_point: float | None
    relative_change: float | None
    direction: str
    rationale: str


def detect_trend(
    points: Sequence[Point],
    *,
    min_history: int = MIN_HISTORY_POINTS,
    min_relative_change: float = 0.2,
) -> TrendVerdict:
    """Whether the series has moved between its first and last thirds.

    Compares the *medians* of the two thirds rather than fitting a line,
    because a single outlier at either end tilts a regression and a median
    ignores it. The middle third is skipped so a gradual change is not
    diluted by the transition itself.
    """
    if len(points) < min_history:
        return TrendVerdict(
            has_trend=False,
            slope_per_point=None,
            relative_change=None,
            direction="unknown",
            rationale=(
                f"{len(points)} points is below the {min_history} needed to claim a " "trend."
            ),
        )

    ordered = sorted(points, key=lambda point: point.at)
    third = len(ordered) // 3
    head = statistics.median([point.value for point in ordered[:third]])
    tail = statistics.median([point.value for point in ordered[-third:]])

    if abs(head) < MIN_MAD_FLOOR:
        return TrendVerdict(
            has_trend=False,
            slope_per_point=None,
            relative_change=None,
            direction="unknown",
            rationale=(
                "The earlier median is effectively zero, so a relative change is "
                "undefined -- any movement would divide by it."
            ),
        )

    relative = (tail - head) / abs(head)
    slope = (tail - head) / max(len(ordered) - third, 1)
    moving = abs(relative) >= min_relative_change
    return TrendVerdict(
        has_trend=moving,
        slope_per_point=slope,
        relative_change=relative,
        direction="rising" if relative > 0 else "falling" if relative < 0 else "flat",
        rationale=(
            f"Median moved from {head:.4g} to {tail:.4g} ({relative:+.1%}) between the "
            f"first and last third of {len(ordered)} points."
        ),
    )


def detect_forecast_deviation(
    observed: float,
    *,
    at: datetime,
    predicted: float,
    interval_low: float,
    interval_high: float,
) -> Detection | None:
    """Whether an observation fell outside its forecast interval.

    ``None`` when it did not. The interval is the claim; a point inside it
    is the forecast working, not an absence of information.

    Raises:
        ValueError: On an inverted interval, which would make every
            observation an anomaly.
    """
    if interval_low > interval_high:
        raise ValueError(
            f"The forecast interval is inverted ({interval_low} > {interval_high}); "
            "every observation would fall outside it."
        )
    if interval_low <= observed <= interval_high:
        return None

    width = interval_high - interval_low
    excess = observed - interval_high if observed > interval_high else interval_low - observed
    deviation = excess / (width / 2) if width > MIN_MAD_FLOOR else None
    return Detection(
        at=at,
        observed=observed,
        expected=predicted,
        expected_low=interval_low,
        expected_high=interval_high,
        deviation=deviation,
        method=AnomalyMethod.FORECAST_DEVIATION,
        shape=AnomalyShape.SPIKE if observed > interval_high else AnomalyShape.DIP,
        severity=_severity_for(deviation) if deviation is not None else AnomalySeverity.MEDIUM,
        baseline_sample_count=0,
        rationale=(
            f"{observed:.4g} fell outside the forecast interval "
            f"[{interval_low:.4g}, {interval_high:.4g}] around {predicted:.4g}."
        ),
    )


def merge_outcomes(*outcomes: DetectionOutcome) -> DetectionOutcome:
    """Combine several passes into one, deduplicating by timestamp.

    When two methods flag the same instant, the one with the larger
    absolute deviation is kept -- but a detection with no deviation (a
    threshold breach) never displaces one that has a measured distance,
    since the measured one carries more information for the same finding.
    """
    best: dict[datetime, Detection] = {}
    reasons: list[str] = []
    evaluated = 0
    baseline: Baseline | None = None

    for outcome in outcomes:
        evaluated = max(evaluated, outcome.evaluated_points)
        baseline = baseline or outcome.baseline
        if outcome.refusal_reason:
            reasons.append(outcome.refusal_reason)
        for detection in outcome.detections:
            existing = best.get(detection.at)
            if existing is None:
                best[detection.at] = detection
                continue
            if detection.deviation is not None and (
                existing.deviation is None or abs(detection.deviation) > abs(existing.deviation)
            ):
                best[detection.at] = detection

    detections = [best[key] for key in sorted(best)]
    # A refusal is only reported when nothing at all could be concluded;
    # one method refusing while another found something is not a refusal.
    refusal = reasons[0] if reasons and not detections and len(reasons) == len(outcomes) else None
    return DetectionOutcome(
        detections=detections,
        baseline=baseline,
        evaluated_points=evaluated,
        refusal_reason=refusal,
    )


__all__ = [
    "DEFAULT_ROBUST_THRESHOLD",
    "LEVEL_DEAD_BAND",
    "LEVEL_SHIFT_MIN_POINTS",
    "MAD_TO_SIGMA",
    "MIN_DOMINANCE",
    "MIN_HISTORY_POINTS",
    "MIN_SEASONAL_CYCLES",
    "SEVERITY_BANDS",
    "Baseline",
    "Detection",
    "DetectionOutcome",
    "Point",
    "ShapeVerdict",
    "TrendVerdict",
    "classify_shape",
    "compute_baseline",
    "detect_forecast_deviation",
    "detect_level_departure",
    "detect_seasonal",
    "detect_statistical",
    "detect_threshold",
    "detect_trend",
    "merge_outcomes",
    "robust_z",
]
