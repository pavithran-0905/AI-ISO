"""Root cause analysis service: assembles per-candidate evidence
(correlation, timing, graph position) and runs it through
``app.root_cause.engine.analyse``, then persists exactly one
:class:`RootCauseReport` per incident -- inconclusive results included.

**Which services are candidates is the caller's decision, not this
module's.** Picking candidates is a topology-neighborhood query
(dependencies within N hops of the symptomatic service, say), and baking
that policy into the analysis engine would make the same evidence produce
a different ranking depending on how the neighborhood was walked. This
service accepts a pre-built candidate pool and assembles the evidence for
exactly those services.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import UUID

from app.events.domain_events import RootCauseCompletedEvent
from app.models.analysis import RootCauseReport
from app.models.enums import CauseConfidence
from app.repositories.analysis import RootCauseReportRepository
from app.root_cause.correlation import Series, correlate, jaccard
from app.root_cause.engine import (
    Candidate,
    Graph,
    analyse,
    blast_radius,
    walk,
)
from app.root_cause.enums import Direction, EvidenceTier, PathQuality
from app.root_cause.timeline import Signal, build_timeline, find_onset
from app.types import EventPublisher

_SOURCE_SERVICE = "observability-platform-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


_CONFIDENCE_BY_TIER: Mapping[EvidenceTier, CauseConfidence] = {
    EvidenceTier.MECHANISM_AND_TIMING: CauseConfidence.STRONG,
    EvidenceTier.TIMING_ONLY: CauseConfidence.MODERATE,
    EvidenceTier.MECHANISM_ONLY: CauseConfidence.MODERATE,
    EvidenceTier.COINCIDENT: CauseConfidence.WEAK,
    EvidenceTier.INSUFFICIENT_EVIDENCE: CauseConfidence.INDISTINGUISHABLE,
}
"""The engine's tiers are ordinal evidence classes; the stored column is a
coarser four-value confidence. Both directions agree that mechanism beats
timing beats coincidence -- this table only ever collapses adjacent
tiers, never reorders them."""


def _build_candidate(
    service_name: str,
    *,
    series: Series,
    symptom: Series,
    onsets: Mapping[str, object],
    symptom_onset_at: datetime | None,
    graph: Graph,
    symptom_service: str,
) -> Candidate:
    result = correlate(series, symptom)
    overlap, _ = jaccard(series.active_buckets, symptom.active_buckets)

    onset = onsets.get(service_name)
    precedes = False
    if onset is not None and getattr(onset, "at", None) and symptom_onset_at:
        precedes = onset.at <= symptom_onset_at  # type: ignore[attr-defined]

    forward = walk(graph, service_name, Direction.UPSTREAM)
    path_quality: PathQuality | None = None
    depth: int | None = None
    if symptom_service in forward.reached:
        path_quality = forward.quality_by_service[symptom_service]
        depth = forward.depth_by_service[symptom_service]

    return Candidate(
        service=service_name,
        tier=EvidenceTier.INSUFFICIENT_EVIDENCE,  # replaced by classify_tier inside analyse()
        correlation=result,
        activity_jaccard=overlap,
        specificity=None,
        precedes_symptom=precedes,
        graph_path=path_quality,
        graph_depth=depth,
        in_cycle_with_symptom=False,
        lag_within_budget=True if path_quality else None,
        change_nearby=False,
    )


class RootCauseAnalysisService:
    """Assembles evidence for a candidate pool and persists the finding."""

    def __init__(
        self, repo: RootCauseReportRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def analyse_incident(
        self,
        organization_id: UUID,
        *,
        symptom_service: str,
        environment: str | None,
        incident_reference: str | None,
        incident_started_at: datetime,
        incident_detected_at: datetime | None,
        symptom_series: Series,
        symptom_signals: Sequence[Signal],
        candidate_series: Mapping[str, Series],
        candidate_signals: Mapping[str, Sequence[Signal]],
        graph: Graph,
        window_start: datetime,
        window_end: datetime,
        analysed_at: datetime,
    ) -> RootCauseReport:
        symptom_onset = find_onset(symptom_signals, window_start=window_start)
        onsets = {
            service: find_onset(signals, window_start=window_start)
            for service, signals in candidate_signals.items()
        }
        timeline = build_timeline(
            [o for o in [symptom_onset, *onsets.values()] if o is not None],
            window_start=window_start,
            window_end=window_end,
        )

        candidates = [
            _build_candidate(
                service,
                series=series,
                symptom=symptom_series,
                onsets=onsets,
                symptom_onset_at=symptom_onset.at if symptom_onset else None,
                graph=graph,
                symptom_service=symptom_service,
            )
            for service, series in candidate_series.items()
            if service != symptom_service
        ]
        radius = blast_radius(
            graph,
            symptom_service,
            symptomatic=list(candidate_series),
            instrumented=[*candidate_series, symptom_service],
        )

        result = analyse(
            candidates,
            timeline=timeline,
            blast=radius,
            graph=graph,
            comparisons_made=len(candidates),
            excluded_service=symptom_service,
        )

        top = result.ranked[0] if result.ranked else None
        report = await self._repo.create(
            RootCauseReport(
                organization_id=organization_id,
                service_name=symptom_service,
                environment=environment,
                incident_reference=incident_reference,
                analysed_at=analysed_at,
                incident_started_at=incident_started_at,
                incident_detected_at=incident_detected_at,
                confidence=(
                    _CONFIDENCE_BY_TIER[top.candidate.tier]
                    if top is not None
                    else CauseConfidence.INDISTINGUISHABLE
                ),
                candidates=[
                    {
                        "service": entry.candidate.service,
                        "rank": entry.rank,
                        "tier": str(entry.candidate.tier),
                        "distinguishable": entry.distinguishable,
                        "correlation": (
                            entry.candidate.correlation.coefficient
                            if entry.candidate.correlation
                            else None
                        ),
                        "precedes_symptom": entry.candidate.precedes_symptom,
                        "graph_path": (
                            str(entry.candidate.graph_path) if entry.candidate.graph_path else None
                        ),
                    }
                    for entry in result.ranked
                ],
                timeline=[
                    {
                        "group": group.index,
                        "members": [m.service for m in group.members],
                        "distinguishable": group.distinguishable,
                    }
                    for group in (timeline.groups if timeline else ())
                ],
                blast_radius=list(radius.observed_affected) if radius else [],
                affected_service_count=len(radius.observed_affected) if radius else 0,
                recommendations=[rec.would_separate for rec in result.recommendations],
                signals_considered=len(symptom_signals)
                + sum(len(s) for s in candidate_signals.values()),
                is_conclusive=result.is_conclusive,
                summary=(
                    f"{top.candidate.service} ranked first ({top.candidate.tier!s})"
                    if top is not None
                    else "No candidate could be ranked."
                ),
                details={
                    "refusal": str(result.refusal) if result.refusal else None,
                    "expected_false_positives": result.expected_false_positives,
                    "window_provenance": str(result.window_provenance),
                    "common_antecedents": [
                        {"services": list(a.services), "shared": list(a.shared)}
                        for a in result.common_antecedents
                    ],
                    "caveat": result.caveat,
                },
            )
        )
        await self._publish(
            RootCauseCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "report_id": str(report.id),
                    "service_name": symptom_service,
                    "is_conclusive": result.is_conclusive,
                    "top_candidate_service": (top.candidate.service if top is not None else None),
                },
            )
        )
        return report


__all__ = ["RootCauseAnalysisService"]
