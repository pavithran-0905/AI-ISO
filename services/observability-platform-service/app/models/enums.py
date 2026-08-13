"""The vocabulary this service reasons in (docs/064).

Every enum here is a decision about what distinctions are worth keeping.
Two values that collapse into one are two facts an operator can no longer
tell apart, and the ones that matter most are marked in their own
docstrings -- ``SliStatus.NO_DATA`` against ``SliStatus.BREACHING``, or
``ForecastQuality.INSUFFICIENT`` against a forecast that is merely wide.
"""

from __future__ import annotations

from enum import StrEnum

# ---- data sources and signals --------------------------------------------------------


class SignalKind(StrEnum):
    """The six kinds of observability signal this platform stores.

    Profiles are separate from metrics because a profile is a *sample of
    where time went*, not a number over time, and folding them together
    makes both queries wrong.
    """

    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    EVENT = "event"
    PROFILE = "profile"
    TOPOLOGY = "topology"


class SourceKind(StrEnum):
    """Where a signal came from.

    The spec's own DATA SOURCES list. Kept as an enum rather than a free
    string so a dashboard can group by it without first agreeing on
    spelling -- "k8s", "kubernetes" and "Kubernetes" are one source.
    """

    PLATFORM_SERVICE = "platform_service"
    MICROSERVICE = "microservice"
    WORKER = "worker"
    SCHEDULER = "scheduler"
    AI_AGENT = "ai_agent"
    AI_ASSISTANT = "ai_assistant"
    WORKFLOW = "workflow"
    AUTOMATION = "automation"
    JOB = "job"
    PLUGIN = "plugin"
    CONNECTOR = "connector"
    WEBHOOK = "webhook"
    API_GATEWAY = "api_gateway"
    KUBERNETES = "kubernetes"
    DOCKER = "docker"
    LINUX = "linux"
    WINDOWS = "windows"
    CLOUD_PROVIDER = "cloud_provider"
    EDGE_NODE = "edge_node"
    CUSTOM_APPLICATION = "custom_application"


class MetricKind(StrEnum):
    """What a metric measures, per the spec's METRICS list."""

    SYSTEM = "system"
    APPLICATION = "application"
    BUSINESS = "business"
    INFRASTRUCTURE = "infrastructure"
    AI = "ai"
    WORKFLOW = "workflow"
    AUTOMATION = "automation"
    DATABASE = "database"
    NETWORK = "network"
    CUSTOM = "custom"


class MetricType(StrEnum):
    """How a metric's values compose, which decides how they may be aggregated.

    This is not decoration. A COUNTER only ever increases, so its *rate*
    is the meaningful quantity and averaging its raw values is
    meaningless. A GAUGE may be averaged. A HISTOGRAM's percentiles may
    not be averaged across series at all -- see
    :mod:`app.metrics.aggregation`. Storing the type is what lets the
    aggregator refuse an operation rather than silently producing a
    number nobody should act on.
    """

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class AggregationKind(StrEnum):
    """How a set of samples is reduced to one number."""

    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    RATE = "rate"
    P50 = "p50"
    P90 = "p90"
    P95 = "p95"
    P99 = "p99"
    STDDEV = "stddev"


class LogLevel(StrEnum):
    """Severity, ordered. See :func:`log_level_rank` for the ordering."""

    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"


class LogFormat(StrEnum):
    """How a log line arrived, so a parse failure can name the format it
    was reading rather than reporting an unparseable line."""

    JSON = "json"
    LOGFMT = "logfmt"
    PLAIN = "plain"
    SYSLOG = "syslog"
    COMMON_LOG = "common_log"
    UNKNOWN = "unknown"


