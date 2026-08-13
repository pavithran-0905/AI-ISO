"""Usage records, coverage, and the storage integral.

The load-bearing idea: **a coverage window is a required input, not an
optional nicety.** It is the only thing that distinguishes "this project
spent nothing" from "the collector was down". Without one the engine has
no basis on which to emit :meth:`Money.measured_zero` and must emit
``None`` instead.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import pairwise

from app.cost.enums import CostSource, MeterBasis
from app.cost.money import WORKING_CONTEXT

BYTES_PER_GIB = Decimal(1024**3)

MAX_GAP_MULTIPLIER = 2
"""A hold tolerates one missed sample. Two consecutive misses is evidence
the collector stopped, not evidence the bytes stayed constant."""


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """One metered quantity over a half-open window.

    ``quantity`` may be negative: credits and refunds are usage records
    too, and clamping them at zero overstates every bill they appear in.
    """

    record_id: str
    source: str
    meter: str
    unit: str
    quantity: Decimal
    window_start: datetime
    window_end: datetime
    basis: MeterBasis = MeterBasis.CUMULATIVE_OVER_INTERVAL
    labels: Mapping[str, str] = field(default_factory=dict)
    cost_source: CostSource = CostSource.METERED
    resource_id: str | None = None

    def __post_init__(self) -> None:
        if self.window_end < self.window_start:
            raise ValueError(f"Usage record {self.record_id!r} ends before it starts.")
        for moment in (self.window_start, self.window_end):
            if moment.tzinfo is None or moment.utcoffset() is None:
                raise ValueError(f"Usage record {self.record_id!r} has a timezone-naive window.")

    @property
    def dedupe_key(self) -> tuple[str, str]:
        return (self.source, self.record_id)

    @property
    def duration(self) -> timedelta:
        return self.window_end - self.window_start


@dataclass(frozen=True, slots=True)
class CoverageWindow:
    """A collector's claim about what it was watching, and when."""

    source: str
    start: datetime
    end: datetime
    meter: str | None = None
    scope: Mapping[str, str] = field(default_factory=dict)

    def covers(self, moment: datetime, meter: str) -> bool:
        if self.meter is not None and self.meter != meter:
            return False
        return self.start <= moment < self.end


@dataclass(frozen=True, slots=True)
class ConflictingDuplicate:
    """Same key, different quantity -- reported, never silently resolved."""

    source: str
    record_id: str
    quantities: tuple[Decimal, ...]


@dataclass(frozen=True, slots=True)
class DedupeOutcome:
    """What survived deduplication, and what was thrown away."""

    kept: tuple[UsageRecord, ...]
    duplicates_dropped: int
    conflicting: tuple[ConflictingDuplicate, ...]


def dedupe_usage(records: Sequence[UsageRecord]) -> DedupeOutcome:
    """Drop repeats keyed on ``(source, record_id)``.

    Identical repeats are a retried delivery and are safe to drop. Two
    records with the same key and *different* quantities are a data
    problem: picking one silently means the total depends on arrival
    order, so both are reported and the first is kept for determinism.
    """
    kept: dict[tuple[str, str], UsageRecord] = {}
    seen_quantities: dict[tuple[str, str], list[Decimal]] = {}
    dropped = 0

    for record in records:
        key = record.dedupe_key
        seen_quantities.setdefault(key, []).append(record.quantity)
        if key in kept:
            dropped += 1
            continue
        kept[key] = record

    conflicting = tuple(
        ConflictingDuplicate(source=key[0], record_id=key[1], quantities=tuple(quantities))
        for key, quantities in sorted(seen_quantities.items())
        if len(set(quantities)) > 1
    )
    return DedupeOutcome(
        kept=tuple(kept.values()),
        duplicates_dropped=dropped,
        conflicting=conflicting,
    )


@dataclass(frozen=True, slots=True)
class OverlapIssue:
    """Two windows for one resource and meter that claim the same time."""

    resource_id: str
    meter: str
    first: str
    second: str
    overlap_seconds: float


