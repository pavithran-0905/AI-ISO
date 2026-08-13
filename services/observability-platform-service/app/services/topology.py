"""Topology service: infers edges from spans with ``app.topology.edges``,
builds the graph with ``app.topology.graph``, and persists both the
edges (as :class:`ServiceDependency`) and the nodes (as
:class:`ServiceTopologyNode`) -- upserting rather than replacing, so an
edge's history survives the next sweep that happens not to observe it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.models.analysis import ServiceDependency, ServiceTopologyNode
from app.models.enums import NodeHealth
from app.repositories.analysis import ServiceDependencyRepository, ServiceTopologyNodeRepository
from app.topology.edges import (
    EdgeInferenceResult,
    InferredEdge,
    SpanRecord,
    aggregate_edges,
    infer_edges,
)
from app.topology.enums import ConfidenceBand
from app.topology.graph import Topology, TopologyNode, build_topology


class TopologyService:
    """Infers, persists, and upserts one environment's service topology."""

    def __init__(
        self,
        dependency_repo: ServiceDependencyRepository,
        node_repo: ServiceTopologyNodeRepository,
    ) -> None:
        self._dependency_repo = dependency_repo
        self._node_repo = node_repo

    async def sweep(
        self,
        organization_id: UUID,
        *,
        environment: str,
        spans: Sequence[SpanRecord],
        window_seconds: float,
        sampling_ratio: float | None,
        observed_at: datetime,
        min_confidence: ConfidenceBand = ConfidenceBand.WEAK,
    ) -> tuple[EdgeInferenceResult, Topology]:
        """Infer edges from *spans* and persist the resulting graph.

        Returns the raw inference result alongside the built
        :class:`Topology` so a caller can report ``missing_links`` and
        ``orphan_spans`` without a second pass over the spans.
        """
        inference = infer_edges(spans)
        edges = aggregate_edges(
            inference.observations,
            window_seconds=window_seconds,
            sampling_ratio=sampling_ratio,
        )
        topology = build_topology(
            edges,
            missing_links=inference.missing_links,
            min_confidence=min_confidence,
        )

        for edge in edges:
            await self._upsert_dependency(organization_id, environment, edge, observed_at)
        for node in topology.nodes.values():
            await self._upsert_node(organization_id, environment, node, observed_at)

        return inference, topology

    async def _upsert_dependency(
        self,
        organization_id: UUID,
        environment: str,
        edge: InferredEdge,
        observed_at: datetime,
    ) -> ServiceDependency:
        existing = await self._dependency_repo.find_edge(
            organization_id, edge.caller_service, edge.callee_service, environment
        )
        call_count = edge.volume.call_count or 0
        error_count = edge.volume.error_count or 0
        if existing is None:
            return await self._dependency_repo.create(
                ServiceDependency(
                    organization_id=organization_id,
                    caller_service=edge.caller_service,
                    callee_service=edge.callee_service,
                    environment=environment,
                    call_count=call_count,
                    error_count=error_count,
                    first_observed_at=observed_at,
                    last_observed_at=observed_at,
                    error_rate=edge.volume.error_ratio,
                    confidence=edge.confidence.value,
                    is_stale=False,
                )
            )
        # Volume accumulates across sweeps; existence confidence does not --
        # it is recomputed fresh from this sweep's own evidence, because a
        # sweep that saw no evidence this time should not keep inheriting
        # yesterday's certainty forever while itself contributing nothing.
        existing.call_count += call_count
        existing.error_count += error_count
        existing.last_observed_at = max(existing.last_observed_at, observed_at)
        existing.error_rate = edge.volume.error_ratio
        existing.confidence = edge.confidence.value
        existing.is_stale = False
        await self._dependency_repo.update(existing)
        return existing

    async def _upsert_node(
        self,
        organization_id: UUID,
        environment: str,
        node: TopologyNode,
        observed_at: datetime,
    ) -> ServiceTopologyNode:
        existing = await self._node_repo.find_node(organization_id, node.service, environment)
        health = self._health_for(node)
        if existing is None:
            return await self._node_repo.create(
                ServiceTopologyNode(
                    organization_id=organization_id,
                    service_name=node.service,
                    environment=environment,
                    health=health,
                    fan_in=node.fan_in,
                    fan_out=node.fan_out,
                    criticality=float(len(node.dominates)),
                    criticality_inputs={str(item): 1.0 for item in node.criticality_inputs},
                    first_seen_at=observed_at,
                    last_seen_at=observed_at,
                    in_cycle=node.in_cycle,
                )
            )
        existing.health = health
        existing.fan_in = node.fan_in
        existing.fan_out = node.fan_out
        existing.criticality = float(len(node.dominates))
        existing.criticality_inputs = {str(item): 1.0 for item in node.criticality_inputs}
        existing.last_seen_at = max(existing.last_seen_at, observed_at)
        existing.in_cycle = node.in_cycle
        await self._node_repo.update(existing)
        return existing

    @staticmethod
    def _health_for(node: TopologyNode) -> NodeHealth:
        if node.unnamed_callers:
            return NodeHealth.UNKNOWN
        return NodeHealth.HEALTHY


__all__ = ["TopologyService"]
