"""Repositories for every table in the observability platform service."""

from __future__ import annotations

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

__all__ = [
    "AnomalyDetectionRepository",
    "CapacityForecastRepository",
    "CostReportRepository",
    "DashboardRepository",
    "LogEntryRepository",
    "MetricRepository",
    "MetricSeriesRepository",
    "ObservabilityAuditRepository",
    "ObservabilityEventRepository",
    "ObservabilityReportRepository",
    "ObservabilityStatisticRepository",
    "ProfileRepository",
    "RetentionPolicyRepository",
    "RootCauseReportRepository",
    "SavedQueryRepository",
    "ServiceDependencyRepository",
    "ServiceTopologyNodeRepository",
    "SliRepository",
    "SloRepository",
    "TraceSessionRepository",
    "TraceSpanRepository",
]
