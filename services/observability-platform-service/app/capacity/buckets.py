"""Turning raw samples into the regular grid a regression needs.

Three decisions here that look like details and are not:

**Fixed-width UTC buckets, never local calendar days.** Local-day
bucketing puts a 23-hour and a 25-hour bucket into every series that
crosses a DST boundary. A peak survives that; a mean is biased and a
per-bucket sum is off by 4% -- and unequal widths silently break the
``Sxx = n(n^2-1)/12`` identity that the engine's sensitivity thresholds
are derived from.

**Empty buckets are emitted, never dropped, and never zero-filled.**
Dropping them makes three days of scattered samples look like a
contiguous thirty-day series. Zero-filling is worse: a collector outage
reads as usage falling to zero, which drags the slope negative and
reports "never exhausts" for a disk that is filling. Every statistic on
an unmeasured bucket is ``None``, and the type says so.

**Integer bucket indices, not epoch seconds.** See
:func:`app.capacity.regression.ols_fit` for what epoch floats do to the
arithmetic.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.capacity.enums import ReductionKind

MIN_SAMPLES_FOR_P95 = 20
"""Nearest-rank p95 sits at index ``ceil(0.95n)``, which is strictly
below ``n`` only when ``n > 20``. At n = 19 the "p95" *is* the maximum
wearing a different label, so below this the field is ``None``."""


@dataclass(frozen=True, slots=True)
class Sample:
    """One raw observation.

    Raises:
        ValueError: On a naive datetime. A tz-naive timestamp cannot be
            placed on a UTC grid without guessing, and the guess is wrong
            twice a year.
    """

    at: datetime
    value: float

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.utcoffset() is None:
            raise ValueError(
                f"Sample at {self.at!r} is timezone-naive; capacity bucketing needs "
                "an unambiguous UTC instant."
            )


@dataclass(frozen=True, slots=True)
class TimeWindow:
    """A half-open interval, ``[start, end)``."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(f"Window end {self.end!r} is not after start {self.start!r}.")

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment < self.end

    def overlaps(self, start: datetime, end: datetime) -> bool:
        return start < self.end and self.start < end


@dataclass(frozen=True, slots=True)
class BucketedPoint:
    """One grid cell, with every statistic optional and honest.

    ``sample_count == 0`` and ``peak is None`` together say "nothing was
    measured here". No arithmetic in this package treats that as a zero.
    """

    index: int
    bucket_start: datetime
    sample_count: int
    expected_samples: int | None
    coverage: float | None
    peak: float | None
    mean: float | None
    p95: float | None
    minimum: float | None
    excluded: bool

    @property
    def is_measured(self) -> bool:
        return self.sample_count > 0 and not self.excluded

    def reduce(self, kind: ReductionKind) -> float | None:
        """The requested statistic, or ``None`` when it does not exist."""
        return {
            ReductionKind.PEAK: self.peak,
            ReductionKind.P95: self.p95,
            ReductionKind.MEAN: self.mean,
            ReductionKind.MINIMUM: self.minimum,
        }[kind]


def nearest_rank_p95(values: Sequence[float]) -> float | None:
    """Nearest-rank 95th percentile, or ``None`` when it would be the max.

    Returning the maximum under a p95 label is the quiet version of this
    bug: the number is plausible, the field name is a lie, and every
    downstream headroom calculation inherits the burst it was meant to
    exclude.
    """
    if len(values) < MIN_SAMPLES_FOR_P95:
        return None
    ordered = sorted(values)
    rank = math.ceil(0.95 * len(ordered))
    return ordered[rank - 1]


def bucket_samples(
    samples: Sequence[Sample],
    *,
    bucket: timedelta,
    origin: datetime,
    expected_cadence: timedelta | None = None,
    excluded_windows: Sequence[TimeWindow] = (),
) -> tuple[BucketedPoint, ...]:
    """Place samples on a fixed UTC grid, emitting every bucket in span.

    Buckets with no samples are returned with ``sample_count = 0`` and all
    statistics ``None`` -- present in the series so gaps are visible and
    countable, absent from any arithmetic.

    Raises:
        ValueError: On a non-positive bucket width or a naive origin.
    """
    if bucket <= timedelta(0):
        raise ValueError(f"Bucket width must be positive; got {bucket!r}.")
    if origin.tzinfo is None or origin.utcoffset() is None:
        raise ValueError(f"Origin {origin!r} is timezone-naive.")
    if not samples:
        return ()

    width = bucket.total_seconds()
    ordered = sorted(samples, key=lambda sample: sample.at)
    first_index = math.floor((ordered[0].at - origin).total_seconds() / width)
    last_index = math.floor((ordered[-1].at - origin).total_seconds() / width)

    grouped: dict[int, list[float]] = {}
    for sample in ordered:
        index = math.floor((sample.at - origin).total_seconds() / width)
        grouped.setdefault(index, []).append(sample.value)

    expected = (
        max(1, round(width / expected_cadence.total_seconds()))
        if expected_cadence is not None and expected_cadence > timedelta(0)
        else None
    )

    points: list[BucketedPoint] = []
    for index in range(first_index, last_index + 1):
        start = origin + bucket * index
        end = start + bucket
        values = grouped.get(index, [])
        excluded = any(window.overlaps(start, end) for window in excluded_windows)
        count = len(values)
        points.append(
            BucketedPoint(
                index=index,
                bucket_start=start,
                sample_count=count,
                expected_samples=expected,
                coverage=None if expected is None else min(1.0, count / expected),
                peak=max(values) if values else None,
                mean=math.fsum(values) / count if values else None,
                p95=nearest_rank_p95(values),
                minimum=min(values) if values else None,
                excluded=excluded,
            )
        )
    return tuple(points)


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """How much of the window was actually observed.

    ``largest_gap_buckets`` is reported separately from the ratio because
    the two fail differently: 80% coverage scattered evenly is a usable
    series, and 80% coverage with a six-day hole in the middle is two
    series with a guess between them.
    """

    total_buckets: int
    measured_buckets: int
    excluded_buckets: int
    ratio: float
    largest_gap_buckets: int
    largest_gap_ratio: float


def assess_coverage(points: Sequence[BucketedPoint]) -> CoverageReport:
    """Count what was measured, what was excluded, and the biggest hole."""
    total = len(points)
    if total == 0:
        return CoverageReport(0, 0, 0, 0.0, 0, 0.0)

    measured = sum(1 for point in points if point.is_measured)
    excluded = sum(1 for point in points if point.excluded)

    longest = 0
    running = 0
    for point in points:
        if point.is_measured:
            running = 0
        else:
            running += 1
            longest = max(longest, running)

    return CoverageReport(
        total_buckets=total,
        measured_buckets=measured,
        excluded_buckets=excluded,
        ratio=measured / total,
        largest_gap_buckets=longest,
        largest_gap_ratio=longest / total,
    )


__all__ = [
    "MIN_SAMPLES_FOR_P95",
    "BucketedPoint",
    "CoverageReport",
    "Sample",
    "TimeWindow",
    "assess_coverage",
    "bucket_samples",
    "nearest_rank_p95",
]
