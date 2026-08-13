"""The repository bundle every route works through.

One object rather than twenty-one constructor arguments, all sharing one
tenant scope: a bundle where one repository was built without it would
enforce tenant isolation everywhere except the one query that forgot,
and that query is the leak.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.analysis import (
    AnomalyDetectionRepository,
    CapacityForecastRepository,
    CostReportRepository,
    RootCauseReportRepository,
    ServiceDependencyRepository,
    ServiceTopologyNodeRepository,
    SliRepository,
    SloRepository,
)
from app.repositories.operations import (
    DashboardRepository,
    ObservabilityAuditRepository,
    ObservabilityReportRepository,
    ObservabilityStatisticRepository,
    RetentionPolicyRepository,
    SavedQueryRepository,
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


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    metric_series: MetricSeriesRepository
    metrics: MetricRepository
    logs: LogEntryRepository
    trace_sessions: TraceSessionRepository
    trace_spans: TraceSpanRepository
    events: ObservabilityEventRepository
    profiles: ProfileRepository

    dependencies: ServiceDependencyRepository
    topology_nodes: ServiceTopologyNodeRepository
    slos: SloRepository
    slis: SliRepository
    anomalies: AnomalyDetectionRepository
    root_causes: RootCauseReportRepository
    forecasts: CapacityForecastRepository
    costs: CostReportRepository

    statistics: ObservabilityStatisticRepository
    reports: ObservabilityReportRepository
    audits: ObservabilityAuditRepository
    saved_queries: SavedQueryRepository
    dashboards: DashboardRepository
    retention_policies: RetentionPolicyRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        metric_series=MetricSeriesRepository(session, tenant_scope=tenant_scope),
        metrics=MetricRepository(session, tenant_scope=tenant_scope),
        logs=LogEntryRepository(session, tenant_scope=tenant_scope),
        trace_sessions=TraceSessionRepository(session, tenant_scope=tenant_scope),
        trace_spans=TraceSpanRepository(session, tenant_scope=tenant_scope),
        events=ObservabilityEventRepository(session, tenant_scope=tenant_scope),
        profiles=ProfileRepository(session, tenant_scope=tenant_scope),
        dependencies=ServiceDependencyRepository(session, tenant_scope=tenant_scope),
        topology_nodes=ServiceTopologyNodeRepository(session, tenant_scope=tenant_scope),
        slos=SloRepository(session, tenant_scope=tenant_scope),
        slis=SliRepository(session, tenant_scope=tenant_scope),
        anomalies=AnomalyDetectionRepository(session, tenant_scope=tenant_scope),
        root_causes=RootCauseReportRepository(session, tenant_scope=tenant_scope),
        forecasts=CapacityForecastRepository(session, tenant_scope=tenant_scope),
        costs=CostReportRepository(session, tenant_scope=tenant_scope),
        statistics=ObservabilityStatisticRepository(session, tenant_scope=tenant_scope),
        reports=ObservabilityReportRepository(session, tenant_scope=tenant_scope),
        audits=ObservabilityAuditRepository(session, tenant_scope=tenant_scope),
        saved_queries=SavedQueryRepository(session, tenant_scope=tenant_scope),
        dashboards=DashboardRepository(session, tenant_scope=tenant_scope),
        retention_policies=RetentionPolicyRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
