"""Every persisted model.

All three modules are imported here so Alembic's autogenerate sees the
whole metadata. A model that is not imported is a table the migration will
not create -- and the failure surfaces as a missing relation at runtime,
long after the migration looked like it worked.
"""

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

__all__ = [
    "AnomalyDetection",
    "CapacityForecast",
    "CostReport",
    "Dashboard",
    "LogEntry",
    "Metric",
    "MetricSeries",
    "ObservabilityAudit",
    "ObservabilityEvent",
    "ObservabilityReport",
    "ObservabilityStatistic",
    "Profile",
    "RetentionPolicy",
    "RootCauseReport",
    "SavedQuery",
    "ServiceDependency",
    "ServiceTopologyNode",
    "Sli",
    "Slo",
    "TraceSession",
    "TraceSpan",
]
