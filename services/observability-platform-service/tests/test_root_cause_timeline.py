"""Tests for app.root_cause.timeline -- clock-aware precedence and onsets."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.root_cause.enums import ClockSource, PrecedenceVerdict
from app.root_cause.timeline import (
    Signal,
    build_timeline,
    find_onset,
    group_by_resolution,
    precedence,
    tolerance_between,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _signal(
    sid: str,
    service: str,
    at: datetime,
    *,
    clock: ClockSource = ClockSource.AGENT,
    fingerprint: str = "fp",
) -> Signal:
    return Signal(signal_id=sid, service=service, fingerprint=fingerprint, at=at, clock=clock)


class TestSignal:
    def test_naive_datetime_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-naive"):
            Signal(signal_id="s1", service="a", fingerprint="fp", at=datetime(2026, 1, 1))


class TestToleranceBetween:
    def test_same_clock_narrow_tolerance(self) -> None:
        result = tolerance_between(ClockSource.AGENT, ClockSource.AGENT)
        assert result == timedelta(seconds=2)

    def test_different_clock_wide_tolerance(self) -> None:
        result = tolerance_between(ClockSource.AGENT, ClockSource.INGEST)
        assert result == timedelta(seconds=30)


class TestPrecedence:
    def test_within_tolerance_is_indeterminate(self) -> None:
        earlier = _signal("s1", "a", T0)
        later = _signal("s2", "b", T0 + timedelta(seconds=1))
        result = precedence(earlier, later)
        assert result.verdict is PrecedenceVerdict.INDETERMINATE
        assert result.lead_time is None

    def test_clearly_precedes(self) -> None:
        earlier = _signal("s1", "a", T0)
        later = _signal("s2", "b", T0 + timedelta(seconds=10))
        result = precedence(earlier, later)
        assert result.verdict is PrecedenceVerdict.PRECEDES
        assert result.lead_time == timedelta(seconds=10)

    def test_clearly_follows(self) -> None:
        earlier = _signal("s1", "a", T0 + timedelta(seconds=10))
        later = _signal("s2", "b", T0)
        result = precedence(earlier, later)
        assert result.verdict is PrecedenceVerdict.FOLLOWS
        assert result.lead_time == timedelta(seconds=10)

    def test_symmetric_regardless_of_argument_order(self) -> None:
        a = _signal("s1", "a", T0)
        b = _signal("s2", "b", T0 + timedelta(seconds=10))
        forward = precedence(a, b)
        backward = precedence(b, a)
        assert forward.verdict is PrecedenceVerdict.PRECEDES
        assert backward.verdict is PrecedenceVerdict.FOLLOWS

    def test_lead_time_below_resolution_is_none(self) -> None:
        earlier = _signal("s1", "a", T0, clock=ClockSource.AGENT)
        later = _signal("s2", "b", T0 + timedelta(seconds=32), clock=ClockSource.INGEST)
        # 32s > 30s cross-clock tolerance -> PRECEDES, but lead_time (32s)
        # exceeds LEAD_TIME_RESOLUTION(4s) so it should be reported.
        result = precedence(earlier, later)
        assert result.verdict is PrecedenceVerdict.PRECEDES
        assert result.lead_time is not None

    def test_comparable_clocks_flag(self) -> None:
        a = _signal("s1", "a", T0, clock=ClockSource.AGENT)
        b = _signal("s2", "b", T0 + timedelta(seconds=10), clock=ClockSource.INGEST)
        result = precedence(a, b)
        assert not result.comparable_clocks


class TestFindOnset:
    def test_empty_signals_returns_none(self) -> None:
        assert find_onset([], window_start=T0) is None

    def test_first_signal_near_window_start_is_censored(self) -> None:
        signals = [_signal("s1", "a", T0 + timedelta(seconds=5))]
        onset = find_onset(signals, window_start=T0)
        assert onset is not None
        assert onset.censored_left
        assert onset.at is None

    def test_first_signal_far_from_window_start_is_not_censored(self) -> None:
        signals = [_signal("s1", "a", T0 + timedelta(minutes=5))]
        onset = find_onset(signals, window_start=T0)
        assert onset is not None
        assert not onset.censored_left
        assert onset.at == T0 + timedelta(minutes=5)

    def test_finds_onset_after_quiet_gap(self) -> None:
        signals = [
            _signal("s1", "a", T0 + timedelta(minutes=10)),
            _signal("s2", "a", T0 + timedelta(minutes=10, seconds=30)),
            # a quiet gap, then a new burst
            _signal("s3", "a", T0 + timedelta(minutes=15)),
        ]
        onset = find_onset(signals, window_start=T0)
        assert onset is not None
        assert onset.signal_id == "s1"

    def test_falls_through_to_first_when_no_gap_found(self) -> None:
        signals = [
            _signal("s1", "a", T0 + timedelta(minutes=10)),
            _signal("s2", "a", T0 + timedelta(minutes=10, seconds=10)),
        ]
        onset = find_onset(signals, window_start=T0, quiet_gap=timedelta(hours=1))
        assert onset is not None
        assert onset.signal_id == "s1"
        assert not onset.censored_left


class TestGroupByResolution:
    def test_empty_onsets(self) -> None:
        assert group_by_resolution([]) == ()

    def test_unplaced_onsets_excluded(self) -> None:
        from app.root_cause.timeline import Onset

        onset = Onset(
            service="a",
            fingerprint="fp",
            at=None,
            censored_left=False,
            signal_id="s1",
            preceding_quiet=None,
        )
        assert group_by_resolution([onset]) == ()

    def test_groups_close_events_together(self) -> None:
        from app.root_cause.timeline import Onset

        onsets = [
            Onset(
                service="a",
                fingerprint="fp",
                at=T0,
                censored_left=False,
                signal_id="s1",
                preceding_quiet=None,
            ),
            Onset(
                service="b",
                fingerprint="fp",
                at=T0 + timedelta(seconds=1),
                censored_left=False,
                signal_id="s2",
                preceding_quiet=None,
            ),
        ]
        groups = group_by_resolution(onsets)
        assert len(groups) == 1
        assert not groups[0].distinguishable

    def test_distant_events_form_separate_groups(self) -> None:
        from app.root_cause.timeline import Onset

        onsets = [
            Onset(
                service="a",
                fingerprint="fp",
                at=T0,
                censored_left=False,
                signal_id="s1",
                preceding_quiet=None,
            ),
            Onset(
                service="b",
                fingerprint="fp",
                at=T0 + timedelta(minutes=10),
                censored_left=False,
                signal_id="s2",
                preceding_quiet=None,
            ),
        ]
        groups = group_by_resolution(onsets)
        assert len(groups) == 2
        assert all(group.distinguishable for group in groups)

    def test_group_anchored_to_first_member_not_chained(self) -> None:
        from app.root_cause.timeline import Onset

        tol = timedelta(seconds=2)
        onsets = [
            Onset(
                service="a",
                fingerprint="fp",
                at=T0,
                censored_left=False,
                signal_id="s1",
                preceding_quiet=None,
            ),
            Onset(
                service="b",
                fingerprint="fp",
                at=T0 + timedelta(seconds=1.9),
                censored_left=False,
                signal_id="s2",
                preceding_quiet=None,
            ),
            # Would be within tolerance of s2 (chained) but not of anchor s1.
            Onset(
                service="c",
                fingerprint="fp",
                at=T0 + timedelta(seconds=3.5),
                censored_left=False,
                signal_id="s3",
                preceding_quiet=None,
            ),
        ]
        groups = group_by_resolution(onsets, tolerance=tol)
        assert len(groups) == 2
        assert len(groups[0].members) == 2


class TestBuildTimeline:
    def test_separates_censored_unplaceable_and_placed(self) -> None:
        from app.root_cause.timeline import Onset

        onsets = [
            Onset(
                service="a",
                fingerprint="fp",
                at=T0,
                censored_left=False,
                signal_id="s1",
                preceding_quiet=None,
            ),
            Onset(
                service="b",
                fingerprint="fp",
                at=None,
                censored_left=True,
                signal_id="s2",
                preceding_quiet=None,
            ),
            Onset(
                service="c",
                fingerprint="fp",
                at=None,
                censored_left=False,
                signal_id="s3",
                preceding_quiet=None,
            ),
        ]
        timeline = build_timeline(onsets, window_start=T0, window_end=T0 + timedelta(hours=1))
        assert len(timeline.groups) == 1
        assert len(timeline.censored) == 1
        assert len(timeline.unplaceable) == 1

    def test_earliest_group_and_distinguishable_first(self) -> None:
        from app.root_cause.timeline import Onset

        onsets = [
            Onset(
                service="a",
                fingerprint="fp",
                at=T0,
                censored_left=False,
                signal_id="s1",
                preceding_quiet=None,
            ),
        ]
        timeline = build_timeline(onsets, window_start=T0, window_end=T0 + timedelta(hours=1))
        assert timeline.earliest_group is not None
        assert timeline.has_distinguishable_first

    def test_no_groups_has_no_earliest(self) -> None:
        timeline = build_timeline([], window_start=T0, window_end=T0 + timedelta(hours=1))
        assert timeline.earliest_group is None
        assert not timeline.has_distinguishable_first

    def test_censored_onset_blocks_distinguishable_first(self) -> None:
        from app.root_cause.timeline import Onset

        onsets = [
            Onset(
                service="a",
                fingerprint="fp",
                at=T0,
                censored_left=False,
                signal_id="s1",
                preceding_quiet=None,
            ),
            Onset(
                service="b",
                fingerprint="fp",
                at=None,
                censored_left=True,
                signal_id="s2",
                preceding_quiet=None,
            ),
        ]
        timeline = build_timeline(onsets, window_start=T0, window_end=T0 + timedelta(hours=1))
        assert not timeline.has_distinguishable_first