class SpanKind(StrEnum):
    """OpenTelemetry span kinds.

    ``SERVER`` and ``CLIENT`` are what make a dependency edge directional:
    a client span in service A whose child is a server span in service B
    is evidence that A depends on B, and not the reverse.
    """

    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(StrEnum):
    """A span's outcome.

    ``UNSET`` is distinct from ``OK`` on purpose: OpenTelemetry's default
    is unset, and counting unset spans as successes inflates every success
    rate computed from traces.
    """

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class EventKind(StrEnum):
    """What kind of thing happened, per the spec's EVENT MANAGEMENT list."""

    PLATFORM = "platform"
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    DEPLOYMENT = "deployment"
    CONFIGURATION = "configuration"
    SECURITY = "security"
    SCALING = "scaling"
    INCIDENT = "incident"
    MAINTENANCE = "maintenance"
    CUSTOM = "custom"


class EventSeverity(StrEnum):
    """How much an event matters. Ordered; see :func:`event_severity_rank`."""

    INFO = "info"
    WARNING = "warning"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class ProfileKind(StrEnum):
    """What a profile sampled."""

    CPU = "cpu"
    MEMORY = "memory"
    HEAP = "heap"
    ALLOCATION = "allocation"
    LOCK = "lock"
    GOROUTINE = "goroutine"
    WALL_CLOCK = "wall_clock"


# ---- SLO and SLI -----------------------------------------------------------------------


class SliKind(StrEnum):
    """What an SLI measures, per the spec's SLO / SLI MANAGEMENT list."""

    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    SUCCESS_RATE = "success_rate"
    THROUGHPUT = "throughput"
    CUSTOM = "custom"


class SliStatus(StrEnum):
    """Where an SLI stands against its objective.

    ``NO_DATA`` is the most important member here and the one most
    commonly missing from SLO tooling. A service that received no requests
    in a window has an *undefined* availability, not a zero one -- and a
    platform that reports the second wakes somebody at 3am because a batch
    job was idle overnight. Every computation in :mod:`app.slo` that
    cannot divide returns this rather than a number.
    """

    HEALTHY = "healthy"
    AT_RISK = "at_risk"
    BREACHING = "breaching"
    EXHAUSTED = "exhausted"
    NO_DATA = "no_data"


class BurnRateWindow(StrEnum):
    """The paired windows of multi-window burn-rate alerting.

    Two windows, both required to fire, because one alone is wrong in a
    predictable direction: a short window alone pages on every brief blip,
    and a long window alone takes hours to notice a total outage.
    """

    FAST = "fast"
    SLOW = "slow"


# ---- anomaly detection -----------------------------------------------------------------


class AnomalyMethod(StrEnum):
    """How an anomaly was concluded.

    Recorded on every detection because an operator's first question is
    "why do you think so", and "the 1-hour value was 6.2 robust deviations
    above the median of the last 14 days at this hour" is an answer where
    "anomaly detected" is not.
    """

    THRESHOLD = "threshold"
    ROBUST_ZSCORE = "robust_zscore"
    SEASONAL = "seasonal"
    FORECAST_DEVIATION = "forecast_deviation"
    SPIKE = "spike"
    LEVEL_SHIFT = "level_shift"
    TREND = "trend"
    CUSTOM_RULE = "custom_rule"
    AI = "ai"


class AnomalyShape(StrEnum):
    """What the anomaly looks like over time.

    Three shapes with three different responses: a SPIKE that has already
    recovered needs no action, a LEVEL_SHIFT means something changed and
    stayed changed, and a TREND means you have time but not much. Reporting
    all three as "anomaly" throws away the only part an operator can act
    on.
    """

    SPIKE = "spike"
    DIP = "dip"
    LEVEL_SHIFT = "level_shift"
    TREND = "trend"
    SEASONAL_DEVIATION = "seasonal_deviation"


