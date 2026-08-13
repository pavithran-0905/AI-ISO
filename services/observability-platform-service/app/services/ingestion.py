"""Ingestion service: wires ``app.ingestion.pipeline``'s pure validation
onto the repositories that actually persist each signal kind.

The pure pipeline (:func:`app.ingestion.pipeline.ingest_batch`) decides
what is valid, clamped, or a duplicate without knowing what a
:class:`MetricSeries` or a :class:`TraceSpan` is. This module is the only
place those two things meet: it turns a validated
:class:`~app.ingestion.pipeline.AcceptedSignal` into the right row (or
rows) in the right table, and nothing here re-implements a decision the
pipeline already made.

**A trace session is derived from its spans, never reported directly.**
No single collector sees a whole trace, so the session row is built
incrementally as spans arrive: extended, not overwritten, and marked
complete only when the specific span with no parent -- the root -- is
seen. A session that looks complete because *some* span merely arrived
without a ``parent_span_id`` recorded on it would be marking traces
complete based on missing data rather than an actual root.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.domain_events import (
    LogIngestedEvent,
    MetricCollectedEvent,
    TraceCompletedEvent,
)
from app.ingestion.pipeline import (
    AcceptedSignal,
    IngestionLimits,
    IngestionResult,
    RawSignal,
    ingest_batch,
)
from app.models.enums import (
    EventKind,
    EventSeverity,
    LogFormat,
    LogLevel,
    MetricKind,
    MetricType,
    ProfileKind,
    SignalKind,
    SourceKind,
    SpanKind,
    SpanStatus,
)
from app.models.signals import (
    LogEntry,
    Metric,
    MetricSeries,
    ObservabilityEvent,
    Profile,
    TraceSession,
    TraceSpan,
)
from app.repositories.signals import (
    LogEntryRepository,
    MetricRepository,
    MetricSeriesRepository,
    ObservabilityEventRepository,
    ProfileRepository,
    TraceSessionRepository,
    TraceSpanRepository,
)
from app.services.labels import fingerprint_labels
from app.types import EventPublisher

_SOURCE_SERVICE = "observability-platform-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher: ingestion works with no messaging backend
    wired up, since a great many callers (a hand-verification script,
    for one) have no queue to publish to and should not be forced to
    provide a fake one just to construct the service."""


@dataclass(frozen=True, slots=True)
class RawMetricSample:
    """One metric point, identifying its series inline.

    The series is found-or-created from these fields; the sample never
    carries a ``metric_series_id`` because the caller cannot know it in
    advance for a series it may be the first to report.
    """

    dedupe_key: str
    name: str
    metric_type: MetricType
    value: float
    occurred_at: datetime
    unit: str | None = None
    metric_kind: MetricKind = MetricKind.CUSTOM
    labels: Mapping[str, str] = field(default_factory=dict)
    service_name: str | None = None
    source_kind: SourceKind = SourceKind.CUSTOM_APPLICATION
    environment: str | None = None
    sample_count: int | None = None
    sum_value: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    buckets: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RawLogLine:
    dedupe_key: str
    message: str
    occurred_at: datetime
    level: LogLevel = LogLevel.INFO
    raw: str | None = None
    log_format: LogFormat = LogFormat.PLAIN
    parse_failed: bool = False
    parse_error: str | None = None
    service_name: str | None = None
    source_kind: SourceKind = SourceKind.CUSTOM_APPLICATION
    environment: str | None = None
    host: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    attributes: Mapping[str, object] = field(default_factory=dict)
    labels: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RawSpan:
    """One span. ``dedupe_key`` is ``trace_id|span_id`` -- see
    :func:`span_dedupe_key`, which every caller must use so the key here
    matches the database's own unique constraint exactly.
    """

    dedupe_key: str
    trace_id: str
    span_id: str
    name: str
    started_at: datetime
    ended_at: datetime
    duration_ms: float
    occurred_at: datetime
    """Equal to ``started_at``. Carried separately because the pipeline's
    clock-skew and max-age gates operate on ``occurred_at`` uniformly
    across every signal kind; a span is the one kind where that name
    would otherwise collide with a more specific concept."""
    service_name: str
    parent_span_id: str | None = None
    span_kind: SpanKind = SpanKind.INTERNAL
    status: SpanStatus = SpanStatus.UNSET
    status_message: str | None = None
    source_kind: SourceKind = SourceKind.MICROSERVICE
    environment: str | None = None
    self_time_ms: float | None = None
    depth: int = 0
    attributes: Mapping[str, object] = field(default_factory=dict)
    events: Sequence[Mapping[str, object]] = ()


