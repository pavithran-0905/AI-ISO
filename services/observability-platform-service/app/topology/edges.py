"""Edge inference from traces, and confidence in what was inferred.

**The boundary rule.** An edge is emitted only at an instrumented service
boundary crossing -- never for every parent/child pair. Two consequences
that look like details and are the whole design:

*Same-service pairs emit nothing.* An INTERNAL-to-INTERNAL chain inside
one service is not a dependency, and emitting it produces ``A -> A``
self-loops that inflate fan-out, break topological ordering, and make
every strongly-connected component non-trivial.

*A severed parent emits a missing link, never a synthesised edge.* When a
span's parent is absent, walking up to the nearest present ancestor and
emitting ``A -> C`` is the single most damaging thing this module could
do: the truth was ``A -> B -> C`` with B sampled out, the fabricated edge
is indistinguishable from a real one forever after, and it understates
B's importance in every impact analysis that follows.

**Existence and volume are different numbers and are never multiplied.**
``observations / total_traces`` answers "is this edge busy?" while
claiming to answer "is this edge real?". A nightly reconciliation seen
thirty times in a month scores 0.0003, drops below any sensible filter,
and vanishes from impact analysis -- and it is exactly the dependency
whose failure produces a Monday-morning incident.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.topology.enums import (
    ConfidenceBand,
    EdgeEvidenceKind,
    SpanKindLabel,
    TopologyEdgeKind,
)

MISATTRIBUTION_RATE: Mapping[EdgeEvidenceKind, float] = {
    # Per-observation chance that this evidence names the wrong caller.
    EdgeEvidenceKind.SERVER_CHILD_OF_CLIENT: 0.001,
    EdgeEvidenceKind.SERVER_CHILD_OF_REMOTE: 0.010,
    EdgeEvidenceKind.PRODUCER_CONSUMER_LINK: 0.020,
    EdgeEvidenceKind.CLIENT_PEER_ATTRIBUTE: 0.050,
}

MAX_INDEPENDENT_PER_HOUR = 3
"""A retry storm produces five thousand spans from one caller in ninety
seconds, all describing one causal event. Confidence saturates at k = 3
even for the weakest evidence, so one hour of observation can reach
PROVEN for a direct link and LIKELY for a peer attribute -- and a burst
confined to one hour can never manufacture more certainty than that."""

MIN_OBSERVATIONS_FOR_RHYTHM = 2
"""One observation has no gap to measure a rhythm from."""

PROVEN_AT = 0.999
LIKELY_AT = 0.95


@dataclass(frozen=True, slots=True)
class SpanRecord:
    """One span, normalised to what edge inference actually needs."""

    span_id: str
    trace_id: str
    parent_span_id: str | None
    service: str
    kind: SpanKindLabel
    operation: str
    start_ns: int
    duration_ns: int
    errored: bool = False
    peer_service: str | None = None
    instance_id: str | None = None
    links_to: tuple[str, ...] = ()

    @property
    def end_ns(self) -> int:
        return self.start_ns + self.duration_ns


@dataclass(frozen=True, slots=True)
class EdgeObservation:
    """One witnessed crossing of a service boundary."""

    caller_service: str
    callee_service: str
    kind: TopologyEdgeKind
    evidence: EdgeEvidenceKind
    operation: str | None
    trace_id: str
    caller_instance_id: str | None
    observed_at_ns: int
    duration_ns: int | None
    errored: bool

    @property
    def key(self) -> tuple[str, str]:
        return (self.caller_service, self.callee_service)


@dataclass(frozen=True, slots=True)
class MissingLinkObservation:
    """Evidence that some caller exists which cannot be named.

    Carried through into fan-in as an explicit unknown rather than being
    resolved into a guess.
    """

    callee_service: str
    missing_parent_span_id: str
    trace_id: str
    observed_at_ns: int


@dataclass(frozen=True, slots=True)
class EdgeInferenceResult:
    """What one trace yielded, including what it could not resolve."""

    observations: tuple[EdgeObservation, ...]
    missing_links: tuple[MissingLinkObservation, ...]
    same_service_pairs_skipped: int
    orphan_spans: int


def infer_edges(spans: Sequence[SpanRecord]) -> EdgeInferenceResult:
    """Emit an edge for every instrumented boundary crossing, and only those.

    Evidence strength descends from a SERVER span whose parent is a CLIENT
    span in another service, through a remote parent of any kind, through
    a producer/consumer link, down to a CLIENT span carrying a
    ``peer.service`` attribute with no matching SERVER child anywhere in
    the trace.
    """
    by_id = {span.span_id: span for span in spans}
    observations: list[EdgeObservation] = []
    missing: list[MissingLinkObservation] = []
    same_service = 0
    orphans = 0

    server_parents = {
        span.parent_span_id
        for span in spans
        if span.kind is SpanKindLabel.SERVER and span.parent_span_id
    }

    for span in sorted(spans, key=lambda item: (item.start_ns, item.span_id)):
        if span.kind in (SpanKindLabel.SERVER, SpanKindLabel.CONSUMER):
            observation = _from_parent(span, by_id)
            if observation is not None:
                observations.append(observation)
                continue
            if span.parent_span_id is None:
                orphans += 1
                continue
            if span.parent_span_id not in by_id:
                # The parent was sampled out. Emitting an edge to the nearest
                # present ancestor would invent a hop that never existed.
                missing.append(
                    MissingLinkObservation(
                        callee_service=span.service,
                        missing_parent_span_id=span.parent_span_id,
                        trace_id=span.trace_id,
                        observed_at_ns=span.start_ns,
                    )
                )
                continue
            same_service += 1

        elif span.kind is SpanKindLabel.CLIENT and span.peer_service:
            if span.span_id in server_parents:
                continue  # A SERVER child already produced stronger evidence.
            if span.peer_service == span.service:
                same_service += 1
                continue
            observations.append(
                EdgeObservation(
                    caller_service=span.service,
                    callee_service=span.peer_service,
                    kind=TopologyEdgeKind.SYNC_CALL,
                    evidence=EdgeEvidenceKind.CLIENT_PEER_ATTRIBUTE,
                    operation=span.operation,
                    trace_id=span.trace_id,
                    caller_instance_id=span.instance_id,
                    observed_at_ns=span.start_ns,
                    duration_ns=span.duration_ns,
                    errored=span.errored,
                )
            )

    return EdgeInferenceResult(
        observations=tuple(observations),
        missing_links=tuple(missing),
        same_service_pairs_skipped=same_service,
        orphan_spans=orphans,
    )


def _from_parent(span: SpanRecord, by_id: Mapping[str, SpanRecord]) -> EdgeObservation | None:
    """An edge from a resolvable cross-service parent, or ``None``."""
    parent_id = span.parent_span_id
    candidates = [parent_id, *span.links_to] if parent_id else list(span.links_to)
    for candidate in candidates:
        parent = by_id.get(candidate or "")
        if parent is None or parent.service == span.service:
            continue

        if span.kind is SpanKindLabel.CONSUMER or parent.kind is SpanKindLabel.PRODUCER:
            return EdgeObservation(
                caller_service=parent.service,
                callee_service=span.service,
                kind=TopologyEdgeKind.ASYNC_MESSAGE,
                evidence=EdgeEvidenceKind.PRODUCER_CONSUMER_LINK,
                operation=span.operation,
                trace_id=span.trace_id,
                caller_instance_id=parent.instance_id,
                observed_at_ns=span.start_ns,
                # Publish-to-consume wall time is queue dwell, not caller
                # blocking. Putting it on a critical path yields "checkout
                # took four hours".
                duration_ns=None,
                errored=span.errored,
            )
        evidence = (
            EdgeEvidenceKind.SERVER_CHILD_OF_CLIENT
            if parent.kind is SpanKindLabel.CLIENT
            else EdgeEvidenceKind.SERVER_CHILD_OF_REMOTE
        )
        return EdgeObservation(
            caller_service=parent.service,
            callee_service=span.service,
            kind=TopologyEdgeKind.SYNC_CALL,
            evidence=evidence,
            operation=span.operation,
            trace_id=span.trace_id,
            caller_instance_id=parent.instance_id,
            observed_at_ns=span.start_ns,
            duration_ns=parent.duration_ns,
            errored=span.errored,
        )
    return None


@dataclass(frozen=True, slots=True)
class ExistenceConfidence:
    """How sure we are the edge is real, with every input beside it.

    Saturates by about three independent observations, and that is the
    point: ten thousand observations do not make an edge's *existence*
    more certain than three do, they make its *rate* more certain.
    """

    value: float
    effective_observations: int
    raw_observations: int
    distinct_traces: int
    distinct_caller_instances: int | None
    distinct_observation_hours: int
    evidence_counts: Mapping[EdgeEvidenceKind, int]

    @property
    def band(self) -> ConfidenceBand:
        if self.value >= PROVEN_AT:
            return ConfidenceBand.PROVEN
        if self.value >= LIKELY_AT:
            return ConfidenceBand.LIKELY
        return ConfidenceBand.WEAK


def existence_confidence(
    observations: Sequence[EdgeObservation],
) -> ExistenceConfidence | None:
    """Probability that at least one observation was not a misattribution.

    ``1 - product(epsilon ** k)`` over evidence kinds. Independence is
    bounded per hour so a burst cannot manufacture certainty.
    """
    if not observations:
        return None

    traces = {observation.trace_id for observation in observations}
    hours = {observation.observed_at_ns // 3_600_000_000_000 for observation in observations}
    instances = {
        observation.caller_instance_id
        for observation in observations
        if observation.caller_instance_id
    }

    cap = MAX_INDEPENDENT_PER_HOUR * max(1, len(hours))
    effective = min(len(traces), cap)

    counts: dict[EdgeEvidenceKind, int] = {}
    for observation in observations:
        counts[observation.evidence] = counts.get(observation.evidence, 0) + 1

    # Effective observations are shared out across evidence kinds in
    # proportion to how often each was seen, so a thousand weak
    # observations cannot borrow the strength of one strong one.
    total = sum(counts.values())
    survival = 1.0
    for kind, count in sorted(counts.items()):
        share = effective * count / total
        survival *= MISATTRIBUTION_RATE[kind] ** share

    return ExistenceConfidence(
        value=1.0 - survival,
        effective_observations=effective,
        raw_observations=len(observations),
        distinct_traces=len(traces),
        distinct_caller_instances=len(instances) or None,
        distinct_observation_hours=len(hours),
        evidence_counts=dict(sorted(counts.items())),
    )


@dataclass(frozen=True, slots=True)
class EdgeVolume:
    """How busy an edge is -- ``None`` when sampling is unknown.

    Extrapolating a rate from sampled traces without knowing the sampling
    ratio produces a number that looks like traffic and is not.
    """

    call_count: int | None
    error_count: int | None
    sampling_ratio: float | None
    window_seconds: float

    @property
    def calls_per_second(self) -> float | None:
        if self.call_count is None or self.window_seconds <= 0:
            return None
        return self.call_count / self.window_seconds

    @property
    def error_ratio(self) -> float | None:
        if not self.call_count or self.error_count is None:
            return None
        return self.error_count / self.call_count


def measure_volume(
    observations: Sequence[EdgeObservation],
    *,
    window_seconds: float,
    sampling_ratio: float | None,
) -> EdgeVolume:
    """Count traffic, refusing to extrapolate without a sampling ratio."""
    if sampling_ratio is None:
        return EdgeVolume(
            call_count=None,
            error_count=None,
            sampling_ratio=None,
            window_seconds=window_seconds,
        )
    if not 0.0 < sampling_ratio <= 1.0:
        raise ValueError(f"A sampling ratio must lie in (0, 1]; got {sampling_ratio}.")
    scale = 1.0 / sampling_ratio
    return EdgeVolume(
        call_count=round(len(observations) * scale),
        error_count=round(sum(1 for observation in observations if observation.errored) * scale),
        sampling_ratio=sampling_ratio,
        window_seconds=window_seconds,
    )


@dataclass(frozen=True, slots=True)
class EdgeRhythm:
    """How regularly an edge is used, and when silence becomes staleness.

    Staleness is relative to the edge's own rhythm rather than a global
    constant. A nightly batch link is not stale after two hours; a
    request-path link is stale after two minutes. One threshold for both
    either hides a real outage or buries the operator in false ones.
    """

    median_gap_ns: float | None
    observation_count: int
    last_observed_ns: int | None

    def is_stale(self, now_ns: int, *, tolerance: float = 3.0) -> bool | None:
        """``None`` when there is not enough history to have a rhythm."""
        if self.median_gap_ns is None or self.last_observed_ns is None:
            return None
        return (now_ns - self.last_observed_ns) > tolerance * self.median_gap_ns


def measure_rhythm(observations: Sequence[EdgeObservation]) -> EdgeRhythm:
    """The typical gap between observations of an edge."""
    times = sorted(observation.observed_at_ns for observation in observations)
    if len(times) < MIN_OBSERVATIONS_FOR_RHYTHM:
        return EdgeRhythm(
            median_gap_ns=None,
            observation_count=len(times),
            last_observed_ns=times[-1] if times else None,
        )
    gaps = sorted(times[i] - times[i - 1] for i in range(1, len(times)))
    middle = len(gaps) // 2
    median = float(gaps[middle]) if len(gaps) % 2 else (gaps[middle - 1] + gaps[middle]) / 2.0
    return EdgeRhythm(
        median_gap_ns=median, observation_count=len(times), last_observed_ns=times[-1]
    )


@dataclass(frozen=True, slots=True)
class InferredEdge:
    """An aggregated edge: existence, volume and rhythm kept apart."""

    caller_service: str
    callee_service: str
    kind: TopologyEdgeKind
    confidence: ExistenceConfidence
    volume: EdgeVolume
    rhythm: EdgeRhythm
    operations: tuple[str, ...] = field(default_factory=tuple)


def aggregate_edges(
    observations: Sequence[EdgeObservation],
    *,
    window_seconds: float,
    sampling_ratio: float | None = None,
    max_operations: int = 20,
) -> tuple[InferredEdge, ...]:
    """Group observations into edges, one per caller/callee/kind.

    Operation names are capped: an unbounded set turns a route with an id
    in the path into thousands of distinct operations and the edge stops
    being one edge.
    """
    grouped: dict[tuple[str, str, TopologyEdgeKind], list[EdgeObservation]] = {}
    for observation in observations:
        grouped.setdefault(
            (observation.caller_service, observation.callee_service, observation.kind),
            [],
        ).append(observation)

    edges: list[InferredEdge] = []
    for (caller, callee, kind), members in sorted(
        grouped.items(), key=lambda item: (item[0][0], item[0][1], item[0][2].value)
    ):
        confidence = existence_confidence(members)
        if confidence is None:
            continue
        operations = sorted({member.operation for member in members if member.operation})
        edges.append(
            InferredEdge(
                caller_service=caller,
                callee_service=callee,
                kind=kind,
                confidence=confidence,
                volume=measure_volume(
                    members,
                    window_seconds=window_seconds,
                    sampling_ratio=sampling_ratio,
                ),
                rhythm=measure_rhythm(members),
                operations=tuple(operations[:max_operations]),
            )
        )
    return tuple(edges)


def confidence_for_counts(counts: Mapping[EdgeEvidenceKind, int]) -> float:
    """Existence confidence from raw per-kind counts, for explanation."""
    survival = math.prod(MISATTRIBUTION_RATE[kind] ** count for kind, count in counts.items())
    return 1.0 - survival


__all__ = [
    "LIKELY_AT",
    "MAX_INDEPENDENT_PER_HOUR",
    "MISATTRIBUTION_RATE",
    "PROVEN_AT",
    "EdgeInferenceResult",
    "EdgeObservation",
    "EdgeRhythm",
    "EdgeVolume",
    "ExistenceConfidence",
    "InferredEdge",
    "MissingLinkObservation",
    "SpanRecord",
    "aggregate_edges",
    "confidence_for_counts",
    "existence_confidence",
    "infer_edges",
    "measure_rhythm",
    "measure_volume",
]