class AnomalySeverity(StrEnum):
    """How far outside expectation a detection sits."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---- root cause and topology -------------------------------------------------------------


class CauseConfidence(StrEnum):
    """How much the evidence supports a candidate root cause.

    Deliberately coarse and deliberately capped. This engine correlates;
    it does not establish causation, and a percentage would invite readers
    to treat a correlation as a measured probability of cause. The top
    band is ``STRONG``, never "confirmed".
    """

    INDISTINGUISHABLE = "indistinguishable"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class DependencyDirection(StrEnum):
    """Which way a dependency edge points."""

    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"


class NodeHealth(StrEnum):
    """A topology node's state.

    ``UNKNOWN`` exists because a node with no recent signal is not a
    healthy node; it is a node nothing has heard from, which is often
    worse.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# ---- capacity and cost ---------------------------------------------------------------------


class ResourceKind(StrEnum):
    """What is being forecast, per the spec's CAPACITY PLANNING list."""

    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    IOPS = "iops"
    CONNECTIONS = "connections"
    CUSTOM = "custom"


class ForecastQuality(StrEnum):
    """Whether a forecast is worth acting on.

    ``INSUFFICIENT`` is returned rather than a forecast when there is too
    little history, and ``UNRELIABLE`` when the fit is too poor. Both are
    refusals, and they are separate because they have different remedies:
    one needs time, the other needs a different model or a different
    question.
    """

    GOOD = "good"
    FAIR = "fair"
    UNRELIABLE = "unreliable"
    INSUFFICIENT = "insufficient"


class CostCategory(StrEnum):
    """What a cost was spent on, per the spec's COST ANALYTICS list."""

    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    MODEL_USAGE = "model_usage"
    EMBEDDING = "embedding"
    CLOUD = "cloud"
    LICENSE = "license"
    OTHER = "other"


class CostDimension(StrEnum):
    """How cost is attributed."""

    ORGANIZATION = "organization"
    DEPARTMENT = "department"
    PROJECT = "project"
    SERVICE = "service"
    ENVIRONMENT = "environment"
    UNATTRIBUTED = "unattributed"


# ---- operations -----------------------------------------------------------------------------


class RetentionTier(StrEnum):
    """How long a signal is kept and at what fidelity.

    Downsampling is lossy and irreversible, so the tier is recorded on the
    data: a chart drawn from ``COARSE`` rows must not be presented as if
    it had raw resolution.
    """

    RAW = "raw"
    DOWNSAMPLED = "downsampled"
    COARSE = "coarse"
    ARCHIVED = "archived"


class ReportKind(StrEnum):
    """What a generated report is about."""

    AVAILABILITY = "availability"
    PERFORMANCE = "performance"
    CAPACITY = "capacity"
    COST = "cost"
    INCIDENT = "incident"
    SLO_COMPLIANCE = "slo_compliance"
    ANOMALY = "anomaly"
    AUDIT = "audit"


class ReportFormat(StrEnum):
    """A rendering a report can be exported as."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    HTML = "html"


class ReportStatus(StrEnum):
    """Where a report generation stands."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionStatus(StrEnum):
    """What happened to a batch of ingested signals.

    ``PARTIAL`` because a batch of a thousand spans where three were
    malformed is neither accepted nor rejected, and reporting either loses
    the three or loses the nine hundred and ninety-seven.
    """

    ACCEPTED = "accepted"
    PARTIAL = "partial"
    REJECTED = "rejected"


class AuditAction(StrEnum):
    """What was done, for the immutable trail."""

    INGESTED = "ingested"
    QUERIED = "queried"
    SLO_CREATED = "slo_created"
    SLO_UPDATED = "slo_updated"
    ANOMALY_DETECTED = "anomaly_detected"
    ROOT_CAUSE_ANALYSED = "root_cause_analysed"
    FORECAST_GENERATED = "forecast_generated"
    REPORT_GENERATED = "report_generated"
    RETENTION_APPLIED = "retention_applied"
    DASHBOARD_SAVED = "dashboard_saved"


# ---- ordered comparisons ----------------------------------------------------------------------

_LOG_LEVEL_ORDER: tuple[LogLevel, ...] = (
    LogLevel.TRACE,
    LogLevel.DEBUG,
    LogLevel.INFO,
    LogLevel.WARNING,
    LogLevel.ERROR,
    LogLevel.CRITICAL,
    LogLevel.FATAL,
)