def detect_overlaps(records: Sequence[UsageRecord]) -> tuple[OverlapIssue, ...]:
    """Overlapping windows for the same resource and meter.

    A collector restart re-emitting a window is double cost. It is
    reported rather than summed, because summing it produces a total that
    is plausibly wrong and reconciles against nothing.
    """
    grouped: dict[tuple[str, str], list[UsageRecord]] = {}
    for record in records:
        if record.resource_id is None:
            continue
        grouped.setdefault((record.resource_id, record.meter), []).append(record)

    issues: list[OverlapIssue] = []
    for (resource_id, meter), members in sorted(grouped.items()):
        ordered = sorted(members, key=lambda item: (item.window_start, item.record_id))
        for earlier, later in pairwise(ordered):
            if later.window_start < earlier.window_end:
                overlap = min(earlier.window_end, later.window_end) - later.window_start
                issues.append(
                    OverlapIssue(
                        resource_id=resource_id,
                        meter=meter,
                        first=earlier.record_id,
                        second=later.record_id,
                        overlap_seconds=overlap.total_seconds(),
                    )
                )
    return tuple(issues)


@dataclass(frozen=True, slots=True)
class SplitResult:
    """Sub-records plus the residual the split could not place."""

    parts: tuple[UsageRecord, ...]
    quantity_residual: Decimal
    duration_residual: timedelta


def split_at_boundaries(record: UsageRecord, boundaries: Sequence[datetime]) -> SplitResult:
    """Divide a record where a price changed mid-window.

    **Only cumulative records are divided.** A point event is assigned
    whole to the sub-interval containing its instant: prorating "1
    request" across a price change into 0.4 and 0.6 requests is
    arithmetically tidy and factually false.

    The residuals are returned rather than swallowed, so a caller can see
    that the parts add back up to the original.
    """
    inside = sorted(
        moment for moment in boundaries if record.window_start < moment < record.window_end
    )
    if not inside or record.basis is MeterBasis.POINT_EVENT:
        return SplitResult(
            parts=(record,), quantity_residual=Decimal(0), duration_residual=timedelta(0)
        )

    edges = [record.window_start, *inside, record.window_end]
    total_seconds = Decimal(str(record.duration.total_seconds()))
    parts: list[UsageRecord] = []
    placed = Decimal(0)

    for index, (start, end) in enumerate(pairwise(edges)):
        span = Decimal(str((end - start).total_seconds()))
        share = (
            WORKING_CONTEXT.divide(WORKING_CONTEXT.multiply(record.quantity, span), total_seconds)
            if total_seconds > 0
            else Decimal(0)
        )
        # The last part absorbs the rounding residue so the parts sum
        # exactly to the original quantity.
        if index == len(edges) - 2:
            share = record.quantity - placed
        placed = WORKING_CONTEXT.add(placed, share)
        parts.append(
            UsageRecord(
                record_id=f"{record.record_id}#{index}",
                source=record.source,
                meter=record.meter,
                unit=record.unit,
                quantity=share,
                window_start=start,
                window_end=end,
                basis=record.basis,
                labels=record.labels,
                cost_source=record.cost_source,
                resource_id=record.resource_id,
            )
        )

    covered = sum((part.duration for part in parts), timedelta(0))
    return SplitResult(
        parts=tuple(parts),
        quantity_residual=record.quantity - placed,
        duration_residual=record.duration - covered,
    )


@dataclass(frozen=True, slots=True)
class StorageSample:
    """A reading of stored bytes at an instant."""

    at: datetime
    stored_bytes: Decimal


@dataclass(frozen=True, slots=True)
class UncoveredWindow:
    """A stretch where nothing was measured."""

    start: datetime
    end: datetime
    reason: str


@dataclass(frozen=True, slots=True)
class StorageIntegral:
    """Byte-time, and how much of the period it actually rests on."""

    gib_months: Decimal
    covered_seconds: Decimal
    period_seconds: Decimal
    uncovered: tuple[UncoveredWindow, ...]

    @property
    def covered_fraction(self) -> Decimal:
        if self.period_seconds <= 0:
            return Decimal(0)
        return WORKING_CONTEXT.divide(self.covered_seconds, self.period_seconds)

    @property
    def is_partial(self) -> bool:
        return bool(self.uncovered)


