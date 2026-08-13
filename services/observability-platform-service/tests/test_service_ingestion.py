"""Integration tests for app.services.ingestion.IngestionService against
the real database -- exercises 7 repositories and 3 domain events."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.pipeline import IngestionLimits
from app.models.enums import (
    EventKind,
    IngestionStatus,
    MetricType,
    ProfileKind,
    SpanKind,
    SpanStatus,
)
from app.services.ingestion import (
    IngestionService,
    RawEvent,
    RawLogLine,
    RawMetricSample,
    RawProfile,
    RawSpan,
    span_dedupe_key,
)
from tests.conftest import RecordingPublisher

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _limits(**overrides: object) -> IngestionLimits:
    from datetime import timedelta

    defaults: dict[str, object] = {
        "max_batch_size": 1000,
        "max_label_count": 64,
        "max_label_value_length": 1024,
        "max_message_length": 64_000,
        "clock_skew_tolerance": timedelta(minutes=5),
        "max_age": timedelta(days=30),
    }
    defaults.update(overrides)
    return IngestionLimits(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def ingestion(
    db_session: AsyncSession, organization_id: UUID, publisher: RecordingPublisher
) -> IngestionService:
    return IngestionService(
        db_session, organization_id=organization_id, limits=_limits(), publish=publisher
    )


class TestIngestMetrics:
    async def test_creates_series_and_metric_on_first_sample(
        self, ingestion: IngestionService, publisher: RecordingPublisher
    ) -> None:
        sample = RawMetricSample(
            dedupe_key="m1",
            name="http_requests",
            metric_type=MetricType.COUNTER,
            value=1.0,
            occurred_at=NOW,
            labels={"route": "/health"},
        )
        result = await ingestion.ingest_metrics([sample], now=NOW)
        assert result.status is IngestionStatus.ACCEPTED
        assert result.accepted_count == 1
        assert "MetricCollectedEvent" in publisher.names() or len(publisher.events) == 1

    async def test_reuses_series_for_matching_labels(
        self, ingestion: IngestionService, publisher: RecordingPublisher
    ) -> None:
        first = RawMetricSample(
            dedupe_key="m1",
            name="cpu_usage",
            metric_type=MetricType.GAUGE,
            value=50.0,
            occurred_at=NOW,
            labels={"host": "a"},
        )
        second = RawMetricSample(
            dedupe_key="m2",
            name="cpu_usage",
            metric_type=MetricType.GAUGE,
            value=60.0,
            occurred_at=NOW,
            labels={"host": "a"},
        )
        result = await ingestion.ingest_metrics([first, second], now=NOW)
        assert result.accepted_count == 2
        # One series created and reused for both samples => one collection event.
        assert len(publisher.events) == 1

    async def test_different_labels_create_different_series(
        self, ingestion: IngestionService
    ) -> None:
        a = RawMetricSample(
            dedupe_key="a",
            name="cpu_usage",
            metric_type=MetricType.GAUGE,
            value=50.0,
            occurred_at=NOW,
            labels={"host": "a"},
        )
        b = RawMetricSample(
            dedupe_key="b",
            name="cpu_usage",
            metric_type=MetricType.GAUGE,
            value=60.0,
            occurred_at=NOW,
            labels={"host": "b"},
        )
        result = await ingestion.ingest_metrics([a, b], now=NOW)
        assert result.accepted_count == 2

    async def test_rejected_sample_produces_no_series(self, ingestion: IngestionService) -> None:
        from datetime import timedelta

        old_sample = RawMetricSample(
            dedupe_key="old",
            name="ancient_metric",
            metric_type=MetricType.GAUGE,
            value=1.0,
            occurred_at=NOW - timedelta(days=365),
        )
        result = await ingestion.ingest_metrics([old_sample], now=NOW)
        assert result.status is IngestionStatus.REJECTED
        assert result.accepted_count == 0


class TestIngestLogs:
    async def test_persists_accepted_lines(
        self, ingestion: IngestionService, publisher: RecordingPublisher
    ) -> None:
        line = RawLogLine(dedupe_key="l1", message="request failed", occurred_at=NOW)
        result = await ingestion.ingest_logs([line], now=NOW)
        assert result.accepted_count == 1
        assert len(publisher.events) == 1

    async def test_empty_batch_publishes_nothing(
        self, ingestion: IngestionService, publisher: RecordingPublisher
    ) -> None:
        result = await ingestion.ingest_logs([], now=NOW)
        assert result.accepted_count == 0
        assert publisher.events == []


class TestIngestSpans:
    async def test_root_span_completes_session(
        self, ingestion: IngestionService, publisher: RecordingPublisher
    ) -> None:
        trace_id = "trace-1"
        root = RawSpan(
            dedupe_key=span_dedupe_key(trace_id, "root"),
            trace_id=trace_id,
            span_id="root",
            name="handle-request",
            started_at=NOW,
            ended_at=NOW,
            duration_ms=100.0,
            occurred_at=NOW,
            service_name="gateway",
            parent_span_id=None,
            span_kind=SpanKind.SERVER,
            status=SpanStatus.OK,
        )
        result = await ingestion.ingest_spans([root], now=NOW)
        assert result.accepted_count == 1
        trace_completed = [e for e in publisher.events if e.event_name.lower().startswith("trace")]
        assert len(trace_completed) == 1

    async def test_non_root_span_does_not_complete_session(
        self, ingestion: IngestionService, publisher: RecordingPublisher
    ) -> None:
        trace_id = "trace-2"
        child = RawSpan(
            dedupe_key=span_dedupe_key(trace_id, "child"),
            trace_id=trace_id,
            span_id="child",
            name="db-query",
            started_at=NOW,
            ended_at=NOW,
            duration_ms=10.0,
            occurred_at=NOW,
            service_name="backend",
            parent_span_id="root",
            span_kind=SpanKind.INTERNAL,
            status=SpanStatus.OK,
        )
        await ingestion.ingest_spans([child], now=NOW)
        trace_completed = [e for e in publisher.events if e.event_name.lower().startswith("trace")]
        assert trace_completed == []

    async def test_root_span_only_completes_once(
        self, ingestion: IngestionService, publisher: RecordingPublisher
    ) -> None:
        trace_id = "trace-3"
        root = RawSpan(
            dedupe_key=span_dedupe_key(trace_id, "root"),
            trace_id=trace_id,
            span_id="root",
            name="handle-request",
            started_at=NOW,
            ended_at=NOW,
            duration_ms=100.0,
            occurred_at=NOW,
            service_name="gateway",
            parent_span_id=None,
        )
        await ingestion.ingest_spans([root], now=NOW)
        # A second batch touching the same (already-complete) trace with a
        # different span must not republish TraceCompletedEvent.
        other = RawSpan(
            dedupe_key=span_dedupe_key(trace_id, "other"),
            trace_id=trace_id,
            span_id="other",
            name="retry",
            started_at=NOW,
            ended_at=NOW,
            duration_ms=5.0,
            occurred_at=NOW,
            service_name="gateway",
            parent_span_id="root",
        )
        await ingestion.ingest_spans([other], now=NOW)
        trace_completed = [e for e in publisher.events if e.event_name.lower().startswith("trace")]
        assert len(trace_completed) == 1

    async def test_error_span_marks_session_has_error(
        self, ingestion: IngestionService, repos
    ) -> None:
        trace_id = "trace-4"
        root = RawSpan(
            dedupe_key=span_dedupe_key(trace_id, "root"),
            trace_id=trace_id,
            span_id="root",
            name="handle-request",
            started_at=NOW,
            ended_at=NOW,
            duration_ms=100.0,
            occurred_at=NOW,
            service_name="gateway",
            parent_span_id=None,
            status=SpanStatus.ERROR,
        )
        await ingestion.ingest_spans([root], now=NOW)
        session = await repos.trace_sessions.find_by_trace_id(ingestion._organization_id, trace_id)
        assert session is not None
        assert session.has_error


class TestIngestEvents:
    async def test_persists_accepted_events(self, ingestion: IngestionService) -> None:
        event = RawEvent(
            dedupe_key="e1", event_kind=EventKind.DEPLOYMENT, title="deploy v2", occurred_at=NOW
        )
        result = await ingestion.ingest_events([event], now=NOW)
        assert result.accepted_count == 1


class TestIngestProfiles:
    async def test_persists_accepted_profiles(self, ingestion: IngestionService) -> None:
        profile = RawProfile(
            dedupe_key="p1", profile_kind=ProfileKind.CPU, service_name="backend", captured_at=NOW
        )
        result = await ingestion.ingest_profiles([profile], now=NOW)
        assert result.accepted_count == 1
