"""Integration tests for the SLO, anomaly, capacity, cost, root-cause,
topology, retention, and search services against the real database.

Each test exercises a service through its repository into real Postgres,
so this file also covers most of app.repositories.analysis/operations.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.anomaly.engine import Point
from app.capacity.enums import ReductionKind
from app.cost.enums import MeterBasis
from app.cost.rates import Rate, RateCard, RateCardSet
from app.cost.usage import UsageRecord
from app.models.analysis import Slo
from app.models.enums import (
    CostCategory,
    SignalKind,
    SliKind,
)
from app.models.operations import RetentionPolicy
from app.root_cause.correlation import Series
from app.root_cause.engine import Edge, Graph
from app.root_cause.enums import EdgeKind
from app.root_cause.timeline import Signal as RcSignal
from app.search.query import QueryLimits, SearchRequest, TimeRange
from app.services.anomaly import AnomalyDetectionService
from app.services.capacity import CapacityForecastService
from app.services.cost import CostReportingService
from app.services.retention import RetentionService
from app.services.root_cause import RootCauseAnalysisService
from app.services.search import SearchService
from app.services.slo import SloEvaluationService
from app.services.topology import TopologyService
from app.slo.engine import RatioWindow
from app.topology.edges import SpanRecord
from app.topology.enums import SpanKindLabel

NOW = datetime(2026, 6, 1, tzinfo=UTC)


class TestSloEvaluationService:
    async def test_evaluate_healthy_window_persists_sli(
        self, db_session: AsyncSession, repos, organization_id: UUID, publisher
    ) -> None:
        slo = Slo(
            organization_id=organization_id,
            name="api-availability",
            service_name="gateway",
            sli_kind=SliKind.AVAILABILITY,
            target=0.99,
            window_days=30,
            is_rolling=True,
            fast_burn_hours=1.0,
            fast_burn_threshold=14.4,
            slow_burn_hours=6.0,
            slow_burn_threshold=6.0,
        )
        slo = await repos.slos.create(slo)
        service = SloEvaluationService(repos.slos, repos.slis, publish=publisher)
        window = RatioWindow(
            window_start=NOW - timedelta(days=1), window_end=NOW, good_count=999, total_count=1000
        )
        empty = RatioWindow(
            window_start=NOW - timedelta(hours=1), window_end=NOW, good_count=0, total_count=0
        )
        sli = await service.evaluate(slo, window, fast_window=empty, slow_window=empty, now=NOW)
        assert sli.id is not None
        assert sli.good_count == 999

    async def test_breaching_window_publishes_event(
        self, db_session: AsyncSession, repos, organization_id: UUID, publisher
    ) -> None:
        slo = await repos.slos.create(
            Slo(
                organization_id=organization_id,
                name="checkout-availability",
                service_name="checkout",
                sli_kind=SliKind.AVAILABILITY,
                target=0.999,
                window_days=30,
                is_rolling=True,
                fast_burn_hours=1.0,
                fast_burn_threshold=14.4,
                slow_burn_hours=6.0,
                slow_burn_threshold=6.0,
            )
        )
        service = SloEvaluationService(repos.slos, repos.slis, publish=publisher)
        window = RatioWindow(
            window_start=NOW - timedelta(days=1), window_end=NOW, good_count=800, total_count=1000
        )
        empty = RatioWindow(
            window_start=NOW - timedelta(hours=1), window_end=NOW, good_count=0, total_count=0
        )
        await service.evaluate(slo, window, fast_window=empty, slow_window=empty, now=NOW)
        assert len(publisher.events) == 1
        payload = publisher.events[0].payload
        assert payload["slo_name"] == "checkout-availability"
        assert payload["service_name"] == "checkout"


async def _make_metric_series(repos, organization_id: UUID) -> UUID:
    from app.models.enums import MetricKind, MetricType, SourceKind
    from app.models.signals import MetricSeries

    series = await repos.metric_series.create(
        MetricSeries(
            organization_id=organization_id,
            name="cpu",
            metric_type=MetricType.GAUGE,
            metric_kind=MetricKind.CUSTOM,
            unit=None,
            labels={},
            label_fingerprint="fp-cpu",
            service_name="backend",
            source_kind=SourceKind.CUSTOM_APPLICATION,
            environment="production",
            first_seen_at=NOW - timedelta(hours=1),
            last_seen_at=NOW,
            sample_count=0,
        )
    )
    return series.id


class TestAnomalyDetectionService:
    async def test_sweep_persists_new_detections_and_publishes(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        series_id = await _make_metric_series(repos, organization_id)
        service = AnomalyDetectionService(repos.anomalies, publish=publisher)
        values = [100.0 + (i % 3 - 1) for i in range(40)] + [900.0]
        points = [Point(at=NOW - timedelta(minutes=41 - i), value=v) for i, v in enumerate(values)]
        detections = await service.sweep_series(
            organization_id,
            metric_series_id=series_id,
            metric_name="cpu",
            service_name="backend",
            environment="production",
            points=points,
        )
        assert len(detections) == 1
        assert len(publisher.events) == 1

    async def test_sweep_does_not_duplicate_existing_detection(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        series_id = await _make_metric_series(repos, organization_id)
        service = AnomalyDetectionService(repos.anomalies, publish=publisher)
        values = [100.0 + (i % 3 - 1) for i in range(40)] + [900.0]
        points = [Point(at=NOW - timedelta(minutes=41 - i), value=v) for i, v in enumerate(values)]
        first = await service.sweep_series(
            organization_id,
            metric_series_id=series_id,
            metric_name="cpu",
            service_name="backend",
            environment="production",
            points=points,
        )
        second = await service.sweep_series(
            organization_id,
            metric_series_id=series_id,
            metric_name="cpu",
            service_name="backend",
            environment="production",
            points=points,
        )
        assert len(first) == 1
        assert len(second) == 0

    async def test_sweep_refuses_below_min_history(self, repos, organization_id: UUID) -> None:
        series_id = await _make_metric_series(repos, organization_id)
        service = AnomalyDetectionService(repos.anomalies)
        points = [Point(at=NOW, value=1.0)]
        result = await service.sweep_series(
            organization_id,
            metric_series_id=series_id,
            metric_name="cpu",
            service_name=None,
            environment=None,
            points=points,
        )
        assert result == ()


class TestCapacityForecastService:
    async def test_forecast_resource_persists_row(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        service = CapacityForecastService(repos.forecasts, publish=publisher)
        samples = [(NOW - timedelta(days=40 - i), 100.0 + 2.0 * i) for i in range(40)]
        forecast = await service.forecast_resource(
            organization_id,
            service_name="storage-svc",
            environment="production",
            resource_kind="disk",
            metric_name="disk_used_bytes",
            unit="bytes",
            samples=samples,
            bucket=timedelta(days=1),
            horizon_days=5,
            reduction=ReductionKind.MEAN,
            generated_at=NOW,
        )
        assert forecast.id is not None
        assert len(publisher.events) == 1

    async def test_forecast_refusal_still_persists_row(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        service = CapacityForecastService(repos.forecasts, publish=publisher)
        samples = [(NOW - timedelta(hours=1), 1.0), (NOW, 2.0)]
        forecast = await service.forecast_resource(
            organization_id,
            service_name="tiny-svc",
            environment="production",
            resource_kind="disk",
            metric_name="disk_used_bytes",
            unit="bytes",
            samples=samples,
            bucket=timedelta(days=1),
            horizon_days=5,
            reduction=ReductionKind.MEAN,
            generated_at=NOW,
        )
        assert forecast.refusal_reason is not None


class TestCostReportingService:
    async def test_generate_report_prices_and_attributes(
        self, repos, organization_id: UUID
    ) -> None:
        service = CostReportingService(repos.costs)
        card = RateCard(
            card_id="c1",
            version="v1",
            effective_from=NOW - timedelta(days=60),
            effective_to=None,
            rates={
                "cpu_hours": Rate(
                    meter="cpu_hours", unit="hour", currency="USD", unit_amount=Decimal("0.10")
                )
            },
        )
        record = UsageRecord(
            record_id="u1",
            source="collector",
            meter="cpu_hours",
            unit="hour",
            quantity=Decimal("10"),
            window_start=NOW - timedelta(hours=1),
            window_end=NOW,
            basis=MeterBasis.CUMULATIVE_OVER_INTERVAL,
            labels={"project_id": "proj-1", "service": "backend"},
        )
        report = await service.generate_report(
            organization_id,
            period_start=NOW - timedelta(days=1),
            period_end=NOW,
            generated_at=NOW,
            dimension="project",
            dimension_value="proj-1",
            category=CostCategory.COMPUTE,
            usage_records=[record],
            cards=RateCardSet(cards=(card,)),
            coverage_windows=[],
        )
        assert report.total_cost == Decimal("1.00")
        assert report.attributed_cost == Decimal("1.00")

    async def test_unpriced_meter_excluded_from_total(self, repos, organization_id: UUID) -> None:
        service = CostReportingService(repos.costs)
        record = UsageRecord(
            record_id="u1",
            source="collector",
            meter="unknown_meter",
            unit="hour",
            quantity=Decimal("10"),
            window_start=NOW - timedelta(hours=1),
            window_end=NOW,
        )
        report = await service.generate_report(
            organization_id,
            period_start=NOW - timedelta(days=1),
            period_end=NOW,
            generated_at=NOW,
            dimension="project",
            dimension_value=None,
            category=None,
            usage_records=[record],
            cards=RateCardSet(cards=()),
            coverage_windows=[],
        )
        assert report.total_cost == Decimal("0")
        assert report.details["unpriced_meters"] == ["unknown_meter"]


class TestRootCauseAnalysisService:
    async def test_analyse_incident_persists_report(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        service = RootCauseAnalysisService(repos.root_causes, publish=publisher)
        graph = Graph(
            edges=(
                Edge(
                    caller="checkout",
                    callee="payments",
                    kind=EdgeKind.SYNCHRONOUS,
                    is_observed=True,
                ),
            )
        )
        symptom_series = Series(
            service="checkout",
            values=tuple(float(i % 5) for i in range(20)),
            observed=tuple(True for _ in range(20)),
            bucket_seconds=60.0,
        )
        candidate_series = {
            "payments": Series(
                service="payments",
                values=tuple(float(i % 5) for i in range(20)),
                observed=tuple(True for _ in range(20)),
                bucket_seconds=60.0,
            )
        }
        report = await service.analyse_incident(
            organization_id,
            symptom_service="checkout",
            environment="production",
            incident_reference="INC-1",
            incident_started_at=NOW - timedelta(minutes=30),
            incident_detected_at=NOW,
            symptom_series=symptom_series,
            symptom_signals=[
                RcSignal(
                    signal_id="s1",
                    service="checkout",
                    fingerprint="fp",
                    at=NOW - timedelta(minutes=20),
                )
            ],
            candidate_series=candidate_series,
            candidate_signals={},
            graph=graph,
            window_start=NOW - timedelta(hours=1),
            window_end=NOW,
            analysed_at=NOW,
        )
        assert report.id is not None
        assert len(publisher.events) == 1


class TestTopologyService:
    async def test_sweep_persists_dependency_and_node(self, repos, organization_id: UUID) -> None:
        service = TopologyService(repos.dependencies, repos.topology_nodes)
        spans = [
            SpanRecord(
                span_id="c1",
                trace_id="t1",
                parent_span_id=None,
                service="gateway",
                kind=SpanKindLabel.CLIENT,
                operation="call",
                start_ns=0,
                duration_ns=1000,
            ),
            SpanRecord(
                span_id="s1",
                trace_id="t1",
                parent_span_id="c1",
                service="backend",
                kind=SpanKindLabel.SERVER,
                operation="handle",
                start_ns=1,
                duration_ns=900,
            ),
        ]
        _inference, topology = await service.sweep(
            organization_id,
            environment="production",
            spans=spans,
            window_seconds=60.0,
            sampling_ratio=None,
            observed_at=NOW,
        )
        assert topology.node("backend") is not None

    async def test_sweep_upserts_on_second_run(self, repos, organization_id: UUID) -> None:
        service = TopologyService(repos.dependencies, repos.topology_nodes)
        spans = [
            SpanRecord(
                span_id="c1",
                trace_id="t1",
                parent_span_id=None,
                service="gateway",
                kind=SpanKindLabel.CLIENT,
                operation="call",
                start_ns=0,
                duration_ns=1000,
            ),
            SpanRecord(
                span_id="s1",
                trace_id="t1",
                parent_span_id="c1",
                service="backend",
                kind=SpanKindLabel.SERVER,
                operation="handle",
                start_ns=1,
                duration_ns=900,
            ),
        ]
        await service.sweep(
            organization_id,
            environment="production",
            spans=spans,
            window_seconds=60.0,
            sampling_ratio=None,
            observed_at=NOW,
        )
        _, topology2 = await service.sweep(
            organization_id,
            environment="production",
            spans=spans,
            window_seconds=60.0,
            sampling_ratio=None,
            observed_at=NOW + timedelta(minutes=1),
        )
        node = topology2.node("backend")
        assert node is not None


class TestRetentionService:
    async def test_plan_for_policy(self, repos, organization_id: UUID) -> None:
        policy = await repos.retention_policies.create(
            RetentionPolicy(
                organization_id=organization_id,
                signal_kind=SignalKind.METRIC,
                environment="production",
                raw_days=7,
                downsampled_days=30,
                coarse_days=395,
                downsample_interval_seconds=300,
                is_enabled=True,
            )
        )
        service = RetentionService(repos.retention_policies)
        plan = await service.plan_for_policy(
            policy,
            now=NOW,
            epoch=NOW - timedelta(days=1000),
            raw_downsampled_watermark=None,
            downsampled_coarsened_watermark=None,
        )
        assert plan.refused is None

    async def test_record_sweep_updates_policy(self, repos, organization_id: UUID) -> None:
        policy = await repos.retention_policies.create(
            RetentionPolicy(
                organization_id=organization_id,
                signal_kind=SignalKind.LOG,
                environment="production",
                raw_days=7,
                downsampled_days=30,
                coarse_days=395,
                downsample_interval_seconds=300,
                is_enabled=True,
            )
        )
        service = RetentionService(repos.retention_policies)
        updated = await service.record_sweep(
            organization_id, policy.id, applied_at=NOW, deleted_count=42
        )
        assert updated.last_deleted_count == 42
        assert updated.last_applied_at == NOW

    async def test_plan_all_enabled(self, repos, organization_id: UUID) -> None:
        await repos.retention_policies.create(
            RetentionPolicy(
                organization_id=organization_id,
                signal_kind=SignalKind.EVENT,
                environment="production",
                raw_days=7,
                downsampled_days=30,
                coarse_days=395,
                downsample_interval_seconds=300,
                is_enabled=True,
            )
        )
        service = RetentionService(repos.retention_policies)
        plans = await service.plan_all_enabled(
            organization_id, now=NOW, epoch=NOW - timedelta(days=1000), watermarks={}
        )
        assert len(plans) >= 1


class TestSearchService:
    async def test_search_logs_and_paginate(self, repos, organization_id: UUID) -> None:
        from app.models.enums import LogFormat, LogLevel, SourceKind
        from app.models.signals import LogEntry

        for i in range(3):
            await repos.logs.create(
                LogEntry(
                    organization_id=organization_id,
                    occurred_at=NOW - timedelta(minutes=i),
                    received_at=NOW,
                    level=LogLevel.ERROR,
                    message=f"error {i}",
                    log_format=LogFormat.PLAIN,
                    parse_failed=False,
                    service_name="backend",
                    source_kind=SourceKind.CUSTOM_APPLICATION,
                )
            )
        limits = QueryLimits(
            max_range=timedelta(days=90), max_filters=10, max_page_size=100, default_page_size=20
        )
        service = SearchService(repos.logs, repos.events, limits=limits)
        request = SearchRequest(
            signal_kind=SignalKind.LOG,
            time_range=TimeRange(start=NOW - timedelta(hours=1), end=NOW + timedelta(minutes=1)),
        )
        outcome = await service.search(organization_id, request, now=NOW + timedelta(minutes=1))
        assert isinstance(outcome, tuple)
        validation, rows = outcome
        assert validation.is_valid
        page = SearchService.paginate(validation, rows)
        assert len(page.rows) >= 1

    async def test_search_refused_range_returns_validation_only(
        self, repos, organization_id: UUID
    ) -> None:
        limits = QueryLimits(
            max_range=timedelta(days=1), max_filters=10, max_page_size=100, default_page_size=20
        )
        service = SearchService(repos.logs, repos.events, limits=limits)
        request = SearchRequest(
            signal_kind=SignalKind.LOG,
            time_range=TimeRange(start=NOW - timedelta(days=10), end=NOW),
        )
        outcome = await service.search(organization_id, request, now=NOW)
        assert not isinstance(outcome, tuple)
        assert not outcome.is_valid
