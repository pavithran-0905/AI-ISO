"""Timeline reconstruction and precedence.

Clocks do not agree, so "before" is a three-valued question. The failure
this module exists to prevent is a *sorted* timeline being read as an
*ordered* one: sorting is correct, every test passes, and the rendering
implies a resolution the clocks do not have while the reader takes the
top row as the cause.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.root_cause.enums import ClockSource, PrecedenceVerdict

CLOCK_SKEW_TOLERANCE = timedelta(seconds=2)
"""Four times the realistic 500ms cross-region NTP ceiling. It widens the
*indeterminate* band rather than the "precedes" one -- the conservative
direction, since the cost of a wrong ordering is a wrong root cause."""

CROSS_CLOCK_TOLERANCE = timedelta(seconds=30)
"""Between an agent stamp and an ingest stamp. That gap is queue latency,
not clock error, and it moves by minutes under load."""

LEAD_TIME_RESOLUTION = timedelta(seconds=4)
"""The difference of two quantities each uncertain by the skew tolerance
carries twice that uncertainty. Reporting a lead time finer than this
would be inventing precision."""

QUIET_GAP = timedelta(minutes=2)
"""Silence required before a signal counts as an onset rather than the
continuation of something already running."""

EDGE_MARGIN = timedelta(seconds=30)
"""Proximity to the window start that makes an onset left-censored."""


@dataclass(frozen=True, slots=True)
class Signal:
    """One observation with a time and a clock that produced it."""

    signal_id: str
    service: str
    fingerprint: str
    at: datetime
    clock: ClockSource = ClockSource.AGENT

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.utcoffset() is None:
            raise ValueError(
                f"Signal {self.signal_id!r} is timezone-naive; a naive comparison "
                "across a DST boundary shifts by an hour without warning, and "
                "every test written in UTC passes anyway."
            )


def tolerance_between(left: ClockSource, right: ClockSource) -> timedelta:
    """How far apart two stamps can be before order means anything."""
    if left is right:
        return CLOCK_SKEW_TOLERANCE
    return CROSS_CLOCK_TOLERANCE


@dataclass(frozen=True, slots=True)
class Precedence:
    """Whether one signal preceded another, and by how much.

    ``lead_time`` is ``None`` for an indeterminate verdict rather than
    zero: no interval was established, and a zero would be summed and
    averaged downstream as though it had been.
    """

    verdict: PrecedenceVerdict
    lead_time: timedelta | None
    tolerance: timedelta
    comparable_clocks: bool


def precedence(earlier: Signal, later: Signal) -> Precedence:
    """Compare two signals symmetrically.

    A one-sided ``cause.at <= effect.at + tolerance`` reports an event
    1.9 seconds *after* its effect as preceding it. The band here is
    symmetric, so anything inside it is indeterminate in both directions.
    """
    tolerance = tolerance_between(earlier.clock, later.clock)
    delta = later.at - earlier.at
    comparable = earlier.clock is later.clock

    if abs(delta) <= tolerance:
        return Precedence(
            verdict=PrecedenceVerdict.INDETERMINATE,
            lead_time=None,
            tolerance=tolerance,
            comparable_clocks=comparable,
        )
    if delta > timedelta(0):
        return Precedence(
            verdict=PrecedenceVerdict.PRECEDES,
            lead_time=delta if delta >= LEAD_TIME_RESOLUTION else None,
            tolerance=tolerance,
            comparable_clocks=comparable,
        )
    return Precedence(
        verdict=PrecedenceVerdict.FOLLOWS,
        lead_time=-delta if -delta >= LEAD_TIME_RESOLUTION else None,
        tolerance=tolerance,
        comparable_clocks=comparable,
    )


@dataclass(frozen=True, slots=True)
class Onset:
    """When a service's trouble started, and whether that is knowable.

    ``censored_left`` is the field that stops the analysis from
    reliably naming whichever service the query happened to start from:
    a problem that began before the window would otherwise be stamped at
    the window edge and become the earliest thing on the timeline.
    """

    service: str
    fingerprint: str
    at: datetime | None
    censored_left: bool
    signal_id: str | None
    preceding_quiet: timedelta | None


def find_onset(
    signals: Sequence[Signal],
    *,
    window_start: datetime,
    quiet_gap: timedelta = QUIET_GAP,
    edge_margin: timedelta = EDGE_MARGIN,
) -> Onset | None:
    """The first signal that follows enough silence to be a beginning.

    A signal arriving hard against the window start is marked censored
    rather than being treated as the onset, because the true onset may
    lie outside the data entirely.
    """
    if not signals:
        return None
    ordered = sorted(signals, key=lambda item: (item.at, item.signal_id))
    first = ordered[0]

    previous: datetime | None = None
    for signal in ordered:
        quiet = None if previous is None else signal.at - previous
        if previous is None or (quiet is not None and quiet >= quiet_gap):
            censored = signal.at - window_start <= edge_margin and previous is None
            return Onset(
                service=signal.service,
                fingerprint=signal.fingerprint,
                at=None if censored else signal.at,
                censored_left=censored,
                signal_id=signal.signal_id,
                preceding_quiet=quiet,
            )
        previous = signal.at

    return Onset(
        service=first.service,
        fingerprint=first.fingerprint,
        at=first.at,
        censored_left=False,
        signal_id=first.signal_id,
        preceding_quiet=None,
    )


@dataclass(frozen=True, slots=True)
class OrderingGroup:
    """Events the clocks cannot separate, presented as one rank.

    Anchored to the group's *first* member. Banding by comparing each
    event to the previous one is the obvious fix and it chains
    transitively, merging a ten-minute cascade into a single
    "simultaneous" group -- while three-event tests pass.
    """

    index: int
    members: tuple[Onset, ...]
    span: timedelta
    distinguishable: bool


def group_by_resolution(
    onsets: Sequence[Onset], *, tolerance: timedelta = CLOCK_SKEW_TOLERANCE
) -> tuple[OrderingGroup, ...]:
    """Band a timeline into groups no finer than the clock allows."""
    placed = [onset for onset in onsets if onset.at is not None]
    ordered = sorted(placed, key=lambda item: (item.at, item.service))

    groups: list[list[Onset]] = []
    for onset in ordered:
        if groups and onset.at is not None:
            anchor = groups[-1][0].at
            if anchor is not None and onset.at - anchor <= tolerance:
                groups[-1].append(onset)
                continue
        groups.append([onset])

    result: list[OrderingGroup] = []
    for index, members in enumerate(groups):
        first, last = members[0].at, members[-1].at
        span = (last - first) if first and last else timedelta(0)
        result.append(
            OrderingGroup(
                index=index,
                members=tuple(members),
                span=span,
                distinguishable=len(members) == 1,
            )
        )
    return tuple(result)


@dataclass(frozen=True, slots=True)
class Timeline:
    """An ordered account of an incident, with its unknowns named."""

    groups: tuple[OrderingGroup, ...]
    unplaceable: tuple[Onset, ...]
    censored: tuple[Onset, ...]
    window_start: datetime
    window_end: datetime

    @property
    def earliest_group(self) -> OrderingGroup | None:
        return self.groups[0] if self.groups else None

    @property
    def has_distinguishable_first(self) -> bool:
        """Whether anything can be said to have come first at all."""
        first = self.earliest_group
        return first is not None and first.distinguishable and not self.censored


def build_timeline(
    onsets: Sequence[Onset],
    *,
    window_start: datetime,
    window_end: datetime,
    tolerance: timedelta = CLOCK_SKEW_TOLERANCE,
) -> Timeline:
    """Assemble onsets into ordered groups, keeping the unknowns visible."""
    censored = tuple(onset for onset in onsets if onset.censored_left)
    unplaceable = tuple(onset for onset in onsets if onset.at is None and not onset.censored_left)
    placeable = [onset for onset in onsets if onset.at is not None]
    return Timeline(
        groups=group_by_resolution(placeable, tolerance=tolerance),
        unplaceable=unplaceable,
        censored=censored,
        window_start=window_start,
        window_end=window_end,
    )


__all__ = [
    "CLOCK_SKEW_TOLERANCE",
    "CROSS_CLOCK_TOLERANCE",
    "EDGE_MARGIN",
    "LEAD_TIME_RESOLUTION",
    "QUIET_GAP",
    "Onset",
    "OrderingGroup",
    "Precedence",
    "Signal",
    "Timeline",
    "build_timeline",
    "find_onset",
    "group_by_resolution",
    "precedence",
    "tolerance_between",
]
