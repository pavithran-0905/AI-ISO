"""Direct integration tests for repository query methods not already
exercised transitively by the service-layer integration tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.models.analysis import (
    AnomalyDetection,
    CapacityForecast,
    CostReport,
    RootCauseReport,
    ServiceDependency,
    ServiceTopologyNode,
    Sli,
    Slo,
)
from app.models.enums import (
    AnomalyMethod,
    AnomalySeverity,
    AnomalyShape,
    AuditAction,
    CauseConfidence,
    ForecastQuality,
    LogFormat,
    LogLevel,
    MetricKind,
    MetricType,
    NodeHealth,
    ReportKind,
    ReportStatus,
    ResourceKind,
    SignalKind,
    SliKind,
    SliStatus,
    SourceKind,
    SpanKind,
    SpanStatus,
)
from app.models.operations import (
    Dashboard,
    ObservabilityAudit,
    ObservabilityReport,
    ObservabilityStatistic,
    RetentionPolicy,
    SavedQuery,
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

NOW = datetime(2026, 6, 1, tzinfo=UTC)


# ---- signals repositories ------------------------------------------------------------


class TestMetricSeriesRepository:
    async def test_find_by_identity_and_list_organization_ids(
        self, repos, organization_id: UUID
    ) -> None:
        series = await repos.metric_series.create(
            MetricSeries(
                organization_id=organization_id,
                name="cpu",
                metric_type=MetricType.GAUGE,
                metric_kind=MetricKind.CUSTOM,
                labels={},
                label_fingerprint="fp1",
                source_kind=SourceKind.CUSTOM_APPLICATION,
                first_seen_at=NOW,
                last_seen_at=NOW,
                sample_count=0,
            )
        )
        found = await repos.metric_series.find_by_identity(organization_id, "cpu", "fp1")
        assert found is not None and found.id == series.id
        org_ids = await repos.metric_series.list_organization_ids()
        assert organization_id in org_ids

    async def test_require_in_org_raises_when_missing(self, repos, organization_id: UUID) -> None:
        from shared_core.exceptions.not_found import NotFoundError

        with pytest.raises(NotFoundError):
            await repos.metric_series.require_in_org(organization_id, uuid4())

    async def test_list_stale_and_active(self, repos, organization_id: UUID) -> None:
        stale = await repos.metric_series.create(
            MetricSeries(
                organization_id=organization_id,
                name="stale",
                metric_type=MetricType.GAUGE,
                metric_kind=MetricKind.CUSTOM,
                labels={},
                label_fingerprint="fp-stale",
                source_kind=SourceKind.CUSTOM_APPLICATION,
                first_seen_at=NOW - timedelta(days=10),
                last_seen_at=NOW - timedelta(days=10),
                sample_count=0,
            )
        )
        active = await repos.metric_series.create(
            MetricSeries(
                organization_id=organization_id,
                name="active",
                metric_type=MetricType.GAUGE,
                metric_kind=MetricKind.CUSTOM,
                labels={},
                label_fingerprint="fp-active",
                source_kind=SourceKind.CUSTOM_APPLICATION,
                first_seen_at=NOW,
                last_seen_at=NOW,
                sample_count=0,
            )
        )
        stale_rows = await repos.metric_series.list_stale(
            organization_id, older_than=NOW - timedelta(days=1)
        )
        assert stale.id in {r.id for r in stale_rows}
        active_rows = await repos.metric_series.list_active(
            organization_id, since=NOW - timedelta(hours=1)
        )
        assert active.id in {r.id for r in active_rows}


class TestMetricRepository:
    async def test_purge_older_than_and_list_for_series(self, repos, organization_id: UUID) -> None:
        series = await repos.metric_series.create(
            MetricSeries(
                organization_id=organization_id,
                name="m",
                metric_type=MetricType.GAUGE,
                metric_kind=MetricKind.CUSTOM,
                labels={},
                label_fingerprint="fp-m",
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
                occurred_at=NOW - timedelta(days=100),
                received_at=NOW,
                value=1.0,
            )
        )
        await repos.metrics.create(
            Metric(
                organization_id=organization_id,
                metric_series_id=series.id,
                occurred_at=NOW,
                received_at=NOW,
                value=2.0,
            )
        )
        rows = await repos.metrics.list_for_series(
            series.id, start=NOW - timedelta(hours=1), end=NOW + timedelta(hours=1)
        )
        assert len(rows) == 1
        deleted = await repos.metrics.purge_older_than(
            organization_id, older_than=NOW - timedelta(days=1)
        )
        assert deleted == 1


class TestLogEntryRepository:
    async def test_search_window_and_parse_failures(self, repos, organization_id: UUID) -> None:
        await repos.logs.create(
            LogEntry(
                organization_id=organization_id,
                occurred_at=NOW,
                received_at=NOW,
                level=LogLevel.ERROR,
                message="bad",
                log_format=LogFormat.PLAIN,
                parse_failed=True,
                service_name="backend",
                source_kind=SourceKind.CUSTOM_APPLICATION,
            )
        )
        rows = await repos.logs.search_window(
            organization_id,
            start=NOW - timedelta(hours=1),
            end=NOW + timedelta(hours=1),
            service_name="backend",
            level=LogLevel.ERROR,
        )
        assert len(rows) == 1
        failures = await repos.logs.list_parse_failures(
            organization_id, since=NOW - timedelta(hours=1)
        )
        assert len(failures) == 1

    async def test_purge_older_than(self, repos, organization_id: UUID) -> None:
        await repos.logs.create(
            LogEntry(
                organization_id=organization_id,
                occurred_at=NOW - timedelta(days=100),
                received_at=NOW,
                level=LogLevel.INFO,
                message="old",
                log_format=LogFormat.PLAIN,
                parse_failed=False,
                source_kind=SourceKind.CUSTOM_APPLICATION,
            )
        )
        deleted = await repos.logs.purge_older_than(
            organization_id, older_than=NOW - timedelta(days=1)
        )
        assert deleted == 1


class TestTraceSessionRepository:
    async def test_find_by_trace_id_and_list_incomplete(self, repos, organization_id: UUID) -> None:
        await repos.trace_sessions.create(
            TraceSession(
                organization_id=organization_id,
                trace_id="t1",
                started_at=NOW - timedelta(hours=2),
                span_count=1,
                error_span_count=0,
                service_count=1,
                max_depth=0,
                has_error=False,
                is_complete=False,
                orphan_span_count=0,
                services=["svc"],
            )
        )
        found = await repos.trace_sessions.find_by_trace_id(organization_id, "t1")
        assert found is not None
        incomplete = await repos.trace_sessions.list_incomplete(
            organization_id, older_than=NOW - timedelta(hours=1)
        )
        assert len(incomplete) == 1


class TestTraceSpanRepository:
    async def test_list_recent_for_trace_errors_and_org_ids(
        self, repos, organization_id: UUID
    ) -> None:
        await repos.trace_spans.create(
            TraceSpan(
                organization_id=organization_id,
                trace_id="t1",
                span_id="s1",
                name="op",
                span_kind=SpanKind.SERVER,
                status=SpanStatus.ERROR,
                service_name="backend",
                source_kind=SourceKind.MICROSERVICE,
                started_at=NOW,
                ended_at=NOW,
                duration_ms=10.0,
                depth=0,
                is_orphan=False,
            )
        )
        recent = await repos.trace_spans.list_recent(
            organization_id, since=NOW - timedelta(hours=1)
        )
        assert len(recent) == 1
        for_trace = await repos.trace_spans.list_for_trace(organization_id, "t1")
        assert len(for_trace) == 1
        errors = await repos.trace_spans.list_errors_for_service(
            organization_id, "backend", start=NOW - timedelta(hours=1), end=NOW + timedelta(hours=1)
        )
        assert len(errors) == 1
        org_ids = await repos.trace_spans.list_organization_ids()
        assert organization_id in org_ids
        deleted = await repos.trace_spans.purge_older_than(
            organization_id, older_than=NOW + timedelta(hours=1)
        )
        assert deleted == 1


class TestObservabilityEventRepository:
    async def test_search_window_active_at_and_purge(self, repos, organization_id: UUID) -> None:
        from app.models.enums import EventKind, EventSeverity

        await repos.events.create(
            ObservabilityEvent(
                organization_id=organization_id,
                event_kind=EventKind.DEPLOYMENT,
                severity=EventSeverity.INFO,
                title="deploy",
                occurred_at=NOW - timedelta(minutes=30),
                received_at=NOW,
                ended_at=NOW + timedelta(minutes=30),
                source_kind=SourceKind.PLATFORM_SERVICE,
            )
        )
        rows = await repos.events.search_window(
            organization_id, start=NOW - timedelta(hours=1), end=NOW + timedelta(hours=1)
        )
        assert len(rows) == 1
        active = await repos.events.active_at(organization_id, NOW)
        assert len(active) == 1
        deleted = await repos.events.purge_older_than(
            organization_id, older_than=NOW + timedelta(hours=2)
        )
        assert deleted == 1


class TestProfileRepository:
    async def test_list_for_service_and_purge(self, repos, organization_id: UUID) -> None:
        from app.models.enums import ProfileKind

        await repos.profiles.create(
            Profile(
                organization_id=organization_id,
                profile_kind=ProfileKind.CPU,
                service_name="backend",
                source_kind=SourceKind.MICROSERVICE,
                captured_at=NOW,
                duration_ms=100.0,
                sample_count=10,
                total_value=1.0,
                frames=[],
                truncated=False,
            )
        )
        rows = await repos.profiles.list_for_service(
            organization_id, "backend", start=NOW - timedelta(hours=1), end=NOW + timedelta(hours=1)
        )
        assert len(rows) == 1
        deleted = await repos.profiles.purge_older_than(
            organization_id, older_than=NOW + timedelta(hours=1)
        )
        assert deleted == 1


# ---- analysis repositories -----------------------------------------------------------


class TestServiceDependencyRepository:
    async def test_find_list_for_service_stale_and_environment(
        self, repos, organization_id: UUID
    ) -> None:
        await repos.dependencies.create(
            ServiceDependency(
                organization_id=organization_id,
                caller_service="a",
                callee_service="b",
                environment="production",
                first_observed_at=NOW - timedelta(days=1),
                last_observed_at=NOW - timedelta(days=1),
            )
        )
        found = await repos.dependencies.find_edge(organization_id, "a", "b", "production")
        assert found is not None
        for_service = await repos.dependencies.list_for_service(organization_id, "a", "production")
        assert len(for_service) == 1
        stale = await repos.dependencies.list_stale(organization_id, "production", older_than=NOW)
        assert len(stale) == 1
        env_edges = await repos.dependencies.list_for_environment(organization_id, "production")
        assert len(env_edges) == 1


class TestServiceTopologyNodeRepository:
    async def test_find_list_critical_and_unhealthy(self, repos, organization_id: UUID) -> None:
        await repos.topology_nodes.create(
            ServiceTopologyNode(
                organization_id=organization_id,
                service_name="hub",
                environment="production",
                health=NodeHealth.DEGRADED,
                criticality=5.0,
                first_seen_at=NOW,
                last_seen_at=NOW,
            )
        )
        found = await repos.topology_nodes.find_node(organization_id, "hub", "production")
        assert found is not None
        critical = await repos.topology_nodes.list_critical(organization_id, "production")
        assert len(critical) == 1
        unhealthy = await repos.topology_nodes.list_unhealthy(organization_id, "production")
        assert len(unhealthy) == 1


class TestSloRepository:
    async def test_require_in_org_list_enabled_and_org_ids(
        self, repos, organization_id: UUID
    ) -> None:
        from shared_core.exceptions.not_found import NotFoundError

        slo = await repos.slos.create(
            Slo(
                organization_id=organization_id,
                name="s1",
                service_name="svc",
                sli_kind=SliKind.AVAILABILITY,
                target=0.99,
            )
        )
        found = await repos.slos.require_in_org(organization_id, slo.id)
        assert found.id == slo.id
        with pytest.raises(NotFoundError):
            await repos.slos.require_in_org(organization_id, uuid4())
        enabled = await repos.slos.list_enabled(organization_id, service_name="svc")
        assert len(enabled) == 1
        org_ids = await repos.slos.list_organization_ids()
        assert organization_id in org_ids


class TestSliRepository:
    async def test_latest_list_for_slo_and_burning(self, repos, organization_id: UUID) -> None:
        slo = await repos.slos.create(
            Slo(
                organization_id=organization_id,
                name="s2",
                service_name="svc",
                sli_kind=SliKind.AVAILABILITY,
                target=0.99,
            )
        )
        await repos.slis.create(
            Sli(
                organization_id=organization_id,
                slo_id=slo.id,
                window_start=NOW - timedelta(hours=1),
                window_end=NOW,
                good_count=90,
                total_count=100,
                value=0.9,
                status=SliStatus.BREACHING,
                is_burning=True,
                computed_at=NOW,
            )
        )
        latest = await repos.slis.latest_for_slo(slo.id)
        assert latest is not None
        windowed = await repos.slis.list_for_slo(
            slo.id, start=NOW - timedelta(hours=2), end=NOW + timedelta(hours=1)
        )
        assert len(windowed) == 1
        burning = await repos.slis.list_burning(organization_id)
        assert len(burning) == 1


class TestAnomalyDetectionRepository:
    async def test_list_recent_and_acknowledge(self, repos, organization_id: UUID) -> None:
        from shared_core.exceptions.not_found import NotFoundError

        detection = await repos.anomalies.create(
            AnomalyDetection(
                organization_id=organization_id,
                service_name="backend",
                detected_at=NOW,
                occurred_at=NOW,
                method=AnomalyMethod.ROBUST_ZSCORE,
                shape=AnomalyShape.SPIKE,
                severity=AnomalySeverity.HIGH,
                observed_value=900.0,
                rationale="spike",
            )
        )
        recent = await repos.anomalies.list_recent(
            organization_id,
            since=NOW - timedelta(hours=1),
            service_name="backend",
            min_severity=AnomalySeverity.MEDIUM,
            unacknowledged_only=True,
        )
        assert len(recent) == 1
        acked = await repos.anomalies.acknowledge(
            organization_id, detection.id, acknowledged_by="oncall"
        )
        assert acked.is_acknowledged
        with pytest.raises(NotFoundError):
            await repos.anomalies.acknowledge(organization_id, uuid4(), acknowledged_by="oncall")


class TestRootCauseReportRepository:
    async def test_find_for_incident_and_list_for_service(
        self, repos, organization_id: UUID
    ) -> None:
        await repos.root_causes.create(
            RootCauseReport(
                organization_id=organization_id,
                service_name="checkout",
                incident_reference="INC-9",
                analysed_at=NOW,
                incident_started_at=NOW - timedelta(minutes=10),
                confidence=CauseConfidence.WEAK,
            )
        )
        found = await repos.root_causes.find_for_incident(organization_id, "INC-9")
        assert found is not None
        for_service = await repos.root_causes.list_for_service(organization_id, "checkout")
        assert len(for_service) == 1


class TestCapacityForecastRepository:
    async def test_latest_for_resource_and_at_risk(self, repos, organization_id: UUID) -> None:
        await repos.forecasts.create(
            CapacityForecast(
                organization_id=organization_id,
                service_name="storage",
                resource_kind=ResourceKind.STORAGE,
                generated_at=NOW,
                history_start=NOW - timedelta(days=30),
                history_end=NOW,
                quality=ForecastQuality.GOOD,
                days_until_exhaustion=5.0,
            )
        )
        latest = await repos.forecasts.latest_for_resource(
            organization_id, "storage", ResourceKind.STORAGE
        )
        assert latest is not None
        at_risk = await repos.forecasts.list_at_risk(organization_id, within_days=10.0)
        assert len(at_risk) == 1


class TestCostReportRepository:
    async def test_find_period_and_list_for_period(self, repos, organization_id: UUID) -> None:
        await repos.costs.create(
            CostReport(
                organization_id=organization_id,
                period_start=NOW - timedelta(days=1),
                period_end=NOW,
                generated_at=NOW,
                dimension="project",
                dimension_value="proj-1",
                total_cost=Decimal("10"),
                attributed_cost=Decimal("10"),
                unattributed_cost=Decimal("0"),
            )
        )
        found = await repos.costs.find_period(
            organization_id,
            period_start=NOW - timedelta(days=1),
            period_end=NOW,
            dimension="project",
            dimension_value="proj-1",
        )
        assert found is not None
        for_period = await repos.costs.list_for_period(
            organization_id,
            period_start=NOW - timedelta(days=1),
            period_end=NOW,
            dimension="project",
        )
        assert len(for_period) == 1


# ---- operations repositories ----------------------------------------------------------


class TestObservabilityStatisticRepository:
    async def test_find_window_and_list_range(self, repos, organization_id: UUID) -> None:
        await repos.statistics.create(
            ObservabilityStatistic(
                organization_id=organization_id,
                window_start=NOW - timedelta(hours=1),
                window_end=NOW,
            )
        )
        found = await repos.statistics.find_window(
            organization_id, window_start=NOW - timedelta(hours=1), window_end=NOW
        )
        assert found is not None
        ranged = await repos.statistics.list_range(
            organization_id, start=NOW - timedelta(hours=2), end=NOW + timedelta(hours=1)
        )
        assert len(ranged) == 1


class TestObservabilityReportRepository:
    async def test_require_in_org_and_list_recent(self, repos, organization_id: UUID) -> None:
        from shared_core.exceptions.not_found import NotFoundError

        report = await repos.reports.create(
            ObservabilityReport(
                organization_id=organization_id,
                kind=ReportKind.SLO_COMPLIANCE,
                title="Report",
                status=ReportStatus.COMPLETED,
            )
        )
        found = await repos.reports.require_in_org(organization_id, report.id)
        assert found.id == report.id
        with pytest.raises(NotFoundError):
            await repos.reports.require_in_org(organization_id, uuid4())
        recent = await repos.reports.list_recent(organization_id, status=ReportStatus.COMPLETED)
        assert len(recent) == 1


class TestObservabilityAuditRepository:
    async def test_list_for_entity_and_recent(self, repos, organization_id: UUID) -> None:
        entity_id = uuid4()
        await repos.audits.create(
            ObservabilityAudit(
                organization_id=organization_id,
                action=AuditAction.QUERIED,
                entity_type="search",
                entity_id=entity_id,
                occurred_at=NOW,
                actor_id="user-1",
            )
        )
        for_entity = await repos.audits.list_for_entity(organization_id, "search", entity_id)
        assert len(for_entity) == 1
        recent = await repos.audits.list_recent(
            organization_id,
            since=NOW - timedelta(hours=1),
            action=AuditAction.QUERIED,
            actor_id="user-1",
        )
        assert len(recent) == 1


class TestSavedQueryRepository:
    async def test_find_by_name_list_visible_and_record_run(
        self, repos, organization_id: UUID
    ) -> None:
        query = await repos.saved_queries.create(
            SavedQuery(
                organization_id=organization_id,
                name="errors",
                signal_kind=SignalKind.LOG,
                owner="user-1",
            )
        )
        found = await repos.saved_queries.find_by_name(organization_id, "errors")
        assert found is not None
        visible = await repos.saved_queries.list_visible_to(
            organization_id, "user-1", signal_kind=SignalKind.LOG
        )
        assert len(visible) == 1
        updated = await repos.saved_queries.record_run(
            organization_id, query.id, duration_ms=50.0, at=NOW
        )
        assert updated.run_count == 1
        assert updated.mean_duration_ms == 50.0


class TestDashboardRepository:
    async def test_find_by_slug_list_visible_and_record_view(
        self, repos, organization_id: UUID
    ) -> None:
        dashboard = await repos.dashboards.create(
            Dashboard(
                organization_id=organization_id, name="Overview", slug="overview", owner="user-1"
            )
        )
        found = await repos.dashboards.find_by_slug(organization_id, "overview")
        assert found is not None
        visible = await repos.dashboards.list_visible_to(organization_id, "user-1")
        assert len(visible) == 1
        updated = await repos.dashboards.record_view(organization_id, dashboard.id, at=NOW)
        assert updated.view_count == 1


class TestRetentionPolicyRepository:
    async def test_find_for_scope_list_enabled_org_ids_and_as_spec(
        self, repos, organization_id: UUID
    ) -> None:
        policy = await repos.retention_policies.create(
            RetentionPolicy(
                organization_id=organization_id,
                signal_kind=SignalKind.TRACE,
                environment="production",
            )
        )
        found = await repos.retention_policies.find_for_scope(
            organization_id, SignalKind.TRACE, "production"
        )
        assert found is not None
        enabled = await repos.retention_policies.list_enabled(organization_id)
        assert len(enabled) == 1
        org_ids = await repos.retention_policies.list_organization_ids()
        assert organization_id in org_ids
        spec = type(repos.retention_policies).as_spec(policy)
        assert spec.signal_kind == SignalKind.TRACE