@dataclass(frozen=True, slots=True)
class RawEvent:
    dedupe_key: str
    event_kind: EventKind
    title: str
    occurred_at: datetime
    severity: EventSeverity = EventSeverity.INFO
    description: str | None = None
    ended_at: datetime | None = None
    service_name: str | None = None
    source_kind: SourceKind = SourceKind.PLATFORM_SERVICE
    environment: str | None = None
    host: str | None = None
    trace_id: str | None = None
    correlation_id: str | None = None
    external_id: str | None = None
    attributes: Mapping[str, object] = field(default_factory=dict)
    labels: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RawProfile:
    dedupe_key: str
    profile_kind: ProfileKind
    service_name: str
    captured_at: datetime
    duration_ms: float = 0.0
    sample_count: int = 0
    sample_period_ms: float | None = None
    unit: str | None = None
    total_value: float = 0.0
    frames: Sequence[Mapping[str, object]] = ()
    truncated: bool = False
    source_kind: SourceKind = SourceKind.MICROSERVICE
    environment: str | None = None
    host: str | None = None
    attributes: Mapping[str, object] = field(default_factory=dict)


def span_dedupe_key(trace_id: str, span_id: str) -> str:
    """The one place ``trace_id|span_id`` is joined, so ingest-time
    deduplication and the database's unique constraint can never
    disagree on what identifies a span."""
    return f"{trace_id}|{span_id}"