def integrate_storage(
    samples: Sequence[StorageSample],
    *,
    period_start: datetime,
    period_end: datetime,
    sample_interval: timedelta,
    seconds_per_month: Decimal,
) -> StorageIntegral:
    """Integrate stored bytes over time.

    **Zero-order hold, not trapezoid.** A sample measures the state at an
    instant; a trapezoid invents a linear ramp between two measurements
    that nothing observed. The hold is also what makes the result stable
    when a sample repeating the same figure is added.

    **Gaps are not integrated across.** Holding the last sample through a
    three-day collector outage produces a confident number resting on one
    reading. Anything longer than twice the declared sample interval
    becomes an uncovered window instead.
    """
    if period_end <= period_start:
        raise ValueError("The storage period must have positive length.")
    if sample_interval <= timedelta(0):
        raise ValueError("The declared sample interval must be positive.")

    period_seconds = Decimal(str((period_end - period_start).total_seconds()))
    ordered = sorted(
        (sample for sample in samples if period_start <= sample.at < period_end),
        key=lambda sample: sample.at,
    )
    if not ordered:
        return StorageIntegral(
            gib_months=Decimal(0),
            covered_seconds=Decimal(0),
            period_seconds=period_seconds,
            uncovered=(
                UncoveredWindow(
                    start=period_start,
                    end=period_end,
                    reason="No storage samples fall inside the period.",
                ),
            ),
        )

    max_gap = sample_interval * MAX_GAP_MULTIPLIER
    total = Decimal(0)
    covered = Decimal(0)
    uncovered: list[UncoveredWindow] = []

    if ordered[0].at > period_start:
        uncovered.append(
            UncoveredWindow(
                start=period_start,
                end=ordered[0].at,
                reason="The period starts before the first sample.",
            )
        )

    edges = [*ordered, StorageSample(at=period_end, stored_bytes=ordered[-1].stored_bytes)]
    for current, following in pairwise(edges):
        span = following.at - current.at
        if span > max_gap:
            uncovered.append(
                UncoveredWindow(
                    start=current.at,
                    end=following.at,
                    reason=(
                        f"{span} exceeds twice the {sample_interval} sample "
                        "interval; the collector stopped rather than the bytes "
                        "holding steady."
                    ),
                )
            )
            continue
        seconds = Decimal(str(span.total_seconds()))
        covered = WORKING_CONTEXT.add(covered, seconds)
        gib = WORKING_CONTEXT.divide(current.stored_bytes, BYTES_PER_GIB)
        total = WORKING_CONTEXT.add(
            total,
            WORKING_CONTEXT.divide(WORKING_CONTEXT.multiply(gib, seconds), seconds_per_month),
        )

    return StorageIntegral(
        gib_months=total,
        covered_seconds=covered,
        period_seconds=period_seconds,
        uncovered=tuple(uncovered),
    )


def observed_fraction(
    windows: Sequence[CoverageWindow],
    *,
    period_start: datetime,
    period_end: datetime,
    meter: str,
) -> Decimal | None:
    """How much of the period a collector claimed to be watching.

    ``None`` when no coverage was declared at all -- which is the only
    honest answer, and is why the caller cannot then emit a measured
    zero.
    """
    relevant = [
        window
        for window in windows
        if window.meter in (None, meter) and window.end > period_start and window.start < period_end
    ]
    if not relevant:
        return None

    merged: list[tuple[datetime, datetime]] = []
    for window in sorted(relevant, key=lambda item: item.start):
        start = max(window.start, period_start)
        end = min(window.end, period_end)
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    seen = sum((end - start).total_seconds() for start, end in merged)
    total = (period_end - period_start).total_seconds()
    if total <= 0:
        return Decimal(0)
    return WORKING_CONTEXT.divide(Decimal(str(seen)), Decimal(str(total)))


__all__ = [
    "BYTES_PER_GIB",
    "MAX_GAP_MULTIPLIER",
    "ConflictingDuplicate",
    "CoverageWindow",
    "DedupeOutcome",
    "OverlapIssue",
    "SplitResult",
    "StorageIntegral",
    "StorageSample",
    "UncoveredWindow",
    "UsageRecord",
    "dedupe_usage",
    "detect_overlaps",
    "integrate_storage",
    "observed_fraction",
    "split_at_boundaries",
]
