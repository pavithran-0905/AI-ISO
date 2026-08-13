"""Tests for app.topology.graph -- cycles, dominators, critical path."""

from __future__ import annotations

import pytest

from app.topology.edges import (
    EdgeRhythm,
    EdgeVolume,
    ExistenceConfidence,
    InferredEdge,
    MissingLinkObservation,
    SpanRecord,
)
from app.topology.enums import ConfidenceBand, CriticalityInput, SpanKindLabel, TopologyEdgeKind
from app.topology.graph import build_topology, critical_path, dominators, find_cycles, self_times


def _confidence(band: ConfidenceBand = ConfidenceBand.PROVEN) -> ExistenceConfidence:
    value = {ConfidenceBand.PROVEN: 0.9999, ConfidenceBand.LIKELY: 0.97, ConfidenceBand.WEAK: 0.5}[
        band
    ]
    return ExistenceConfidence(
        value=value,
        effective_observations=3,
        raw_observations=3,
        distinct_traces=3,
        distinct_caller_instances=None,
        distinct_observation_hours=1,
        evidence_counts={},
    )


def _edge(
    caller: str,
    callee: str,
    *,
    kind: TopologyEdgeKind = TopologyEdgeKind.SYNC_CALL,
    band: ConfidenceBand = ConfidenceBand.PROVEN,
) -> InferredEdge:
    return InferredEdge(
        caller_service=caller,
        callee_service=callee,
        kind=kind,
        confidence=_confidence(band),
        volume=EdgeVolume(call_count=10, error_count=0, sampling_ratio=1.0, window_seconds=60.0),
        rhythm=EdgeRhythm(median_gap_ns=1000, observation_count=3, last_observed_ns=1000),
    )


def _span(
    span_id: str,
    service: str,
    kind: SpanKindLabel,
    *,
    parent: str | None = None,
    start: int = 0,
    duration: int = 100,
) -> SpanRecord:
    return SpanRecord(
        span_id=span_id,
        trace_id="t1",
        parent_span_id=parent,
        service=service,
        kind=kind,
        operation="op",
        start_ns=start,
        duration_ns=duration,
    )


class TestFindCycles:
    def test_no_cycle(self) -> None:
        edges = (_edge("a", "b"), _edge("b", "c"))
        assert find_cycles(edges) == ()

    def test_two_node_cycle(self) -> None:
        edges = (_edge("a", "b"), _edge("b", "a"))
        cycles = find_cycles(edges)
        assert ("a", "b") in cycles

    def test_async_included_by_default(self) -> None:
        edges = (_edge("a", "b", kind=TopologyEdgeKind.ASYNC_MESSAGE), _edge("b", "a"))
        cycles = find_cycles(edges)
        assert ("a", "b") in cycles


class TestDominators:
    def test_entry_not_in_graph_returns_empty(self) -> None:
        edges = (_edge("a", "b"),)
        assert dominators(edges, "missing") == {}

    def test_linear_chain_dominators(self) -> None:
        edges = (_edge("a", "b"), _edge("b", "c"))
        result = dominators(edges, "a")
        assert result["c"] == frozenset({"a", "b", "c"})

    def test_diamond_shape_only_shared_ancestor_dominates(self) -> None:
        edges = (_edge("a", "b"), _edge("a", "c"), _edge("b", "d"), _edge("c", "d"))
        result = dominators(edges, "a")
        assert result["d"] == frozenset({"a", "d"})

    def test_hard_only_excludes_async_edges(self) -> None:
        edges = (_edge("a", "b", kind=TopologyEdgeKind.ASYNC_MESSAGE),)
        result = dominators(edges, "a", hard_only=True)
        # Async edge excluded entirely from the successor graph.
        assert "b" not in result or result == {}


