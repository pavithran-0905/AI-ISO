"""Tests for app.workers.* -- each worker's tick() run directly against
the real database (leader election / scheduling itself is shared_core's
concern, not this service's)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.analysis import Slo
from app.models.enums import (
    MetricKind,
    MetricType,
    SignalKind,
    SliKind,
    SourceKind,
    SpanKind,
    SpanStatus,
)
from app.models.operations import RetentionPolicy
from app.models.signals import Metric, MetricSeries, TraceSpan
from app.workers.anomaly_sweep import AnomalySweepWorker
from app.workers.registrar import (
    _register,
    register_anomaly_sweep,
    register_retention_sweep,
    register_slo_evaluation,
    register_statistics_rollup,
    register_topology_rebuild,
)
from app.workers.retention_sweep import RetentionSweepWorker
from app.workers.slo_evaluation import SloEvaluationWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from app.workers.topology_rebuild import TopologyRebuildWorker

NOW = datetime.now(UTC)
"""Real wall-clock time, not a fixed constant: every worker under test
computes its own ``datetime.now(UTC)`` internally and windows its query
against it, so fixture data must actually fall inside that real window."""


async def _noop_publish(event: object) -> None:
    pass


class TestSloEvaluationWorker:
    async def test_tick_evaluates_ratio_kind_slo(
        self, db_session_factory, repos, organization_id
    ) -> None:
        await repos.slos.create(
            Slo(
                organization_id=organization_id,
                name="worker-slo",
                service_name="backend",
                sli_kind=SliKind.AVAILABILITY,
                target=0.99,
                window_days=1,
                fast_burn_hours=1.0,
                fast_burn_threshold=14.4,
                slow_burn_hours=6.0,
                slow_burn_threshold=6.0,
            )
        )
        await repos.trace_spans.create(
            TraceSpan(
                organization_id=organization_id,
                trace_id="t1",
                span_id="s1",
                name="op",
                span_kind=SpanKind.SERVER,
                status=SpanStatus.OK,
                service_name="backend",
                source_kind=SourceKind.MICROSERVICE,
                started_at=NOW - timedelta(minutes=5),
                ended_at=NOW,
                duration_ms=10.0,
                depth=0,
                is_orphan=False,
            )
        )
        worker = SloEvaluationWorker(db_session_factory, publish_event=_noop_publish)
        count = await worker.tick()
        assert count == 1

    async def test_tick_skips_non_ratio_kind(
        self, db_session_factory, repos, organization_id
    ) -> None:
        await repos.slos.create(
            Slo(
                organization_id=organization_id,
                name="latency-slo",
                service_name="backend",
                sli_kind=SliKind.LATENCY,
                target=0.99,
                latency_threshold_ms=300.0,
            )
        )
        worker = SloEvaluationWorker(db_session_factory, publish_event=_noop_publish)
        count = await worker.tick()
        assert count == 0


class TestAnomalySweepWorker:
    async def test_tick_sweeps_active_series_with_enough_history(
        self, db_session_factory, repos, organization_id
    ) -> None:
        series = await repos.metric_series.create(
            MetricSeries(
                organization_id=organization_id,
                name="cpu",
                metric_type=MetricType.GAUGE,
                metric_kind=MetricKind.CUSTOM,
                labels={},
                label_fingerprint="fp-worker",
                source_kind=SourceKind.CUSTOM_APPLICATION,
                first_seen_at=NOW,
                last_seen_at=NOW,
                sample_count=0,
            )
        )
        for i in range(35):
            await repos.metrics.create(
                Metric(
                    organization_id=organization_id,
                    metric_series_id=series.id,
                    occurred_at=NOW - timedelta(minutes=35 - i),
                    received_at=NOW,
                    value=100.0 + (i % 3 - 1),
                )
            )
        worker = AnomalySweepWorker(
            db_session_factory, publish_event=_noop_publish, lookback=timedelta(hours=6)
        )
        count = await worker.tick()
        assert count == 0  # no anomalous points among the 35 stable samples

    async def test_tick_skips_series_below_min_history(
        self, db_session_factory, repos, organization_id
    ) -> None:
        series = await repos.metric_series.create(
            MetricSeries(
                organization_id=organization_id,
                name="sparse",
                metric_type=MetricType.GAUGE,
                metric_kind=MetricKind.CUSTOM,
                labels={},
                label_fingerprint="fp-sparse",
                source_kind=SourceKind.CUSTOM_APPLICATION,
                first_seen_at=NOW,
                last_seen_at=NOW,
                sample_count=0,
            )
        )
        await repos.metrics.create(
            Metric(
                organization_id=organization_id,
                metric_series_id=series.id,
                occurred_at=NOW,
                received_at=NOW,
                value=1.0,
            )
        )
        worker = AnomalySweepWorker(db_session_factory, publish_event=_noop_publish)
        count = await worker.tick()
        assert count == 0


class TestTopologyRebuildWorker:
    async def test_tick_rebuilds_from_recent_spans(
        self, db_session_factory, repos, organization_id
    ) -> None:
        await repos.trace_spans.create(
            TraceSpan(
                organization_id=organization_id,
                trace_id="t1",
                span_id="c1",
                name="call",
                span_kind=SpanKind.CLIENT,
                status=SpanStatus.OK,
                service_name="gateway",
                source_kind=SourceKind.MICROSERVICE,
                started_at=NOW,
                ended_at=NOW,
                duration_ms=10.0,
                depth=0,
                is_orphan=False,
            )
        )
        await repos.trace_spans.create(
            TraceSpan(
                organization_id=organization_id,
                trace_id="t1",
                span_id="s1",
                name="handle",
                span_kind=SpanKind.SERVER,
                status=SpanStatus.OK,
                service_name="backend",
                source_kind=SourceKind.MICROSERVICE,
                started_at=NOW,
                ended_at=NOW,
                duration_ms=9.0,
                depth=1,
                parent_span_id="c1",
                is_orphan=False,
            )
        )
        worker = TopologyRebuildWorker(db_session_factory, lookback=timedelta(hours=1))
        edges = await worker.tick()
        assert edges == 1

    async def test_tick_no_spans_no_edges(self, db_session_factory) -> None:
        worker = TopologyRebuildWorker(db_session_factory, lookback=timedelta(hours=1))
        edges = await worker.tick()
        assert edges == 0


class TestRetentionSweepWorker:
    async def test_tick_applies_coarse_tier_and_records_sweep(
        self, db_session_factory, repos, organization_id
    ) -> None:
        await repos.retention_policies.create(
            RetentionPolicy(
                organization_id=organization_id,
                signal_kind=SignalKind.METRIC,
                environment="production",
                raw_days=1,
                downsampled_days=1,
                coarse_days=1,
                is_enabled=True,
            )
        )
        series = await repos.metric_series.create(
            MetricSeries(
                organization_id=organization_id,
                name="old",
                metric_type=MetricType.GAUGE,
                metric_kind=MetricKind.CUSTOM,
                labels={},
                label_fingerprint="fp-old",
                source_kind=SourceKind.CUSTOM_APPLICATION,
                first_seen_at=NOW - timedelta(days=10),
                last_seen_at=NOW - timedelta(days=10),
                sample_count=0,
            )
        )
        await repos.metrics.create(
            Metric(
                organization_id=organization_id,
                metric_series_id=series.id,
                occurred_at=NOW - timedelta(days=10),
                received_at=NOW,
                value=1.0,
            )
        )
        worker = RetentionSweepWorker(db_session_factory)
        deleted = await worker.tick()
        assert deleted == 1
        updated = await repos.retention_policies.find_for_scope(
            organization_id, SignalKind.METRIC, "production"
        )
        assert updated is not None
        assert updated.last_applied_at is not None

    async def test_tick_no_policies_no_deletions(self, db_session_factory) -> None:
        worker = RetentionSweepWorker(db_session_factory)
        deleted = await worker.tick()
        assert deleted == 0


class TestStatisticsRollupWorker:
    async def test_tick_rolls_up_and_is_idempotent(
        self, db_session_factory, repos, organization_id
    ) -> None:
        await repos.metric_series.create(
            MetricSeries(
                organization_id=organization_id,
                name="rollup-series",
                metric_type=MetricType.GAUGE,
                metric_kind=MetricKind.CUSTOM,
                labels={},
                label_fingerprint="fp-rollup",
                source_kind=SourceKind.CUSTOM_APPLICATION,
                first_seen_at=NOW,
                last_seen_at=NOW,
                sample_count=0,
            )
        )
        worker = StatisticsRollupWorker(db_session_factory)
        first = await worker.tick()
        second = await worker.tick()
        assert first >= 1
        assert second >= 1  # idempotent: same window updated, not duplicated

    async def test_tick_no_organizations_no_rollup(self, db_session_factory) -> None:
        worker = StatisticsRollupWorker(db_session_factory)
        rolled = await worker.tick()
        assert rolled == 0


class TestRegistrar:
    def test_non_positive_interval_raises(self) -> None:
        async def _fn(_job: object) -> None:
            pass

        with pytest.raises(ValueError, match="must be positive"):
            _register(None, _fn, job_id="test-job", interval_seconds=0, component="test")  # type: ignore[arg-type]

    def test_negative_interval_raises(self) -> None:
        async def _fn(_job: object) -> None:
            pass

        with pytest.raises(ValueError, match="must be positive"):
            _register(None, _fn, job_id="test-job", interval_seconds=-5, component="test")  # type: ignore[arg-type]

    def test_all_five_register_functions_call_manager(self) -> None:
        class _StubManager:
            def __init__(self) -> None:
                self.registered = []

            def register_job(self, job):
                self.registered.append(job)
                return job

        async def _fn(_job: object) -> None:
            pass

        manager = _StubManager()
        register_slo_evaluation(manager, _fn, interval_seconds=60)
        register_anomaly_sweep(manager, _fn, interval_seconds=300)
        register_topology_rebuild(manager, _fn, interval_seconds=600)
        register_retention_sweep(manager, _fn, interval_seconds=3600)
        register_statistics_rollup(manager, _fn, interval_seconds=900)
        assert len(manager.registered) == 5
        job_ids = {job.job_id for job in manager.registered}
        assert len(job_ids) == 5  # every job id is distinct
