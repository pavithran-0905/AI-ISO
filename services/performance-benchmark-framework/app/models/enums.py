"""Every enum this service's models and engines use (docs/078)."""

from __future__ import annotations

from enum import StrEnum


class BenchmarkType(StrEnum):
    """What kind of system a benchmark suite targets."""

    PLATFORM = "platform"
    API = "api"
    DATABASE = "database"
    WORKFLOW = "workflow"
    AUTOMATION = "automation"
    AI = "ai"
    RAG = "rag"
    GRAPH = "graph"
    CACHE = "cache"
    QUEUE = "queue"
    STORAGE = "storage"
    INFRASTRUCTURE = "infrastructure"
    CLUSTER = "cluster"
    EDGE = "edge"
    CLOUD = "cloud"


class LoadProfile(StrEnum):
    """The load shape a benchmark profile drives."""

    LIGHT = "light"
    NORMAL = "normal"
    PEAK = "peak"
    BURST = "burst"
    SOAK = "soak"
    STRESS = "stress"
    SPIKE = "spike"
    CUSTOM = "custom"


class BenchmarkRunStatus(StrEnum):
    """The shared job lifecycle every benchmark run drives through --
    see ``app.benchmark.engine``."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ResourceType(StrEnum):
    """A kind of resource whose capacity or utilization is tracked."""

    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    CLUSTER = "cluster"
    GPU = "gpu"
    QUEUE = "queue"
    CACHE = "cache"
    CONNECTION_POOL = "connection_pool"
    CONTAINER = "container"


class OptimizationCategory(StrEnum):
    """What area an optimization recommendation targets."""

    QUERY = "query"
    WORKFLOW = "workflow"
    API = "api"
    INFRASTRUCTURE = "infrastructure"
    SCALING = "scaling"


class RecommendationStatus(StrEnum):
    """Whether an optimization recommendation has been acted on."""

    PENDING = "pending"
    APPLIED = "applied"
    DISMISSED = "dismissed"


class RegressionType(StrEnum):
    """What kind of metric a detected regression concerns."""

    LATENCY = "latency"
    THROUGHPUT = "throughput"
    MEMORY = "memory"
    CPU = "cpu"
    API = "api"
    WORKFLOW = "workflow"
    DATABASE = "database"


class RegressionSeverity(StrEnum):
    """How severe a detected regression is."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SliType(StrEnum):
    """What kind of service level indicator an SLO result measures."""

    AVAILABILITY = "availability"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    SUCCESS_RATE = "success_rate"
    RECOVERY_TIME = "recovery_time"
    RESOURCE_UTILIZATION = "resource_utilization"
    CUSTOM = "custom"


class BenchmarkReportKind(StrEnum):
    """What a generated report covers."""

    BENCHMARK = "benchmark"
    PERFORMANCE = "performance"
    REGRESSION = "regression"
    CAPACITY = "capacity"
    SLO = "slo"
    INFRASTRUCTURE = "infrastructure"
    EXECUTIVE = "executive"
    AUDIT = "audit"


class ReportFormat(StrEnum):
    """The file format a generated report is rendered as."""

    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    HTML = "html"


class ReportStatus(StrEnum):
    """Where a report generation stands."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class BenchmarkAuditAction(StrEnum):
    """What was done, for the immutable benchmark audit trail."""

    BENCHMARK_EXECUTION = "benchmark_execution"
    BASELINE_CHANGE = "baseline_change"
    OPTIMIZATION_APPROVAL = "optimization_approval"
    CAPACITY_CHANGE = "capacity_change"
    ADMINISTRATIVE = "administrative"


__all__ = [
    "BenchmarkAuditAction",
    "BenchmarkReportKind",
    "BenchmarkRunStatus",
    "BenchmarkType",
    "LoadProfile",
    "OptimizationCategory",
    "RecommendationStatus",
    "RegressionSeverity",
    "RegressionType",
    "ReportFormat",
    "ReportStatus",
    "ResourceType",
    "SliType",
]