class TestBuildTopology:
    def test_basic_topology(self) -> None:
        edges = (_edge("gateway", "backend"), _edge("backend", "db"))
        topology = build_topology(edges)
        assert topology.node("gateway") is not None
        assert topology.node("backend").fan_in == 1  # type: ignore[union-attr]
        assert topology.node("backend").fan_out == 1  # type: ignore[union-attr]

    def test_filters_by_min_confidence(self) -> None:
        edges = (_edge("a", "b", band=ConfidenceBand.WEAK),)
        topology = build_topology(edges, min_confidence=ConfidenceBand.PROVEN)
        assert topology.edges == ()

    def test_missing_links_produce_unnamed_callers(self) -> None:
        edges = (_edge("a", "b"),)
        links = (
            MissingLinkObservation(
                callee_service="b", missing_parent_span_id="x", trace_id="t1", observed_at_ns=0
            ),
        )
        topology = build_topology(edges, missing_links=links)
        node = topology.node("b")
        assert node is not None
        assert node.unnamed_callers == 1
        assert CriticalityInput.UNOBSERVED_DEPENDENTS in node.criticality_inputs

    def test_cycle_flagged(self) -> None:
        edges = (_edge("a", "b"), _edge("b", "a"))
        topology = build_topology(edges)
        assert topology.node("a").in_cycle  # type: ignore[union-attr]
        assert len(topology.cycles) == 1

    def test_single_point_of_failure_detected(self) -> None:
        edges = (
            _edge("gateway", "hub"),
            _edge("hub", "svc1"),
            _edge("hub", "svc2"),
            _edge("hub", "svc3"),
        )
        topology = build_topology(edges, dominates_many_at=3)
        hub = topology.node("hub")
        assert hub is not None
        assert hub.is_single_point_of_failure
        assert hub in topology.single_points_of_failure

    def test_high_fan_in_flagged(self) -> None:
        edges = (_edge("a", "shared"), _edge("b", "shared"), _edge("c", "shared"))
        topology = build_topology(edges, dominates_many_at=3)
        node = topology.node("shared")
        assert node is not None
        assert CriticalityInput.HIGH_FAN_IN in node.criticality_inputs

    def test_explicit_entry_points_override_root_inference(self) -> None:
        edges = (_edge("a", "b"),)
        topology = build_topology(edges, entry_points=["a"])
        assert topology.entry_points == ("a",)

    def test_node_for_unknown_service_is_none(self) -> None:
        edges = (_edge("a", "b"),)
        topology = build_topology(edges)
        assert topology.node("nonexistent") is None


class TestSelfTimes:
    def test_leaf_span_self_time_equals_duration(self) -> None:
        spans = [_span("s1", "svc", SpanKindLabel.SERVER, duration=100)]
        timings = self_times(spans)
        assert timings[0].self_time_ns == 100
        assert timings[0].child_blocking_ns == 0

    def test_parent_self_time_excludes_child_blocking(self) -> None:
        spans = [
            _span("p1", "svc", SpanKindLabel.SERVER, start=0, duration=100),
            _span("c1", "svc", SpanKindLabel.INTERNAL, parent="p1", start=10, duration=50),
        ]
        timings = {t.span_id: t for t in self_times(spans)}
        assert timings["p1"].child_blocking_ns == 50
        assert timings["p1"].self_time_ns == 50

    def test_overlapping_children_merged_not_summed(self) -> None:
        spans = [
            _span("p1", "svc", SpanKindLabel.SERVER, start=0, duration=100),
            _span("c1", "svc", SpanKindLabel.INTERNAL, parent="p1", start=0, duration=60),
            _span("c2", "svc", SpanKindLabel.INTERNAL, parent="p1", start=10, duration=60),
        ]
        timings = {t.span_id: t for t in self_times(spans)}
        # Merged interval [0,70), not summed 60+60=120.
        assert timings["p1"].child_blocking_ns == 70
        assert timings["p1"].self_time_ns == 30

    def test_async_child_does_not_block_parent(self) -> None:
        spans = [
            _span("p1", "svc", SpanKindLabel.PRODUCER, start=0, duration=100),
            _span("c1", "other", SpanKindLabel.CONSUMER, parent="p1", start=10, duration=50),
        ]
        timings = {t.span_id: t for t in self_times(spans)}
        assert timings["p1"].child_blocking_ns == 0
        assert timings["p1"].self_time_ns == 100


class TestCriticalPath:
    def test_empty_spans_returns_none(self) -> None:
        assert critical_path([]) is None

    def test_single_span(self) -> None:
        spans = [_span("s1", "svc", SpanKindLabel.SERVER, duration=100)]
        result = critical_path(spans)
        assert result is not None
        assert result.total_ns == 100
        assert result.dominant is not None
        assert result.dominant_share == pytest.approx(1.0)

    def test_follows_blocking_chain_not_longest_child(self) -> None:
        # Parent has two children: one long but early (parallel, not
        # blocking), one short but the last to finish (on the critical path).
        spans = [
            _span("root", "svc", SpanKindLabel.SERVER, start=0, duration=100),
            _span("long-early", "svc", SpanKindLabel.INTERNAL, parent="root", start=0, duration=40),
            _span(
                "late-blocker", "svc", SpanKindLabel.INTERNAL, parent="root", start=50, duration=50
            ),
        ]
        result = critical_path(spans)
        assert result is not None
        chain_ids = [t.span_id for t in result.chain]
        assert "late-blocker" in chain_ids
        assert chain_ids[0] == "root"

    def test_async_children_excluded_from_chain(self) -> None:
        spans = [
            _span("root", "svc", SpanKindLabel.PRODUCER, start=0, duration=100),
            _span(
                "consumer", "other", SpanKindLabel.CONSUMER, parent="root", start=10, duration=200
            ),
        ]
        result = critical_path(spans)
        assert result is not None
        assert len(result.chain) == 1

    def test_zero_duration_root_has_no_dominant_share(self) -> None:
        spans = [_span("s1", "svc", SpanKindLabel.SERVER, duration=0)]
        result = critical_path(spans)
        assert result is not None
        assert result.dominant_share is None