_EVENT_SEVERITY_ORDER: tuple[EventSeverity, ...] = (
    EventSeverity.INFO,
    EventSeverity.WARNING,
    EventSeverity.MINOR,
    EventSeverity.MAJOR,
    EventSeverity.CRITICAL,
)


def log_level_rank(level: LogLevel | str) -> int:
    """Where *level* sits in severity order, lowest first.

    A rank rather than a comparison on the enum itself, because
    ``StrEnum`` compares alphabetically -- which puts ``critical`` below
    ``debug`` and makes every "at least WARNING" filter silently wrong.
    """
    return _LOG_LEVEL_ORDER.index(LogLevel(str(level)))


def event_severity_rank(severity: EventSeverity | str) -> int:
    """Where *severity* sits in order, lowest first. See
    :func:`log_level_rank` for why this is not a string comparison."""
    return _EVENT_SEVERITY_ORDER.index(EventSeverity(str(severity)))


def at_least(level: LogLevel | str, minimum: LogLevel | str) -> bool:
    """Whether *level* is at least as severe as *minimum*."""
    return log_level_rank(level) >= log_level_rank(minimum)


CUMULATIVE_TYPES = frozenset({MetricType.COUNTER})
"""Metric types whose raw values only increase.

Averaging one of these is meaningless -- the average of a counter is a
fact about how long it has been running, not about the system. The
aggregator refuses rather than returning it."""

NON_AVERAGEABLE_AGGREGATIONS = frozenset(
    {AggregationKind.P50, AggregationKind.P90, AggregationKind.P95, AggregationKind.P99}
)
"""Aggregations that may not themselves be averaged.

The mean of two p99s is not the p99 of the union: percentiles are not
linear. Combining them requires the underlying distribution, which is why
histograms are stored with their buckets rather than only their computed
percentiles."""

TERMINAL_REPORT_STATUSES = frozenset({ReportStatus.COMPLETED, ReportStatus.FAILED})

ACTIONABLE_ANOMALY_SHAPES = frozenset({AnomalyShape.LEVEL_SHIFT, AnomalyShape.TREND})
"""Shapes that describe a condition still in effect.

A ``SPIKE`` that has already recovered is history; a level shift or a
trend is a thing still happening, and those are what a page should be
about."""


def is_terminal_report(status: ReportStatus | str) -> bool:
    """Whether a report has finished, either way."""
    return ReportStatus(str(status)) in TERMINAL_REPORT_STATUSES


def can_average(metric_type: MetricType | str) -> bool:
    """Whether raw samples of this metric type may be averaged."""
    return MetricType(str(metric_type)) not in CUMULATIVE_TYPES


__all__ = [
    "ACTIONABLE_ANOMALY_SHAPES",
    "CUMULATIVE_TYPES",
    "NON_AVERAGEABLE_AGGREGATIONS",
    "TERMINAL_REPORT_STATUSES",
    "AggregationKind",
    "AnomalyMethod",
    "AnomalySeverity",
    "AnomalyShape",
    "AuditAction",
    "BurnRateWindow",
    "CauseConfidence",
    "CostCategory",
    "CostDimension",
    "DependencyDirection",
    "EventKind",
    "EventSeverity",
    "ForecastQuality",
    "IngestionStatus",
    "LogFormat",
    "LogLevel",
    "MetricKind",
    "MetricType",
    "NodeHealth",
    "ProfileKind",
    "ReportFormat",
    "ReportKind",
    "ReportStatus",
    "ResourceKind",
    "RetentionTier",
    "SignalKind",
    "SliKind",
    "SliStatus",
    "SourceKind",
    "SpanKind",
    "SpanStatus",
    "at_least",
    "can_average",
    "event_severity_rank",
    "is_terminal_report",
    "log_level_rank",
]
