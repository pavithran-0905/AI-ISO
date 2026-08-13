"""Root cause analysis: graph reasoning, ranking, and refusal.

**There is no score field anywhere in this module.** A single composite
number ranks coincidence above mechanism, invites a threshold that turns
a correlation into a causal claim, and forces missing evidence to be
imputed to something. Candidates carry a discrete tier and a
lexicographic key over named evidence instead, and two candidates the
data cannot separate share a rank and say so.

Two traversals exist and are named in opposite directions, because the
inversion -- searching dependents for causes, or dependencies for blast
radius -- is plausible from either end and a line-graph test passes if
the author and reviewer share the confusion. :func:`assert_dual` checks
them against each other.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.root_cause.correlation import (
    MIN_JACCARD,
    CorrelationResult,
    expected_false_positives,
)
from app.root_cause.enums import (
    AnalysisRefusal,
    BlastBucket,
    Direction,
    EdgeKind,
    EvidenceTier,
    PathQuality,
    RecommendationKind,
    WindowProvenance,
)
from app.root_cause.timeline import Timeline

MAX_DEPTH = 4
"""service -> gateway -> service -> datastore -> host. Beyond four hops
everything in an estate reaches everything, and a blast radius that
includes the whole platform is not a finding."""

MAX_NODES = 500
SYNC_HOP_BUDGET = timedelta(seconds=30)
"""A 10-second timeout with three attempts -- the common retry
configuration."""

CACHE_MASK_BUDGET = timedelta(seconds=120)
MIN_PAIRED_FOR_SEPARATION = 2
"""Below two paired buckets there is no standard error to compare
candidates against, so they cannot be separated at all."""

MIN_SPECIFICITY = 0.50
"""A fingerprint present in more than half the baseline carries under one
bit of information about this incident."""


@dataclass(frozen=True, slots=True)
class LagBudget:
    """How long a symptom may take to cross an edge.

    ``maximum=None`` for asynchronous edges, because a consumer lagging
    four minutes behind is normal and any ceiling would be fabricated.
    ``minimum`` exists for caches: symptoms are expected *after* the TTL
    expires, so an instant symptom is evidence of a different mechanism,
    not a better fit.
    """

    minimum: timedelta
    maximum: timedelta | None
    unbounded_reason: str | None = None

    def admits(self, lag: timedelta) -> bool:
        if lag < self.minimum:
            return False
        return self.maximum is None or lag <= self.maximum


def budget_for(kind: EdgeKind, *, cache_ttl: timedelta | None = None) -> LagBudget:
    """The lag budget appropriate to an edge kind."""
    if kind is EdgeKind.ASYNCHRONOUS:
        return LagBudget(
            minimum=timedelta(0),
            maximum=None,
            unbounded_reason=(
                "Queue depth sets the delay on an async edge; any ceiling here "
                "would be invented."
            ),
        )
    if kind is EdgeKind.CACHE:
        ttl = cache_ttl or CACHE_MASK_BUDGET
        return LagBudget(minimum=ttl, maximum=None)
    return LagBudget(minimum=timedelta(0), maximum=SYNC_HOP_BUDGET)


@dataclass(frozen=True, slots=True)
class Edge:
    """A directed dependency: ``caller`` depends on ``callee``."""

    caller: str
    callee: str
    kind: EdgeKind
    is_observed: bool
    last_observed_at: datetime | None = None
    call_count: int | None = None

    @property
    def quality(self) -> PathQuality:
        return PathQuality.OBSERVED_ONLY if self.is_observed else PathQuality.DECLARED_ONLY


@dataclass(frozen=True, slots=True)
class Graph:
    """A service dependency graph with both adjacency directions built."""

    edges: tuple[Edge, ...]

    def _adjacency(self, direction: Direction) -> dict[str, list[Edge]]:
        adjacency: dict[str, list[Edge]] = {}
        for edge in self.edges:
            key = edge.caller if direction is Direction.UPSTREAM else edge.callee
            adjacency.setdefault(key, []).append(edge)
        return adjacency

    @property
    def nodes(self) -> tuple[str, ...]:
        seen = {edge.caller for edge in self.edges} | {edge.callee for edge in self.edges}
        return tuple(sorted(seen))

    def dependencies_of(self, service: str) -> tuple[Edge, ...]:
        """Edges to things ``service`` calls -- where a cause might be."""
        return tuple(edge for edge in self.edges if edge.caller == service)

    def dependents_of(self, service: str) -> tuple[Edge, ...]:
        """Edges from things that call ``service`` -- where impact lands."""
        return tuple(edge for edge in self.edges if edge.callee == service)


@dataclass(frozen=True, slots=True)
class Traversal:
    """What a bounded walk found, and whether it saw everything."""

    reached: tuple[str, ...]
    depth_by_service: Mapping[str, int]
    quality_by_service: Mapping[str, PathQuality]
    complete: bool
    truncated_at_depth: bool
    truncated_at_node_cap: bool


def walk(
    graph: Graph,
    origin: str,
    direction: Direction,
    *,
    max_depth: int = MAX_DEPTH,
    max_nodes: int = MAX_NODES,
) -> Traversal:
    """Breadth-first walk in one named direction.

    ``complete`` is returned because a truncated traversal presented as a
    finished one understates impact at exactly the moment impact is
    largest.
    """
    reached: dict[str, int] = {}
    quality: dict[str, PathQuality] = {}
    frontier = [(origin, 0, PathQuality.OBSERVED_ONLY)]
    truncated_depth = False
    truncated_nodes = False

    while frontier:
        service, depth, path_quality = frontier.pop(0)
        if service in reached:
            continue
        if len(reached) >= max_nodes:
            truncated_nodes = True
            break
        reached[service] = depth
        quality[service] = path_quality
        if depth >= max_depth:
            truncated_depth = True
            continue

        edges = (
            graph.dependencies_of(service)
            if direction is Direction.UPSTREAM
            else graph.dependents_of(service)
        )
        for edge in sorted(edges, key=lambda item: (item.callee, item.caller)):
            neighbour = edge.callee if direction is Direction.UPSTREAM else edge.caller
            # A declared-only hop taints the whole path: an edge that has
            # carried no traffic in months cannot corroborate anything.
            onward = (
                PathQuality.DECLARED_ONLY
                if not edge.is_observed or path_quality is PathQuality.DECLARED_ONLY
                else PathQuality.OBSERVED_ONLY
            )
            frontier.append((neighbour, depth + 1, onward))

    return Traversal(
        reached=tuple(sorted(reached)),
        depth_by_service=dict(sorted(reached.items())),
        quality_by_service=dict(sorted(quality.items())),
        complete=not (truncated_depth or truncated_nodes),
        truncated_at_depth=truncated_depth,
        truncated_at_node_cap=truncated_nodes,
    )


def strongly_connected_components(graph: Graph) -> tuple[tuple[str, ...], ...]:
    """Tarjan's SCCs, sorted for determinism.

    A visited set stops the infinite loop, and tests catch that. Nothing
    stops the engine from crediting "A is a dependency of B" inside a
    cycle when the graph says the reverse just as loudly -- so graph
    evidence is voided for any pair sharing a component.
    """
    index_of: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[tuple[str, ...]] = []
    counter = 0

    successors: dict[str, list[str]] = {}
    for edge in graph.edges:
        successors.setdefault(edge.caller, []).append(edge.callee)

    def strongconnect(node: str) -> None:
        nonlocal counter
        index_of[node] = low[node] = counter
        counter += 1
        stack.append(node)
        on_stack.add(node)

        for successor in sorted(successors.get(node, [])):
            if successor not in index_of:
                strongconnect(successor)
                low[node] = min(low[node], low[successor])
            elif successor in on_stack:
                low[node] = min(low[node], index_of[successor])

        if low[node] == index_of[node]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)
                if member == node:
                    break
            components.append(tuple(sorted(component)))

    for node in graph.nodes:
        if node not in index_of:
            strongconnect(node)

    return tuple(sorted(components))


def share_component(components: Sequence[Sequence[str]], left: str, right: str) -> bool:
    """Whether two services sit in the same cycle."""
    return any(left in component and right in component for component in components)


def assert_dual(graph: Graph, upstream: str, downstream: str) -> bool:
    """Cross-check the two traversals on a ranked pair.

    If ``downstream`` is reachable from ``upstream`` by dependencies,
    then ``upstream`` must be reachable from ``downstream`` by
    dependents. When that fails, the direction has been inverted
    somewhere, and this is the only check that notices.
    """
    forward = walk(graph, upstream, Direction.UPSTREAM)
    backward = walk(graph, downstream, Direction.DOWNSTREAM)
    return (downstream in forward.reached) == (upstream in backward.reached)


@dataclass(frozen=True, slots=True)
class BlastRadius:
    """Who is affected, in three buckets and with no total.

    An aggregate would have to choose how to count the services nobody
    can see, and every choice misleads.
    """

    origin: str
    observed_affected: tuple[str, ...]
    observed_healthy: tuple[str, ...]
    unobservable: tuple[str, ...]
    traversal: Traversal

    def bucket_of(self, service: str) -> BlastBucket | None:
        if service in self.observed_affected:
            return BlastBucket.OBSERVED_AFFECTED
        if service in self.observed_healthy:
            return BlastBucket.OBSERVED_HEALTHY
        if service in self.unobservable:
            return BlastBucket.UNOBSERVABLE
        return None


def blast_radius(
    graph: Graph,
    origin: str,
    *,
    symptomatic: Sequence[str],
    instrumented: Sequence[str],
    max_depth: int = MAX_DEPTH,
) -> BlastRadius:
    """Which dependents of ``origin`` are affected.

    Traverses *dependents*, never dependencies. The named direction is
    the whole defence.
    """
    traversal = walk(graph, origin, Direction.DOWNSTREAM, max_depth=max_depth)
    symptom_set = set(symptomatic)
    instrument_set = set(instrumented)
    reached = [service for service in traversal.reached if service != origin]

    return BlastRadius(
        origin=origin,
        observed_affected=tuple(s for s in reached if s in symptom_set),
        observed_healthy=tuple(s for s in reached if s not in symptom_set and s in instrument_set),
        unobservable=tuple(s for s in reached if s not in instrument_set),
        traversal=traversal,
    )


@dataclass(frozen=True, slots=True)
class Candidate:
    """One possible origin, with its evidence kept separate and named."""

    service: str
    tier: EvidenceTier
    correlation: CorrelationResult | None
    activity_jaccard: float | None
    specificity: float | None
    precedes_symptom: bool
    graph_path: PathQuality | None
    graph_depth: int | None
    in_cycle_with_symptom: bool
    lag_within_budget: bool | None
    change_nearby: bool
    notes: tuple[str, ...] = ()

    @property
    def has_mechanism(self) -> bool:
        return (
            self.graph_path is not None
            and not self.in_cycle_with_symptom
            and self.lag_within_budget is not False
        )

    @property
    def has_timing(self) -> bool:
        return self.precedes_symptom

    @property
    def ranking_key(self) -> tuple[int, int, int, float, float, str]:
        """A lexicographic key over discrete evidence, not a score.

        Ordered so that mechanism outranks coincidence no matter how
        strong the coincidence: a correlation of 0.99 with no path never
        overtakes a corroborated path with a weaker one.
        """
        tier_rank = _TIER_ORDER.index(self.tier)
        corroborated = 0 if self.graph_path is PathQuality.OBSERVED_ONLY else 1
        timing = 0 if self.precedes_symptom else 1
        coefficient = (
            -abs(self.correlation.coefficient)
            if (self.correlation and self.correlation.coefficient is not None)
            else 0.0
        )
        specificity = -(self.specificity or 0.0)
        return (tier_rank, corroborated, timing, coefficient, specificity, self.service)


_TIER_ORDER = (
    EvidenceTier.MECHANISM_AND_TIMING,
    EvidenceTier.TIMING_ONLY,
    EvidenceTier.MECHANISM_ONLY,
    EvidenceTier.COINCIDENT,
    EvidenceTier.INSUFFICIENT_EVIDENCE,
)


def classify_tier(  # noqa: PLR0911 - one exit per EvidenceTier, by design
    candidate: Candidate,
) -> EvidenceTier:
    """Assign a tier from what was actually established."""
    if candidate.correlation is not None and candidate.correlation.unmeasurable is not None:
        return EvidenceTier.INSUFFICIENT_EVIDENCE
    if candidate.specificity is not None and candidate.specificity < MIN_SPECIFICITY:
        return EvidenceTier.COINCIDENT

    measured = (
        candidate.correlation is not None
        and candidate.correlation.coefficient is not None
        and candidate.correlation.significant
    )
    overlapping = (
        candidate.activity_jaccard is not None and candidate.activity_jaccard >= MIN_JACCARD
    )
    timing = candidate.has_timing and (measured or overlapping)

    if candidate.has_mechanism and timing:
        return EvidenceTier.MECHANISM_AND_TIMING
    if timing:
        return EvidenceTier.TIMING_ONLY
    if candidate.has_mechanism:
        return EvidenceTier.MECHANISM_ONLY
    if measured or overlapping:
        return EvidenceTier.COINCIDENT
    return EvidenceTier.INSUFFICIENT_EVIDENCE


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    """A candidate with its position and whether that position is real."""

    candidate: Candidate
    rank: int
    distinguishable: bool
    separating_evidence_absent: tuple[str, ...]


def rank_candidates(candidates: Sequence[Candidate]) -> tuple[RankedCandidate, ...]:
    """Order candidates, sharing a rank where the data cannot separate.

    Two candidates whose evidence differs only in the fourth decimal are
    printed 1 and 2, and someone acts on 1. Here they share rank 1 and
    carry ``distinguishable=False`` with the evidence that is missing.
    """
    ordered = sorted(candidates, key=lambda item: item.ranking_key)
    ranked: list[RankedCandidate] = []
    rank = 0
    previous: Candidate | None = None

    for index, candidate in enumerate(ordered):
        tied = previous is not None and _indistinguishable(previous, candidate)
        if not tied:
            rank = index + 1
        ranked.append(
            RankedCandidate(
                candidate=candidate,
                rank=rank,
                distinguishable=not tied,
                separating_evidence_absent=_missing_separators(candidate),
            )
        )
        previous = candidate

    # A tie marks *both* members, not just the second one: a reader
    # looking only at rank 1 must see that rank 1 is shared.
    tied_ranks = {entry.rank for entry in ranked if not entry.distinguishable}
    return tuple(
        RankedCandidate(
            candidate=entry.candidate,
            rank=entry.rank,
            distinguishable=entry.rank not in tied_ranks,
            separating_evidence_absent=entry.separating_evidence_absent,
        )
        for entry in ranked
    )


def _indistinguishable(left: Candidate, right: Candidate) -> bool:
    """Whether two candidates differ by less than the measurement error."""
    if left.tier is not right.tier:
        return False
    left_rho = left.correlation.coefficient if left.correlation else None
    right_rho = right.correlation.coefficient if right.correlation else None
    if left_rho is None or right_rho is None:
        return left_rho is right_rho
    paired = min(
        left.correlation.paired_buckets if left.correlation else 0,
        right.correlation.paired_buckets if right.correlation else 0,
    )
    if paired < MIN_PAIRED_FOR_SEPARATION:
        return True
    standard_error = 1.0 / math.sqrt(paired - 1)
    return bool(abs(abs(left_rho) - abs(right_rho)) < standard_error)


def _missing_separators(candidate: Candidate) -> tuple[str, ...]:
    """Which evidence, if collected, would break a tie."""
    missing: list[str] = []
    if candidate.graph_path is None:
        missing.append("no dependency path is known between this service and the symptom")
    if candidate.graph_path is PathQuality.DECLARED_ONLY:
        missing.append("the path is declared but has carried no observed traffic")
    if not candidate.precedes_symptom:
        missing.append("no onset ordering could be established")
    if candidate.specificity is None:
        missing.append("no baseline exists to judge how unusual this symptom is")
    if not candidate.change_nearby:
        missing.append("no change record was found near the onset")
    return tuple(missing)


@dataclass(frozen=True, slots=True)
class CommonAntecedent:
    """Candidates that share an upstream, and so are not independent.

    Three symptoms of one shared-cache failure look like three agreeing
    candidates and read as corroboration. They are one finding.
    """

    services: tuple[str, ...]
    shared: tuple[str, ...]


def find_common_antecedents(
    graph: Graph, services: Sequence[str], *, max_depth: int = MAX_DEPTH
) -> tuple[CommonAntecedent, ...]:
    """Groups of candidates whose upstream closures intersect."""
    closures = {
        service: set(walk(graph, service, Direction.UPSTREAM, max_depth=max_depth).reached)
        - {service}
        for service in services
    }
    found: list[CommonAntecedent] = []
    ordered = sorted(closures)
    for i, left in enumerate(ordered):
        for right in ordered[i + 1 :]:
            shared = closures[left] & closures[right]
            if shared:
                found.append(CommonAntecedent(services=(left, right), shared=tuple(sorted(shared))))
    return tuple(found)


@dataclass(frozen=True, slots=True)
class Recommendation:
    """A next step, and what it would settle."""

    kind: RecommendationKind
    target: str | None
    would_separate: str


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """The finding, shaped so it cannot be read as a causal claim.

    ``ranked`` is ordered by evidence, and the top entry is a candidate,
    never a conclusion. ``refusal`` is set when nothing could be ranked
    at all -- an empty ranking and a refusal are different answers.
    """

    ranked: tuple[RankedCandidate, ...]
    timeline: Timeline | None
    blast: BlastRadius | None
    common_antecedents: tuple[CommonAntecedent, ...]
    recommendations: tuple[Recommendation, ...]
    comparisons_made: int
    expected_false_positives: float
    platform_gap_buckets: tuple[int, ...]
    window_provenance: WindowProvenance
    refusal: AnalysisRefusal | None
    narrative: str | None = None
    narrative_backend: str | None = None

    @property
    def is_conclusive(self) -> bool:
        """Whether one candidate stands alone with both kinds of evidence."""
        if not self.ranked or self.refusal is not None:
            return False
        top = self.ranked[0]
        return top.distinguishable and top.candidate.tier is EvidenceTier.MECHANISM_AND_TIMING

    @property
    def caveat(self) -> str:
        return (
            "This engine correlates and traverses declared and observed "
            "dependencies. It does not establish causation, and no tier here "
            "asserts one."
        )


def recommend(
    result_candidates: Sequence[RankedCandidate],
    *,
    timeline: Timeline | None,
    blast: BlastRadius | None,
    antecedents: Sequence[CommonAntecedent] = (),
) -> tuple[Recommendation, ...]:
    """What to collect next, ordered by what it would resolve.

    Every recommendation acquires or verifies evidence. None of them
    remediates, because remediation asserts a cause.
    """
    recommendations: list[Recommendation] = []

    if timeline is not None and timeline.censored:
        recommendations.append(
            Recommendation(
                kind=RecommendationKind.WIDEN_WINDOW,
                target=None,
                would_separate=(
                    f"{len(timeline.censored)} onset(s) begin at the window edge, so "
                    "their true start is outside the data and their ordering is "
                    "unestablished."
                ),
            )
        )
    if blast is not None and not blast.traversal.complete:
        recommendations.append(
            Recommendation(
                kind=RecommendationKind.EXPAND_GRAPH,
                target=blast.origin,
                would_separate=(
                    "The traversal hit its bound, so the affected set is a subset "
                    "of the real one."
                ),
            )
        )
    if blast is not None and blast.unobservable:
        recommendations.append(
            Recommendation(
                kind=RecommendationKind.INSTRUMENT_SERVICE,
                target=blast.unobservable[0],
                would_separate=(
                    f"{len(blast.unobservable)} reachable service(s) emit nothing, "
                    "so they are neither affected nor healthy in this result."
                ),
            )
        )
    for antecedent in antecedents:
        recommendations.append(
            Recommendation(
                kind=RecommendationKind.SEPARATE_CONFOUNDED,
                target=antecedent.shared[0] if antecedent.shared else None,
                would_separate=(
                    f"{' and '.join(antecedent.services)} share upstream "
                    f"{', '.join(antecedent.shared)}, so they agree because of a "
                    "common antecedent rather than independently."
                ),
            )
        )
    for entry in result_candidates:
        if entry.distinguishable:
            continue
        for missing in entry.separating_evidence_absent[:1]:
            recommendations.append(
                Recommendation(
                    kind=RecommendationKind.COLLECT_TRACES,
                    target=entry.candidate.service,
                    would_separate=f"Rank {entry.rank} is shared: {missing}.",
                )
            )
    return tuple(recommendations)


def analyse(
    candidates: Sequence[Candidate],
    *,
    timeline: Timeline | None = None,
    blast: BlastRadius | None = None,
    graph: Graph | None = None,
    platform_gaps: Sequence[int] = (),
    comparisons_made: int = 0,
    window_provenance: WindowProvenance = WindowProvenance.OPERATOR_SUPPLIED,
    excluded_service: str | None = None,
) -> AnalysisResult:
    """Assemble a finding from evidence already gathered.

    ``excluded_service`` removes the service whose alert defined the
    window. Left in, it correlates perfectly with its own symptom and
    wins every ranking -- a circularity that no test of the correlation
    maths would ever catch.
    """
    pool = [
        candidate
        for candidate in candidates
        if excluded_service is None or candidate.service != excluded_service
    ]
    if not pool:
        return AnalysisResult(
            ranked=(),
            timeline=timeline,
            blast=blast,
            common_antecedents=(),
            recommendations=(),
            comparisons_made=comparisons_made,
            expected_false_positives=expected_false_positives(comparisons_made),
            platform_gap_buckets=tuple(platform_gaps),
            window_provenance=window_provenance,
            refusal=AnalysisRefusal.NO_CANDIDATES,
        )
    if platform_gaps:
        return AnalysisResult(
            ranked=(),
            timeline=timeline,
            blast=blast,
            common_antecedents=(),
            recommendations=(
                Recommendation(
                    kind=RecommendationKind.VERIFY_CLOCK_SYNC,
                    target=None,
                    would_separate=(
                        f"{len(platform_gaps)} bucket(s) show most of the estate "
                        "silent at once, which is a collector failure before it is "
                        "an outage. Any correlation computed across them would be "
                        "near-perfect and meaningless."
                    ),
                ),
            ),
            comparisons_made=comparisons_made,
            expected_false_positives=expected_false_positives(comparisons_made),
            platform_gap_buckets=tuple(platform_gaps),
            window_provenance=window_provenance,
            refusal=AnalysisRefusal.PLATFORM_WIDE_GAP,
        )

    tiered = tuple(
        Candidate(
            service=candidate.service,
            tier=classify_tier(candidate),
            correlation=candidate.correlation,
            activity_jaccard=candidate.activity_jaccard,
            specificity=candidate.specificity,
            precedes_symptom=candidate.precedes_symptom,
            graph_path=candidate.graph_path,
            graph_depth=candidate.graph_depth,
            in_cycle_with_symptom=candidate.in_cycle_with_symptom,
            lag_within_budget=candidate.lag_within_budget,
            change_nearby=candidate.change_nearby,
            notes=candidate.notes,
        )
        for candidate in pool
    )
    ranked = rank_candidates(tiered)
    antecedents = (
        find_common_antecedents(graph, [c.service for c in tiered]) if graph is not None else ()
    )
    return AnalysisResult(
        ranked=ranked,
        timeline=timeline,
        blast=blast,
        common_antecedents=antecedents,
        recommendations=recommend(ranked, timeline=timeline, blast=blast, antecedents=antecedents),
        comparisons_made=comparisons_made,
        expected_false_positives=expected_false_positives(comparisons_made),
        platform_gap_buckets=tuple(platform_gaps),
        window_provenance=window_provenance,
        refusal=None,
    )


__all__ = [
    "CACHE_MASK_BUDGET",
    "MAX_DEPTH",
    "MAX_NODES",
    "MIN_SPECIFICITY",
    "SYNC_HOP_BUDGET",
    "AnalysisResult",
    "BlastRadius",
    "Candidate",
    "CommonAntecedent",
    "Edge",
    "Graph",
    "LagBudget",
    "RankedCandidate",
    "Recommendation",
    "Traversal",
    "analyse",
    "assert_dual",
    "blast_radius",
    "budget_for",
    "classify_tier",
    "find_common_antecedents",
    "rank_candidates",
    "share_component",
    "strongly_connected_components",
    "walk",
]
