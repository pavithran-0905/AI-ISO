"""Tests for app.topology.edges -- edge inference, confidence, volume, rhythm."""

from __future__ import annotations

import pytest

from app.topology.edges import (
    MAX_INDEPENDENT_PER_HOUR,
    SpanRecord,
    aggregate_edges,
    confidence_for_counts,
    existence_confidence,
    infer_edges,
    measure_rhythm,
    measure_volume,
)
from app.topology.enums import ConfidenceBand, EdgeEvidenceKind, SpanKindLabel, TopologyEdgeKind

HOUR_NS = 3_600_000_000_000


def _span(
    span_id: str,
    service: str,
    kind: SpanKindLabel,
    *,
    parent: str | None = None,
    start: int = 0,
    **overrides: object,
) -> SpanRecord:
    defaults: dict[str, object] = {
        "span_id": span_id,
        "trace_id": "t1",
        "parent_span_id": parent,
        "service": service,
        "kind": kind,
        "operation": "op",
        "start_ns": start,
        "duration_ns": 100,
    }
    defaults.update(overrides)
    return SpanRecord(**defaults)  # type: ignore[arg-type]


class TestInferEdges:
    def test_server_child_of_client_produces_edge(self) -> None:
        spans = [
            _span("c1", "gateway", SpanKindLabel.CLIENT, start=0),
            _span("s1", "backend", SpanKindLabel.SERVER, parent="c1", start=1),
        ]
        result = infer_edges(spans)
        assert len(result.observations) == 1
        assert result.observations[0].caller_service == "gateway"
        assert result.observations[0].callee_service == "backend"
        assert result.observations[0].evidence is EdgeEvidenceKind.SERVER_CHILD_OF_CLIENT

    def test_same_service_pair_skipped(self) -> None:
        spans = [
            _span("c1", "svc", SpanKindLabel.CLIENT, start=0),
            _span("s1", "svc", SpanKindLabel.SERVER, parent="c1", start=1),
        ]
        result = infer_edges(spans)
        assert result.observations == ()
        assert result.same_service_pairs_skipped == 1

    def test_orphan_span_counted(self) -> None:
        spans = [_span("s1", "svc", SpanKindLabel.SERVER, parent=None)]
        result = infer_edges(spans)
        assert result.orphan_spans == 1

    def test_missing_parent_produces_missing_link_not_synthesized_edge(self) -> None:
        spans = [_span("s1", "svc", SpanKindLabel.SERVER, parent="ghost")]
        result = infer_edges(spans)
        assert result.observations == ()
        assert len(result.missing_links) == 1
        assert result.missing_links[0].missing_parent_span_id == "ghost"

    def test_producer_consumer_link(self) -> None:
        spans = [
            _span("p1", "producer-svc", SpanKindLabel.PRODUCER, start=0),
            _span("c1", "consumer-svc", SpanKindLabel.CONSUMER, parent="p1", start=1),
        ]
        result = infer_edges(spans)
        assert len(result.observations) == 1
        assert result.observations[0].kind is TopologyEdgeKind.ASYNC_MESSAGE
        assert result.observations[0].duration_ns is None

    def test_client_peer_attribute_without_server_child(self) -> None:
        spans = [_span("c1", "gateway", SpanKindLabel.CLIENT, peer_service="external-api")]
        result = infer_edges(spans)
        assert len(result.observations) == 1
        assert result.observations[0].evidence is EdgeEvidenceKind.CLIENT_PEER_ATTRIBUTE

    def test_client_peer_attribute_suppressed_when_server_child_exists(self) -> None:
        spans = [
            _span("c1", "gateway", SpanKindLabel.CLIENT, start=0, peer_service="backend"),
            _span("s1", "backend", SpanKindLabel.SERVER, parent="c1", start=1),
        ]
        result = infer_edges(spans)
        assert len(result.observations) == 1
        assert result.observations[0].evidence is EdgeEvidenceKind.SERVER_CHILD_OF_CLIENT

    def test_client_peer_same_as_own_service_skipped(self) -> None:
        spans = [_span("c1", "svc", SpanKindLabel.CLIENT, peer_service="svc")]
        result = infer_edges(spans)
        assert result.observations == ()
        assert result.same_service_pairs_skipped == 1

    def test_links_to_used_when_no_parent(self) -> None:
        spans = [
            _span("l1", "producer-svc", SpanKindLabel.PRODUCER, start=0),
            _span(
                "c1", "consumer-svc", SpanKindLabel.CONSUMER, parent=None, start=1, links_to=("l1",)
            ),
        ]
        result = infer_edges(spans)
        assert len(result.observations) == 1

    def test_remote_parent_kind_uses_server_child_of_remote(self) -> None:
        spans = [
            _span("i1", "gateway", SpanKindLabel.INTERNAL, start=0),
            _span("s1", "backend", SpanKindLabel.SERVER, parent="i1", start=1),
        ]
        result = infer_edges(spans)
        assert result.observations[0].evidence is EdgeEvidenceKind.SERVER_CHILD_OF_REMOTE


