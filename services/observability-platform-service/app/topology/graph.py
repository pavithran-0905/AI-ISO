"""Topology graph: cycles, single points of failure, and critical path.

**Single points of failure are dominators, not high-betweenness nodes.**
Betweenness counts how many shortest paths cross a node, which ranks a
busy hub above a quiet chokepoint -- and it is the chokepoint that takes
the estate down. A node dominates another when *every* path from the
entry point passes through it, which is precisely the property "if this
is down, that is unreachable".

**The longest span is not the critical path.** A parent span's duration
contains all its children; picking the longest span therefore picks the
root every time. What matters is self time -- the parent's duration minus
the part it spent blocked on children -- and the chain of children that
were actually on the blocking path.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.topology.edges import InferredEdge, MissingLinkObservation, SpanRecord
from app.topology.enums import (
    ConfidenceBand,
    CriticalityInput,
    SpanKindLabel,
    TopologyEdgeKind,
)


@dataclass(frozen=True, slots=True)
class TopologyNode:
    """One service, with the inputs to its criticality kept separate."""

    service: str
    fan_in: int
    fan_out: int
    in_cycle: bool
    dominates: tuple[str, ...]
    unnamed_callers: int
    criticality_inputs: tuple[CriticalityInput, ...]

    @property
    def is_single_point_of_failure(self) -> bool:
        return CriticalityInput.DOMINATES_MANY in self.criticality_inputs


@dataclass(frozen=True, slots=True)
class Topology:
    """A built graph and everything derived from it."""

    nodes: Mapping[str, TopologyNode]
    edges: tuple[InferredEdge, ...]
    cycles: tuple[tuple[str, ...], ...]
    entry_points: tuple[str, ...]
    unnamed_caller_counts: Mapping[str, int] = field(default_factory=dict)

    def node(self, service: str) -> TopologyNode | None:
        return self.nodes.get(service)

    @property
    def single_points_of_failure(self) -> tuple[TopologyNode, ...]:
        return tuple(
            node for _, node in sorted(self.nodes.items()) if node.is_single_point_of_failure
        )


def _successors(edges: Sequence[InferredEdge], *, hard_only: bool = False) -> dict[str, list[str]]:
    graph: dict[str, list[str]] = {}
    for edge in edges:
        if hard_only and edge.kind is TopologyEdgeKind.ASYNC_MESSAGE:
            continue
        graph.setdefault(edge.caller_service, []).append(edge.callee_service)
        graph.setdefault(edge.callee_service, [])
    return {node: sorted(set(targets)) for node, targets in graph.items()}


def find_cycles(edges: Sequence[InferredEdge]) -> tuple[tuple[str, ...], ...]:
    """Strongly connected components with more than one member.

    Cycles are reported rather than broken. A dependency cycle between
    three services is a real architectural fact, and an engine that
    quietly picks an ordering hides it.
    """
    successors = _successors(edges)
    index_of: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[tuple[str, ...]] = []
    counter = 0

    def connect(node: str) -> None:
        nonlocal counter
        index_of[node] = low[node] = counter
        counter += 1
        stack.append(node)
        on_stack.add(node)
        for target in successors.get(node, []):
            if target not in index_of:
                connect(target)
                low[node] = min(low[node], low[target])
            elif target in on_stack:
                low[node] = min(low[node], index_of[target])
        if low[node] == index_of[node]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1:
                components.append(tuple(sorted(component)))

    for node in sorted(successors):
        if node not in index_of:
            connect(node)
    return tuple(sorted(components))


def dominators(
    edges: Sequence[InferredEdge], entry: str, *, hard_only: bool = True
) -> Mapping[str, frozenset[str]]:
    """Which nodes every path from ``entry`` must pass through.

    Iterative dataflow to a fixed point. Async edges are excluded by
    default: a consumer being unreachable does not make its producer
    unreachable, so including them would claim dominance the failure
    semantics do not support.
    """
    successors = _successors(edges, hard_only=hard_only)
    nodes = sorted(successors)
    if entry not in successors:
        return {}

    predecessors: dict[str, set[str]] = {node: set() for node in nodes}
    for node, targets in successors.items():
        for target in targets:
            predecessors[target].add(node)

    everything = frozenset(nodes)
    result: dict[str, frozenset[str]] = {
        node: everything if node != entry else frozenset({entry}) for node in nodes
    }

    changed = True
    while changed:
        changed = False
        for node in nodes:
            if node == entry:
                continue
            incoming = [result[p] for p in sorted(predecessors[node]) if p in result]
            if not incoming:
                new = frozenset({node})
            else:
                intersection = incoming[0]
                for other in incoming[1:]:
                    intersection = intersection & other
                new = intersection | {node}
            if new != result[node]:
                result[node] = new
                changed = True

    return dict(sorted(result.items()))


def build_topology(
    edges: Sequence[InferredEdge],
    *,
    missing_links: Sequence[MissingLinkObservation] = (),
    entry_points: Sequence[str] = (),
    dominates_many_at: int = 3,
    min_confidence: ConfidenceBand = ConfidenceBand.WEAK,
) -> Topology:
    """Assemble a topology, naming why each node is critical.

    ``missing_links`` become an ``unnamed_callers`` count on the callee.
    A service with unnamed callers has a fan-in that is a lower bound,
    and saying so is the difference between "two dependents" and "two
    dependents that we can see".
    """
    bands = {ConfidenceBand.WEAK: 0, ConfidenceBand.LIKELY: 1, ConfidenceBand.PROVEN: 2}
    kept = tuple(edge for edge in edges if bands[edge.confidence.band] >= bands[min_confidence])

    unnamed: dict[str, int] = {}
    for link in missing_links:
        unnamed[link.callee_service] = unnamed.get(link.callee_service, 0) + 1

    services = sorted(
        {edge.caller_service for edge in kept}
        | {edge.callee_service for edge in kept}
        | set(unnamed)
    )
    fan_in = dict.fromkeys(services, 0)
    fan_out = dict.fromkeys(services, 0)
    for edge in kept:
        fan_out[edge.caller_service] += 1
        fan_in[edge.callee_service] += 1

    cycles = find_cycles(kept)
    in_cycle = {service for cycle in cycles for service in cycle}

    roots = tuple(entry_points) or tuple(service for service in services if fan_in[service] == 0)
    dominated: dict[str, set[str]] = {service: set() for service in services}
    for root in roots:
        for node, doms in dominators(kept, root).items():
            for dominator in doms:
                if dominator != node:
                    dominated[dominator].add(node)

    nodes: dict[str, TopologyNode] = {}
    for service in services:
        inputs: list[CriticalityInput] = []
        if len(dominated[service]) >= dominates_many_at:
            inputs.append(CriticalityInput.DOMINATES_MANY)
        if fan_in[service] >= dominates_many_at:
            inputs.append(CriticalityInput.HIGH_FAN_IN)
        if service in in_cycle:
            inputs.append(CriticalityInput.IN_CYCLE)
        if unnamed.get(service):
            inputs.append(CriticalityInput.UNOBSERVED_DEPENDENTS)
        nodes[service] = TopologyNode(
            service=service,
            fan_in=fan_in[service],
            fan_out=fan_out[service],
            in_cycle=service in in_cycle,
            dominates=tuple(sorted(dominated[service])),
            unnamed_callers=unnamed.get(service, 0),
            criticality_inputs=tuple(inputs),
        )

    return Topology(
        nodes=nodes,
        edges=kept,
        cycles=cycles,
        entry_points=roots,
        unnamed_caller_counts=dict(sorted(unnamed.items())),
    )


@dataclass(frozen=True, slots=True)
class SpanTiming:
    """A span's own contribution, separated from its children's."""

    span_id: str
    service: str
    operation: str
    duration_ns: int
    self_time_ns: int
    child_blocking_ns: int


def self_times(spans: Sequence[SpanRecord]) -> tuple[SpanTiming, ...]:
    """Each span's duration minus the time it spent blocked on children.

    Child intervals are *merged* before subtracting. Summing them instead
    double-counts concurrent children and can make self time negative --
    which then either gets clamped to zero, hiding the real cost, or
    propagates as a negative into the totals.
    """
    children: dict[str, list[SpanRecord]] = {}
    for span in spans:
        if span.parent_span_id:
            children.setdefault(span.parent_span_id, []).append(span)

    timings: list[SpanTiming] = []
    for span in sorted(spans, key=lambda item: (item.start_ns, item.span_id)):
        intervals = sorted(
            (child.start_ns, child.end_ns)
            for child in children.get(span.span_id, [])
            # Async children do not block the parent.
            if child.kind is not SpanKindLabel.CONSUMER
        )
        merged: list[list[int]] = []
        for start, end in intervals:
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        blocking = sum(end - start for start, end in merged)
        timings.append(
            SpanTiming(
                span_id=span.span_id,
                service=span.service,
                operation=span.operation,
                duration_ns=span.duration_ns,
                self_time_ns=max(0, span.duration_ns - blocking),
                child_blocking_ns=blocking,
            )
        )
    return tuple(timings)


@dataclass(frozen=True, slots=True)
class CriticalPath:
    """The chain of spans that actually determined the total duration."""

    chain: tuple[SpanTiming, ...]
    total_ns: int
    dominant: SpanTiming | None
    dominant_share: float | None


def critical_path(spans: Sequence[SpanRecord]) -> CriticalPath | None:
    """Walk the blocking chain from the root.

    At each step the child that finishes last is the one the parent waited
    for; that is the span on the critical path. Choosing the *longest*
    child instead is wrong whenever a long child ran early and in parallel
    with the one that actually held the parent open.
    """
    if not spans:
        return None
    by_id = {span.span_id: span for span in spans}
    children: dict[str, list[SpanRecord]] = {}
    for span in spans:
        if span.parent_span_id and span.parent_span_id in by_id:
            children.setdefault(span.parent_span_id, []).append(span)

    roots = [span for span in spans if not span.parent_span_id or span.parent_span_id not in by_id]
    if not roots:
        return None
    root = min(roots, key=lambda item: (item.start_ns, item.span_id))

    timings = {timing.span_id: timing for timing in self_times(spans)}
    chain: list[SpanTiming] = []
    current: SpanRecord | None = root
    while current is not None:
        chain.append(timings[current.span_id])
        blocking = [
            child
            for child in children.get(current.span_id, [])
            if child.kind is not SpanKindLabel.CONSUMER
        ]
        current = max(blocking, key=lambda item: (item.end_ns, item.span_id)) if blocking else None

    total = root.duration_ns
    dominant = max(chain, key=lambda item: (item.self_time_ns, item.span_id))
    return CriticalPath(
        chain=tuple(chain),
        total_ns=total,
        dominant=dominant,
        dominant_share=dominant.self_time_ns / total if total > 0 else None,
    )


__all__ = [
    "CriticalPath",
    "SpanTiming",
    "Topology",
    "TopologyNode",
    "build_topology",
    "critical_path",
    "dominators",
    "find_cycles",
    "self_times",
]
