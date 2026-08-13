"""Tests for app.root_cause.engine -- graph traversal, ranking, refusal."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.root_cause.correlation import CorrelationResult
from app.root_cause.engine import (
    Candidate,
    Edge,
    Graph,
    analyse,
    assert_dual,
    blast_radius,
    budget_for,
    classify_tier,
    find_common_antecedents,
    rank_candidates,
    share_component,
    strongly_connected_components,
    walk,
)
from app.root_cause.enums import (
    AnalysisRefusal,
    Direction,
    EdgeKind,
    EvidenceTier,
    PathQuality,
    WindowProvenance,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _edge(
    caller: str, callee: str, *, kind: EdgeKind = EdgeKind.SYNCHRONOUS, observed: bool = True
) -> Edge:
    return Edge(caller=caller, callee=callee, kind=kind, is_observed=observed)


def _candidate(service: str, **overrides: object) -> Candidate:
    defaults: dict[str, object] = {
        "service": service,
        "tier": EvidenceTier.INSUFFICIENT_EVIDENCE,
        "correlation": None,
        "activity_jaccard": None,
        "specificity": None,
        "precedes_symptom": False,
        "graph_path": None,
        "graph_depth": None,
        "in_cycle_with_symptom": False,
        "lag_within_budget": None,
        "change_nearby": False,
    }
    defaults.update(overrides)
    return Candidate(**defaults)  # type: ignore[arg-type]


def _correlation(
    coefficient: float | None, *, significant: bool = True, paired: int = 20
) -> CorrelationResult:
    return CorrelationResult(
        service="x",
        coefficient=coefficient,
        paired_buckets=paired,
        excluded_buckets=0,
        bucket_seconds=60.0,
        lag_buckets=0,
        lag_ambiguous=False,
        differenced=False,
        unmeasurable=None,
        p_value=0.01,
        adjusted_p_value=0.01,
        significant=significant,
    )


class TestLagBudget:
    def test_admits_within_bounds(self) -> None:
        budget = budget_for(EdgeKind.SYNCHRONOUS)
        assert budget.admits(timedelta(seconds=5))
        assert not budget.admits(timedelta(seconds=60))

    def test_asynchronous_has_no_maximum(self) -> None:
        budget = budget_for(EdgeKind.ASYNCHRONOUS)
        assert budget.admits(timedelta(hours=1))
        assert budget.unbounded_reason is not None

    def test_cache_has_minimum(self) -> None:
        budget = budget_for(EdgeKind.CACHE, cache_ttl=timedelta(seconds=60))
        assert not budget.admits(timedelta(seconds=10))
        assert budget.admits(timedelta(seconds=61))

    def test_cache_default_ttl(self) -> None:
        budget = budget_for(EdgeKind.CACHE)
        assert budget.minimum == timedelta(seconds=120)


class TestGraph:
    def test_nodes(self) -> None:
        graph = Graph(edges=(_edge("a", "b"), _edge("b", "c")))
        assert graph.nodes == ("a", "b", "c")

    def test_dependencies_and_dependents(self) -> None:
        graph = Graph(edges=(_edge("a", "b"),))
        assert len(graph.dependencies_of("a")) == 1
        assert len(graph.dependents_of("b")) == 1
        assert graph.dependencies_of("b") == ()


class TestWalk:
    def test_upstream_walk_finds_dependencies(self) -> None:
        graph = Graph(edges=(_edge("a", "b"), _edge("b", "c")))
        result = walk(graph, "a", Direction.UPSTREAM)
        assert "c" in result.reached
        assert result.complete

    def test_downstream_walk_finds_dependents(self) -> None:
        graph = Graph(edges=(_edge("a", "b"), _edge("b", "c")))
        result = walk(graph, "c", Direction.DOWNSTREAM)
        assert "a" in result.reached
        assert result.complete

    def test_depth_truncation(self) -> None:
        graph = Graph(edges=tuple(_edge(f"n{i}", f"n{i+1}") for i in range(10)))
        result = walk(graph, "n0", Direction.UPSTREAM, max_depth=2)
        assert result.truncated_at_depth
        assert not result.complete

    def test_node_cap_truncation(self) -> None:
        graph = Graph(edges=tuple(_edge("origin", f"n{i}") for i in range(10)))
        result = walk(graph, "origin", Direction.UPSTREAM, max_nodes=3)
        assert result.truncated_at_node_cap
        assert not result.complete

    def test_declared_only_edge_taints_path(self) -> None:
        graph = Graph(edges=(_edge("a", "b", observed=False), _edge("b", "c", observed=True)))
        result = walk(graph, "a", Direction.UPSTREAM)
        assert result.quality_by_service["c"] is PathQuality.DECLARED_ONLY

    def test_cycle_does_not_infinite_loop(self) -> None:
        graph = Graph(edges=(_edge("a", "b"), _edge("b", "a")))
        result = walk(graph, "a", Direction.UPSTREAM)
        assert set(result.reached) == {"a", "b"}


class TestStronglyConnectedComponents:
    def test_no_cycle_singleton_components(self) -> None:
        graph = Graph(edges=(_edge("a", "b"),))
        components = strongly_connected_components(graph)
        assert ("a",) in components
        assert ("b",) in components

    def test_cycle_grouped_together(self) -> None:
        graph = Graph(edges=(_edge("a", "b"), _edge("b", "a")))
        components = strongly_connected_components(graph)
        assert ("a", "b") in components


class TestShareComponent:
    def test_true_when_in_same_component(self) -> None:
        assert share_component([("a", "b"), ("c",)], "a", "b")

    def test_false_when_in_different_components(self) -> None:
        assert not share_component([("a",), ("b",)], "a", "b")


class TestAssertDual:
    def test_consistent_directions(self) -> None:
        graph = Graph(edges=(_edge("a", "b"),))
        assert assert_dual(graph, "a", "b")


class TestBlastRadius:
    def test_categorises_dependents(self) -> None:
        graph = Graph(edges=(_edge("gateway", "origin"), _edge("worker", "origin")))
        result = blast_radius(
            graph, "origin", symptomatic=["gateway"], instrumented=["gateway", "worker"]
        )
        assert "gateway" in result.observed_affected
        assert "worker" in result.observed_healthy
        assert result.bucket_of("gateway") is not None

    def test_unobservable_service(self) -> None:
        graph = Graph(edges=(_edge("caller", "origin"),))
        result = blast_radius(graph, "origin", symptomatic=[], instrumented=[])
        assert "caller" in result.unobservable
        assert result.bucket_of("unknown") is None


class TestClassifyTier:
    def test_unmeasurable_correlation_is_insufficient(self) -> None:
        from app.root_cause.correlation import Unmeasurable

        corr = CorrelationResult(
            service="x",
            coefficient=None,
            paired_buckets=1,
            excluded_buckets=0,
            bucket_seconds=60.0,
            lag_buckets=0,
            lag_ambiguous=False,
            differenced=False,
            unmeasurable=Unmeasurable.TOO_FEW_PAIRED_BUCKETS,
        )
        candidate = _candidate("svc", correlation=corr)
        assert classify_tier(candidate) is EvidenceTier.INSUFFICIENT_EVIDENCE

    def test_low_specificity_is_coincident(self) -> None:
        candidate = _candidate("svc", specificity=0.1)
        assert classify_tier(candidate) is EvidenceTier.COINCIDENT

    def test_mechanism_and_timing(self) -> None:
        corr = _correlation(0.9)
        candidate = _candidate(
            "svc",
            correlation=corr,
            specificity=0.9,
            precedes_symptom=True,
            graph_path=PathQuality.OBSERVED_ONLY,
        )
        assert classify_tier(candidate) is EvidenceTier.MECHANISM_AND_TIMING

    def test_timing_only(self) -> None:
        corr = _correlation(0.9)
        candidate = _candidate(
            "svc", correlation=corr, specificity=0.9, precedes_symptom=True, graph_path=None
        )
        assert classify_tier(candidate) is EvidenceTier.TIMING_ONLY

    def test_mechanism_only(self) -> None:
        candidate = _candidate(
            "svc", specificity=0.9, precedes_symptom=False, graph_path=PathQuality.OBSERVED_ONLY
        )
        assert classify_tier(candidate) is EvidenceTier.MECHANISM_ONLY

    def test_coincident_from_measured_correlation_without_timing(self) -> None:
        corr = _correlation(0.9)
        candidate = _candidate(
            "svc", correlation=corr, specificity=0.9, precedes_symptom=False, graph_path=None
        )
        assert classify_tier(candidate) is EvidenceTier.COINCIDENT

    def test_insufficient_evidence_default(self) -> None:
        candidate = _candidate("svc", specificity=0.9)
        assert classify_tier(candidate) is EvidenceTier.INSUFFICIENT_EVIDENCE

    def test_mechanism_voided_by_cycle(self) -> None:
        candidate = _candidate(
            "svc", specificity=0.9, graph_path=PathQuality.OBSERVED_ONLY, in_cycle_with_symptom=True
        )
        assert not candidate.has_mechanism


class TestRankCandidates:
    def test_orders_by_tier(self) -> None:
        strong = _candidate(
            "strong",
            correlation=_correlation(0.9),
            specificity=0.9,
            precedes_symptom=True,
            graph_path=PathQuality.OBSERVED_ONLY,
        )
        weak = _candidate("weak", specificity=0.9)
        ranked = rank_candidates([weak, strong])
        assert ranked[0].candidate.service == "strong"
        assert ranked[0].rank == 1

    def test_ties_share_rank(self) -> None:
        a = _candidate("a", specificity=0.9)
        b = _candidate("b", specificity=0.9)
        ranked = rank_candidates([a, b])
        assert ranked[0].rank == ranked[1].rank
        assert not ranked[0].distinguishable
        assert not ranked[1].distinguishable

    def test_missing_separators_listed(self) -> None:
        candidate = _candidate("a")
        ranked = rank_candidates([candidate])
        assert len(ranked[0].separating_evidence_absent) > 0

    def test_empty_candidates(self) -> None:
        assert rank_candidates([]) == ()


class TestFindCommonAntecedents:
    def test_shared_upstream_detected(self) -> None:
        graph = Graph(edges=(_edge("a", "shared"), _edge("b", "shared")))
        result = find_common_antecedents(graph, ["a", "b"])
        assert len(result) == 1
        assert "shared" in result[0].shared

    def test_no_shared_upstream(self) -> None:
        graph = Graph(edges=(_edge("x", "a"), _edge("y", "b")))
        result = find_common_antecedents(graph, ["a", "b"])
        assert result == ()


class TestAnalyse:
    def test_no_candidates_refuses(self) -> None:
        result = analyse([])
        assert result.refusal is AnalysisRefusal.NO_CANDIDATES
        assert not result.is_conclusive

    def test_platform_gap_refuses(self) -> None:
        result = analyse([_candidate("a")], platform_gaps=[3, 4])
        assert result.refusal is AnalysisRefusal.PLATFORM_WIDE_GAP
        assert len(result.recommendations) == 1

    def test_excludes_alerting_service(self) -> None:
        result = analyse(
            [_candidate("alert-source"), _candidate("other", specificity=0.9)],
            excluded_service="alert-source",
        )
        assert all(entry.candidate.service != "alert-source" for entry in result.ranked)

    def test_all_excluded_refuses(self) -> None:
        result = analyse([_candidate("alert-source")], excluded_service="alert-source")
        assert result.refusal is AnalysisRefusal.NO_CANDIDATES

    def test_conclusive_when_top_is_distinguishable_mechanism_and_timing(self) -> None:
        strong = _candidate(
            "strong",
            correlation=_correlation(0.95),
            specificity=0.9,
            precedes_symptom=True,
            graph_path=PathQuality.OBSERVED_ONLY,
        )
        weak = _candidate("weak")
        result = analyse([strong, weak])
        assert result.is_conclusive
        assert result.caveat

    def test_with_graph_finds_antecedents(self) -> None:
        graph = Graph(edges=(_edge("a", "shared"), _edge("b", "shared")))
        candidates = [_candidate("a", specificity=0.9), _candidate("b", specificity=0.9)]
        result = analyse(candidates, graph=graph)
        assert len(result.common_antecedents) == 1

    def test_window_provenance_propagated(self) -> None:
        result = analyse([_candidate("a")], window_provenance=WindowProvenance.DERIVED_FROM_SIGNAL)
        assert result.window_provenance is WindowProvenance.DERIVED_FROM_SIGNAL


class TestRecommend:
    def test_censored_timeline_recommends_widen_window(self) -> None:
        from app.root_cause.enums import RecommendationKind
        from app.root_cause.timeline import Onset, Timeline

        censored = Onset(
            service="a",
            fingerprint="fp",
            at=None,
            censored_left=True,
            signal_id="s1",
            preceding_quiet=None,
        )
        timeline = Timeline(
            groups=(), unplaceable=(), censored=(censored,), window_start=T0, window_end=T0
        )
        result = analyse([_candidate("a", specificity=0.9)], timeline=timeline)
        assert any(r.kind is RecommendationKind.WIDEN_WINDOW for r in result.recommendations)

    def test_incomplete_blast_recommends_expand_graph(self) -> None:
        from app.root_cause.enums import RecommendationKind

        # Dependents chain: n(i+1) calls n(i), so walking DOWNSTREAM from n0
        # reaches n1, n2, ... -- deep enough to be truncated at max_depth=1.
        graph = Graph(edges=tuple(_edge(f"n{i+1}", f"n{i}") for i in range(10)))
        blast = blast_radius(graph, "n0", symptomatic=[], instrumented=[], max_depth=1)
        result = analyse([_candidate("a", specificity=0.9)], blast=blast)
        assert any(r.kind is RecommendationKind.EXPAND_GRAPH for r in result.recommendations)

    def test_unobservable_blast_recommends_instrument(self) -> None:
        from app.root_cause.enums import RecommendationKind

        graph = Graph(edges=(_edge("caller", "origin"),))
        blast = blast_radius(graph, "origin", symptomatic=[], instrumented=[])
        result = analyse([_candidate("a", specificity=0.9)], blast=blast)
        assert any(r.kind is RecommendationKind.INSTRUMENT_SERVICE for r in result.recommendations)

    def test_shared_antecedent_recommends_separate_confounded(self) -> None:
        from app.root_cause.enums import RecommendationKind

        graph = Graph(edges=(_edge("a", "shared"), _edge("b", "shared")))
        candidates = [_candidate("a", specificity=0.9), _candidate("b", specificity=0.9)]
        result = analyse(candidates, graph=graph)
        assert any(r.kind is RecommendationKind.SEPARATE_CONFOUNDED for r in result.recommendations)


class TestIndistinguishableGapCoverage:
    def test_one_sided_correlation_is_distinguishable(self) -> None:
        with_corr = _candidate(
            "a",
            correlation=_correlation(0.9),
            specificity=0.9,
            precedes_symptom=True,
            graph_path=PathQuality.OBSERVED_ONLY,
        )
        without_corr = _candidate(
            "b", specificity=0.9, precedes_symptom=True, graph_path=PathQuality.OBSERVED_ONLY
        )
        ranked = rank_candidates([with_corr, without_corr])
        tiers = {entry.candidate.service: entry.candidate.tier for entry in ranked}
        # Different tiers (MECHANISM_AND_TIMING vs TIMING_ONLY) => not tied.
        assert tiers["a"] != tiers["b"] or ranked[0].distinguishable

    def test_below_min_paired_is_indistinguishable(self) -> None:
        low_paired_a = _candidate(
            "a",
            correlation=_correlation(0.9, paired=1),
            specificity=0.9,
            precedes_symptom=True,
            graph_path=PathQuality.OBSERVED_ONLY,
        )
        low_paired_b = _candidate(
            "b",
            correlation=_correlation(0.5, paired=1),
            specificity=0.9,
            precedes_symptom=True,
            graph_path=PathQuality.OBSERVED_ONLY,
        )
        ranked = rank_candidates([low_paired_a, low_paired_b])
        assert not ranked[0].distinguishable

    def test_declared_only_path_lists_as_missing_separator(self) -> None:
        candidate = _candidate("a", graph_path=PathQuality.DECLARED_ONLY, specificity=0.9)
        ranked = rank_candidates([candidate])
        assert any(
            "no observed traffic" in reason for reason in ranked[0].separating_evidence_absent
        )