class TestExistenceConfidence:
    def test_none_when_no_observations(self) -> None:
        assert existence_confidence([]) is None

    def test_confidence_bands(self) -> None:
        from app.topology.edges import EdgeObservation

        obs = [
            EdgeObservation(
                caller_service="a",
                callee_service="b",
                kind=TopologyEdgeKind.SYNC_CALL,
                evidence=EdgeEvidenceKind.SERVER_CHILD_OF_CLIENT,
                operation="op",
                trace_id=f"t{i}",
                caller_instance_id="i1",
                observed_at_ns=i * HOUR_NS,
                duration_ns=10,
                errored=False,
            )
            for i in range(5)
        ]
        result = existence_confidence(obs)
        assert result is not None
        assert result.band in (ConfidenceBand.PROVEN, ConfidenceBand.LIKELY, ConfidenceBand.WEAK)

    def test_saturates_per_hour(self) -> None:
        from app.topology.edges import EdgeObservation

        # 100 observations all within the same hour still cap at
        # MAX_INDEPENDENT_PER_HOUR effective observations.
        obs = [
            EdgeObservation(
                caller_service="a",
                callee_service="b",
                kind=TopologyEdgeKind.SYNC_CALL,
                evidence=EdgeEvidenceKind.CLIENT_PEER_ATTRIBUTE,
                operation="op",
                trace_id=f"t{i}",
                caller_instance_id=None,
                observed_at_ns=i,
                duration_ns=10,
                errored=False,
            )
            for i in range(100)
        ]
        result = existence_confidence(obs)
        assert result is not None
        assert result.effective_observations == MAX_INDEPENDENT_PER_HOUR


class TestMeasureVolume:
    def test_none_sampling_ratio_yields_unknown_counts(self) -> None:
        volume = measure_volume([], window_seconds=60.0, sampling_ratio=None)
        assert volume.call_count is None
        assert volume.calls_per_second is None
        assert volume.error_ratio is None

    def test_invalid_sampling_ratio_raises(self) -> None:
        with pytest.raises(ValueError, match="sampling ratio"):
            measure_volume([], window_seconds=60.0, sampling_ratio=1.5)

    def test_extrapolates_call_count(self) -> None:
        from app.topology.edges import EdgeObservation

        obs = [
            EdgeObservation(
                caller_service="a",
                callee_service="b",
                kind=TopologyEdgeKind.SYNC_CALL,
                evidence=EdgeEvidenceKind.SERVER_CHILD_OF_CLIENT,
                operation="op",
                trace_id="t1",
                caller_instance_id=None,
                observed_at_ns=0,
                duration_ns=10,
                errored=True,
            )
        ]
        volume = measure_volume(obs, window_seconds=60.0, sampling_ratio=0.5)
        assert volume.call_count == 2
        assert volume.error_count == 2
        assert volume.calls_per_second == pytest.approx(2 / 60)
        assert volume.error_ratio == pytest.approx(1.0)


class TestMeasureRhythm:
    def test_below_min_observations(self) -> None:
        rhythm = measure_rhythm([])
        assert rhythm.median_gap_ns is None
        assert rhythm.is_stale(0) is None

    def test_computes_median_gap(self) -> None:
        from app.topology.edges import EdgeObservation

        obs = [
            EdgeObservation(
                caller_service="a",
                callee_service="b",
                kind=TopologyEdgeKind.SYNC_CALL,
                evidence=EdgeEvidenceKind.SERVER_CHILD_OF_CLIENT,
                operation="op",
                trace_id="t1",
                caller_instance_id=None,
                observed_at_ns=n,
                duration_ns=10,
                errored=False,
            )
            for n in [0, 100, 200]
        ]
        rhythm = measure_rhythm(obs)
        assert rhythm.median_gap_ns == 100.0
        assert not rhythm.is_stale(250, tolerance=3.0)
        assert rhythm.is_stale(1_000_000, tolerance=3.0)


class TestAggregateEdges:
    def test_groups_by_caller_callee_kind(self) -> None:
        spans = [
            _span("c1", "gateway", SpanKindLabel.CLIENT, start=0),
            _span("s1", "backend", SpanKindLabel.SERVER, parent="c1", start=1),
            _span("c2", "gateway", SpanKindLabel.CLIENT, start=10),
            _span("s2", "backend", SpanKindLabel.SERVER, parent="c2", start=11),
        ]
        observations = infer_edges(spans).observations
        edges = aggregate_edges(observations, window_seconds=60.0)
        assert len(edges) == 1
        assert edges[0].caller_service == "gateway"
        assert edges[0].callee_service == "backend"

    def test_empty_observations(self) -> None:
        assert aggregate_edges([], window_seconds=60.0) == ()

    def test_operations_capped(self) -> None:
        from app.topology.edges import EdgeObservation

        obs = [
            EdgeObservation(
                caller_service="a",
                callee_service="b",
                kind=TopologyEdgeKind.SYNC_CALL,
                evidence=EdgeEvidenceKind.SERVER_CHILD_OF_CLIENT,
                operation=f"op{i}",
                trace_id=f"t{i}",
                caller_instance_id=None,
                observed_at_ns=i,
                duration_ns=10,
                errored=False,
            )
            for i in range(5)
        ]
        edges = aggregate_edges(obs, window_seconds=60.0, max_operations=2)
        assert len(edges[0].operations) == 2


class TestConfidenceForCounts:
    def test_single_kind(self) -> None:
        result = confidence_for_counts({EdgeEvidenceKind.SERVER_CHILD_OF_CLIENT: 1})
        assert result == pytest.approx(0.999)

    def test_empty_counts(self) -> None:
        assert confidence_for_counts({}) == 0.0
