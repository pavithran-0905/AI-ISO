"""Enumerations for the Testing & Quality Assurance Framework.

Every enum here is a :class:`~enum.StrEnum` -- stored as its literal
string value in Postgres (plain ``String`` columns, matching every
other AI-IOS service's convention), and comparable with ``==`` against
a value freshly loaded from the database, which comes back as a plain
``str`` rather than the enum instance itself. Coerce through the enum
class first (``EnumClass(value)``) before comparing or reading
``.value`` on a row that may have just come back from a query.
"""

from __future__ import annotations

from enum import StrEnum


class TestType(StrEnum):
    UNIT = "unit"
    INTEGRATION = "integration"
    END_TO_END = "end_to_end"
    REGRESSION = "regression"
    SMOKE = "smoke"
    SANITY = "sanity"
    ACCEPTANCE = "acceptance"
    EXPLORATORY = "exploratory"
    COMPATIBILITY = "compatibility"
    CROSS_PLATFORM = "cross_platform"


class TestRunStatus(StrEnum):
    """The shared lifecycle for a test run and a pipeline result -- see
    ``app.pipeline.engine`` for the transition table this drives."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TestResultStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    FLAKY = "flaky"


class TestEnvironmentType(StrEnum):
    LOCAL = "local"
    DEVELOPMENT = "development"
    QA = "qa"
    UAT = "uat"
    STAGING = "staging"
    PERFORMANCE = "performance"
    PRODUCTION_VERIFICATION = "production_verification"
    EPHEMERAL = "ephemeral"


class MockServiceType(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"
    WEBHOOK = "webhook"
    MESSAGE_QUEUE = "message_queue"
    DATABASE = "database"
    CLOUD = "cloud"
    THIRD_PARTY_API = "third_party_api"


class QualityGateType(StrEnum):
    MINIMUM_COVERAGE = "minimum_coverage"
    PERFORMANCE_THRESHOLDS = "performance_thresholds"
    SECURITY_VALIDATION = "security_validation"
    LINT_VALIDATION = "lint_validation"
    FORMATTING_VALIDATION = "formatting_validation"
    TYPE_VALIDATION = "type_validation"
    DEPENDENCY_VALIDATION = "dependency_validation"
    DOCUMENTATION_VALIDATION = "documentation_validation"
    RELEASE_APPROVAL = "release_approval"


class QualityGateStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class CheckResultStatus(StrEnum):
    """Shared pass/fail/warn outcome for security results, chaos
    results, synthetic checks, and contract tests."""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


class CoverageType(StrEnum):
    UNIT = "unit"
    INTEGRATION = "integration"
    API = "api"
    UI = "ui"
    WORKFLOW = "workflow"
    BRANCH = "branch"
    MUTATION = "mutation"


class PerformanceTestType(StrEnum):
    LOAD = "load"
    STRESS = "stress"
    SPIKE = "spike"
    SOAK = "soak"
    SCALABILITY = "scalability"
    CAPACITY = "capacity"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    RESOURCE_UTILIZATION = "resource_utilization"
    CONCURRENCY = "concurrency"


class SecurityTestType(StrEnum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RBAC = "rbac"
    OWASP_TOP_10 = "owasp_top_10"
    API_SECURITY = "api_security"
    DEPENDENCY_SCANNING = "dependency_scanning"
    SECRET_DETECTION = "secret_detection"
    STATIC_ANALYSIS = "static_analysis"
    DYNAMIC_ANALYSIS = "dynamic_analysis"
    CONTAINER_SECURITY = "container_security"


class ChaosFaultType(StrEnum):
    NETWORK_LATENCY = "network_latency"
    PACKET_LOSS = "packet_loss"
    NODE_FAILURE = "node_failure"
    CONTAINER_FAILURE = "container_failure"
    DATABASE_FAILURE = "database_failure"
    CACHE_FAILURE = "cache_failure"
    QUEUE_FAILURE = "queue_failure"
    SERVICE_FAILURE = "service_failure"
    REGION_FAILURE = "region_failure"


class SyntheticCheckType(StrEnum):
    API_CHECK = "api_check"
    UI_CHECK = "ui_check"
    LOGIN = "login"
    WORKFLOW = "workflow"
    TRANSACTION = "transaction"
    AVAILABILITY = "availability"
    GLOBAL = "global"


class ContractTestType(StrEnum):
    CONSUMER = "consumer"
    PROVIDER = "provider"
    SCHEMA_VALIDATION = "schema_validation"
    VERSION_COMPATIBILITY = "version_compatibility"
    BACKWARD_COMPATIBILITY = "backward_compatibility"
    FORWARD_COMPATIBILITY = "forward_compatibility"
    API_EVOLUTION = "api_evolution"


class QaReportKind(StrEnum):
    COVERAGE = "coverage"
    PERFORMANCE = "performance"
    SECURITY = "security"
    REGRESSION = "regression"
    CHAOS = "chaos"
    BENCHMARK = "benchmark"
    PIPELINE = "pipeline"
    EXECUTIVE_QA = "executive_qa"
    AUDIT = "audit"


class ReportFormat(StrEnum):
    JSON = "json"
    PDF = "pdf"
    CSV = "csv"


class ReportStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class QaAuditAction(StrEnum):
    """What was done, for the immutable QA audit trail."""

    TEST_EXECUTION = "test_execution"
    QUALITY_GATE_CHANGE = "quality_gate_change"
    SECURITY_SCAN = "security_scan"
    PIPELINE_APPROVAL = "pipeline_approval"
    ADMINISTRATIVE = "administrative"


__all__ = [
    "ChaosFaultType",
    "CheckResultStatus",
    "ContractTestType",
    "CoverageType",
    "MockServiceType",
    "PerformanceTestType",
    "QaAuditAction",
    "QaReportKind",
    "QualityGateStatus",
    "QualityGateType",
    "ReportFormat",
    "ReportStatus",
    "SecurityTestType",
    "SyntheticCheckType",
    "TestEnvironmentType",
    "TestResultStatus",
    "TestRunStatus",
    "TestType",
]