class IngestionService:
    """Validates and persists every signal kind for one organization."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        limits: IngestionLimits,
        tenant_scope: TenantScope | None = None,
        publish: EventPublisher = _noop_publisher,
    ) -> None:
        self._session = session
        self._organization_id = organization_id
        self._limits = limits
        self._publish = publish
        scope = tenant_scope or TenantScope(organization_id=organization_id)
        self._series_repo = MetricSeriesRepository(session, tenant_scope=scope)
        self._metric_repo = MetricRepository(session, tenant_scope=scope)
        self._log_repo = LogEntryRepository(session, tenant_scope=scope)
        self._session_repo = TraceSessionRepository(session, tenant_scope=scope)
        self._span_repo = TraceSpanRepository(session, tenant_scope=scope)
        self._event_repo = ObservabilityEventRepository(session, tenant_scope=scope)
        self._profile_repo = ProfileRepository(session, tenant_scope=scope)

    async def ingest_metrics(
        self, samples: Sequence[RawMetricSample], *, now: datetime
    ) -> IngestionResult:
        """Validate a batch, then find-or-create each sample's series."""
        by_key = {sample.dedupe_key: sample for sample in samples}
        raw = [
            RawSignal(
                dedupe_key=sample.dedupe_key,
                signal_kind=SignalKind.METRIC,
                occurred_at=sample.occurred_at,
                labels=dict(sample.labels),
            )
            for sample in samples
        ]
        result = ingest_batch(raw, self._limits, now=now)

        series_cache: dict[tuple[str, str], MetricSeries] = {}
        accepted_per_series: dict[UUID, int] = {}
        for accepted in result.accepted:
            sample = by_key[accepted.dedupe_key]
            fingerprint = fingerprint_labels(sample.labels)
            cache_key = (sample.name, fingerprint)
            series = series_cache.get(cache_key)
            if series is None:
                series = await self._series_repo.find_by_identity(
                    self._organization_id, sample.name, fingerprint
                )
                if series is None:
                    series = await self._series_repo.create(
                        MetricSeries(
                            organization_id=self._organization_id,
                            name=sample.name,
                            metric_type=sample.metric_type,
                            metric_kind=sample.metric_kind,
                            unit=sample.unit,
                            labels=dict(sample.labels),
                            label_fingerprint=fingerprint,
                            service_name=sample.service_name,
                            source_kind=sample.source_kind,
                            environment=sample.environment,
                            first_seen_at=accepted.occurred_at,
                            last_seen_at=accepted.occurred_at,
                            sample_count=0,
                        )
                    )
                series_cache[cache_key] = series

            series.last_seen_at = max(series.last_seen_at, accepted.occurred_at)
            series.sample_count += 1
            accepted_per_series[series.id] = accepted_per_series.get(series.id, 0) + 1

            await self._metric_repo.create(
                Metric(
                    organization_id=self._organization_id,
                    metric_series_id=series.id,
                    occurred_at=accepted.occurred_at,
                    received_at=accepted.received_at,
                    value=sample.value,
                    sample_count=sample.sample_count,
                    sum_value=sample.sum_value,
                    min_value=sample.min_value,
                    max_value=sample.max_value,
                    buckets=dict(sample.buckets),
                )
            )

        # One event per series touched, not per sample: a batch of a
        # thousand points for one series is one collection event, and
        # publishing a thousand would flood every subscriber for no
        # information a count could not carry.
        for series_key, series in series_cache.items():
            await self._publish(
                MetricCollectedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=self._organization_id,
                    payload={
                        "metric_series_id": str(series.id),
                        "series_name": series_key[0],
                        "accepted_count": accepted_per_series.get(series.id, 0),
                    },
                )
            )
        return result

    async def ingest_logs(self, lines: Sequence[RawLogLine], *, now: datetime) -> IngestionResult:
        by_key = {line.dedupe_key: line for line in lines}
        raw = [
            RawSignal(
                dedupe_key=line.dedupe_key,
                signal_kind=SignalKind.LOG,
                occurred_at=line.occurred_at,
                labels=dict(line.labels),
                message=line.message,
            )
            for line in lines
        ]
        result = ingest_batch(raw, self._limits, now=now)
        for accepted in result.accepted:
            line = by_key[accepted.dedupe_key]
            await self._log_repo.create(
                LogEntry(
                    organization_id=self._organization_id,
                    occurred_at=accepted.occurred_at,
                    received_at=accepted.received_at,
                    level=line.level,
                    message=line.message,
                    raw=line.raw,
                    log_format=line.log_format,
                    parse_failed=line.parse_failed,
                    parse_error=line.parse_error,
                    service_name=line.service_name,
                    source_kind=line.source_kind,
                    environment=line.environment,
                    host=line.host,
                    trace_id=line.trace_id,
                    span_id=line.span_id,
                    attributes=dict(line.attributes),
                    labels=dict(line.labels),
                )
            )
        if lines:
            parse_failed = sum(1 for line in lines if line.parse_failed)
            await self._publish(
                LogIngestedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=self._organization_id,
                    payload={
                        "accepted_count": result.accepted_count,
                        "parse_failed_count": parse_failed,
                    },
                )
            )
        return result

    async def ingest_spans(self, spans: Sequence[RawSpan], *, now: datetime) -> IngestionResult:
        """Persist spans and roll each trace's session forward.

        Spans for one trace may arrive in any order and across many
        batches, so the session update is a merge -- extend, never
        overwrite -- keyed on whichever span in *this* batch turns out to
        be the root.
        """
        by_key = {span.dedupe_key: span for span in spans}
        raw = [
            RawSignal(
                dedupe_key=span.dedupe_key,
                signal_kind=SignalKind.TRACE,
                occurred_at=span.occurred_at,
            )
            for span in spans
        ]
        result = ingest_batch(raw, self._limits, now=now)

        by_trace: dict[str, list[AcceptedSignal]] = {}
        for accepted in result.accepted:
            span = by_key[accepted.dedupe_key]
            by_trace.setdefault(span.trace_id, []).append(accepted)
            await self._span_repo.create(
                TraceSpan(
                    organization_id=self._organization_id,
                    trace_id=span.trace_id,
                    span_id=span.span_id,
                    parent_span_id=span.parent_span_id,
                    name=span.name,
                    span_kind=span.span_kind,
                    status=span.status,
                    status_message=span.status_message,
                    service_name=span.service_name,
                    source_kind=span.source_kind,
                    environment=span.environment,
                    started_at=span.started_at,
                    ended_at=span.ended_at,
                    duration_ms=span.duration_ms,
                    self_time_ms=span.self_time_ms,
                    depth=span.depth,
                    is_orphan=False,
                    attributes=dict(span.attributes),
                    events=list(span.events),
                )
            )

        for trace_id, accepted_for_trace in by_trace.items():
            trace_spans = [by_key[a.dedupe_key] for a in accepted_for_trace]
            await self._merge_session(trace_id, trace_spans)
        return result

    async def _merge_session(self, trace_id: str, spans: Sequence[RawSpan]) -> None:
        session = await self._session_repo.find_by_trace_id(self._organization_id, trace_id)
        root = next((span for span in spans if span.parent_span_id is None), None)
        earliest = min(span.started_at for span in spans)
        error_count = sum(1 for span in spans if span.status is SpanStatus.ERROR)
        services = {span.service_name for span in spans}

        if session is None:
            # Every field the merge below reads or compares against must be
            # set here explicitly: a column's declared `default=` is applied
            # by SQLAlchemy at flush/INSERT time, not on construction, so an
            # unset field is still None right up until the merge tries to
            # max() or or() against it.
            session = TraceSession(
                organization_id=self._organization_id,
                trace_id=trace_id,
                started_at=earliest,
                span_count=0,
                error_span_count=0,
                service_count=0,
                max_depth=0,
                has_error=False,
                is_complete=False,
                orphan_span_count=0,
                services=[],
            )
            self._session.add(session)

        was_complete = session.is_complete
        session.started_at = min(session.started_at, earliest)
        session.span_count += len(spans)
        session.error_span_count += error_count
        session.services = sorted(set(session.services) | services)
        session.service_count = len(session.services)
        session.has_error = session.has_error or error_count > 0
        session.max_depth = max([session.max_depth, *(span.depth for span in spans)])

        if root is not None and not session.is_complete:
            # The specific span with no parent is what marks completeness --
            # not merely "some span arrived" -- so a trace missing its root
            # forever correctly stays incomplete forever.
            session.root_span_id = root.span_id
            session.root_service_name = root.service_name
            session.root_operation = root.name
            session.ended_at = root.ended_at
            session.duration_ms = root.duration_ms
            session.is_complete = True

        await self._session.flush()

        if not was_complete and session.is_complete:
            # Published once, at the False -> True transition, from the
            # now-final counts. Without the was_complete guard, every later
            # batch that happens to include the root span's trace_id (a
            # retried delivery, say) would republish the same completion.
            await self._publish(
                TraceCompletedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=self._organization_id,
                    payload={
                        "trace_id": trace_id,
                        "root_service_name": session.root_service_name,
                        "span_count": session.span_count,
                        "has_error": session.has_error,
                        "duration_ms": session.duration_ms,
                    },
                )
            )

    async def ingest_events(self, events: Sequence[RawEvent], *, now: datetime) -> IngestionResult:
        by_key = {event.dedupe_key: event for event in events}
        raw = [
            RawSignal(
                dedupe_key=event.dedupe_key,
                signal_kind=SignalKind.EVENT,
                occurred_at=event.occurred_at,
                labels=dict(event.labels),
            )
            for event in events
        ]
        result = ingest_batch(raw, self._limits, now=now)
        for accepted in result.accepted:
            event = by_key[accepted.dedupe_key]
            await self._event_repo.create(
                ObservabilityEvent(
                    organization_id=self._organization_id,
                    event_kind=event.event_kind,
                    severity=event.severity,
                    title=event.title,
                    description=event.description,
                    occurred_at=accepted.occurred_at,
                    received_at=accepted.received_at,
                    ended_at=event.ended_at,
                    service_name=event.service_name,
                    source_kind=event.source_kind,
                    environment=event.environment,
                    host=event.host,
                    trace_id=event.trace_id,
                    correlation_id=event.correlation_id,
                    external_id=event.external_id,
                    attributes=dict(event.attributes),
                    labels=dict(event.labels),
                )
            )
        return result

    async def ingest_profiles(
        self, profiles: Sequence[RawProfile], *, now: datetime
    ) -> IngestionResult:
        by_key = {profile.dedupe_key: profile for profile in profiles}
        raw = [
            RawSignal(
                dedupe_key=profile.dedupe_key,
                signal_kind=SignalKind.PROFILE,
                occurred_at=profile.captured_at,
            )
            for profile in profiles
        ]
        result = ingest_batch(raw, self._limits, now=now)
        for accepted in result.accepted:
            profile = by_key[accepted.dedupe_key]
            await self._profile_repo.create(
                Profile(
                    organization_id=self._organization_id,
                    profile_kind=profile.profile_kind,
                    service_name=profile.service_name,
                    source_kind=profile.source_kind,
                    environment=profile.environment,
                    host=profile.host,
                    captured_at=accepted.occurred_at,
                    duration_ms=profile.duration_ms,
                    sample_count=profile.sample_count,
                    sample_period_ms=profile.sample_period_ms,
                    unit=profile.unit,
                    total_value=profile.total_value,
                    frames=list(profile.frames),
                    truncated=profile.truncated,
                    attributes=dict(profile.attributes),
                )
            )
        return result


__all__ = [
    "IngestionService",
    "RawEvent",
    "RawLogLine",
    "RawMetricSample",
    "RawProfile",
    "RawSpan",
    "span_dedupe_key",
]
