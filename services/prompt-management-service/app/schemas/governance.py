"""Request/response shapes for testing, A/B, governance, and analytics
(docs/061 "REST APIs").
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    AbTestArm,
    AbTestStatus,
    ApprovalStatus,
    ExecutionStatus,
    OptimizationKind,
    OptimizationStatus,
    ReportFormat,
    ReportKind,
    ReportStatus,
    ReviewDecision,
    ScanStatus,
    SecuritySeverity,
    TestKind,
    TestRunStatus,
)


class TestCreateRequest(BaseModel):
    """``POST /prompts/test`` -- define a reusable case."""

    prompt_id: UUID
    name: str = Field(min_length=1, max_length=255)
    kind: TestKind = TestKind.AUTOMATED
    description: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    expected_output: str | None = None
    expected_substrings: list[str] = Field(default_factory=list)
    forbidden_substrings: list[str] = Field(default_factory=list)
    minimum_score: float = Field(default=0.7, ge=0.0, le=1.0)


class TestRunRequest(BaseModel):
    """``POST /prompts/test/{id}/run``."""

    version_number: str | None = Field(default=None, max_length=32)
    actual_output: str | None = None
    """A model reply the caller already obtained. When absent, the
    assertions apply to the rendered prompt itself -- this service
    cannot call a model."""


class EvaluateRequest(BaseModel):
    """``POST /prompts/evaluate``."""

    prompt_version_id: UUID
    actual: str = Field(min_length=1)
    expected: str | None = None
    required_points: list[str] = Field(default_factory=list)
    repeated_outputs: list[str] = Field(default_factory=list)
    grounding: list[str] = Field(default_factory=list)
    latency_ms: float | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)


class OptimizeRequest(BaseModel):
    """``POST /prompts/optimize``."""

    prompt_version_id: UUID
    min_saving_ratio: float = Field(default=0.05, gt=0, lt=1)


class AbTestCreateRequest(BaseModel):
    """``POST /prompts/ab-test``."""

    prompt_id: UUID
    name: str = Field(min_length=1, max_length=255)
    control_version_number: str = Field(min_length=1, max_length=32)
    variant_version_number: str = Field(min_length=1, max_length=32)
    variant_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    minimum_samples_per_arm: int = Field(default=100, ge=2)
    significance_level: float = Field(default=0.05, gt=0, lt=1)
    auto_promote: bool = False


class ExecutionRecordRequest(BaseModel):
    """``POST /prompts/executions`` -- reported by whichever service ran it."""

    prompt_id: UUID
    version_number: str = Field(min_length=1, max_length=32)
    status: ExecutionStatus = ExecutionStatus.SUCCEEDED
    rendered_prompt: str | None = None
    """Recorded **masked**. This service applies the masking rather
    than trusting the caller to have done it."""
    model_provider: str | None = Field(default=None, max_length=32)
    model_name: str | None = Field(default=None, max_length=128)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    latency_ms: float | None = Field(default=None, ge=0)
    cost_usd: float = Field(default=0.0, ge=0)
    agent_id: str | None = Field(default=None, max_length=128)
    workflow_id: str | None = Field(default=None, max_length=128)
    ab_test_id: UUID | None = None
    ab_arm: AbTestArm | None = None
    result_metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ReviewRequestBody(BaseModel):
    """``POST /prompts/{id}/reviews``."""

    version_number: str = Field(min_length=1, max_length=32)
    reviewer_id: str = Field(min_length=1, max_length=128)
    is_mandatory: bool = False


class ReviewSubmitRequest(BaseModel):
    """``POST /prompts/reviews/{id}``."""

    decision: ReviewDecision
    comments: str | None = None
    requested_changes: list[str] = Field(default_factory=list)


class ApprovalRequestBody(BaseModel):
    """``POST /prompts/{id}/approvals``."""

    version_number: str = Field(min_length=1, max_length=32)
    required_approvals: int = Field(default=1, ge=1, le=10)


class ApprovalDecideRequest(BaseModel):
    """``POST /prompts/approvals/{id}``."""

    approve: bool
    reason: str | None = None


class TestResponse(BaseModel):
    """One test definition."""

    id: UUID
    prompt_id: UUID
    name: str
    kind: TestKind
    description: str | None
    variables: dict[str, Any]
    expected_output: str | None
    expected_substrings: list[str]
    forbidden_substrings: list[str]
    minimum_score: float
    enabled: bool
    last_status: TestRunStatus
    last_run_at: datetime | None

    model_config = {"from_attributes": True}


class TestResultResponse(BaseModel):
    """One test run."""

    id: UUID
    prompt_test_id: UUID
    prompt_version_id: UUID
    status: TestRunStatus
    score: float | None
    rendered_prompt: str | None
    actual_output: str | None
    failure_reasons: list[str]
    duration_ms: float | None
    run_at: datetime

    model_config = {"from_attributes": True}


class AbTestResponse(BaseModel):
    """One experiment."""

    id: UUID
    prompt_id: UUID
    name: str
    status: AbTestStatus
    control_version_id: UUID
    variant_version_id: UUID
    variant_weight: float
    minimum_samples_per_arm: int
    significance_level: float
    control_executions: int
    control_successes: int
    variant_executions: int
    variant_successes: int
    winner: AbTestArm | None
    p_value: float | None
    is_significant: bool
    decision_notes: str | None
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class EvaluationResponse(BaseModel):
    """One evaluation's scored metrics."""

    prompt_version_id: UUID
    overall: float
    scores: list[dict[str, Any]]


class OptimizationResponse(BaseModel):
    """One optimization suggestion."""

    id: UUID
    prompt_version_id: UUID
    kind: OptimizationKind
    status: OptimizationStatus
    rationale: str
    suggested_body: str | None
    original_tokens: int
    optimized_tokens: int
    token_saving: int
    saving_ratio: float
    estimated_cost_saving_usd: float
    suggested_at: datetime
    decided_at: datetime | None

    model_config = {"from_attributes": True}


class ReviewResponse(BaseModel):
    """One review."""

    id: UUID
    prompt_version_id: UUID
    reviewer_id: str
    decision: ReviewDecision
    comments: str | None
    requested_changes: list[str]
    is_mandatory: bool
    submitted_at: datetime | None

    model_config = {"from_attributes": True}


class ApprovalResponse(BaseModel):
    """One approval gate."""

    id: UUID
    prompt_version_id: UUID
    approver_id: str | None
    status: ApprovalStatus
    required_approvals: int
    reason: str | None
    requested_by: str | None
    requested_at: datetime
    decided_at: datetime | None
    expires_at: datetime

    model_config = {"from_attributes": True}


class SecurityScanResponse(BaseModel):
    """One security scan.

    ``findings`` carry the kind, severity, and a description -- never
    the matched text.
    """

    id: UUID
    prompt_version_id: UUID
    status: ScanStatus
    highest_severity: SecuritySeverity
    findings: list[dict[str, Any]]
    finding_count: int
    blocked_publish: bool
    scanned_at: datetime

    model_config = {"from_attributes": True}


class GateResponse(BaseModel):
    """Whether a revision may be published."""

    allowed: bool
    blockers: list[str]
    reason: str


class StatisticResponse(BaseModel):
    """One rolled-up activity window."""

    id: UUID
    window_start: datetime
    window_end: datetime
    total_prompts: int
    published_prompts: int
    execution_count: int
    executions_succeeded: int
    executions_failed: int
    total_tokens: int
    average_latency_ms: float | None
    average_cost_usd: float | None
    optimization_token_savings: int
    security_findings: int
    by_prompt_type: dict[str, int]
    by_category: dict[str, int]
    top_prompts: list[dict[str, Any]]

    model_config = {"from_attributes": True}


class ReportResponse(BaseModel):
    """One generated report."""

    id: UUID
    kind: ReportKind
    report_format: ReportFormat
    title: str
    status: ReportStatus
    content: dict[str, Any]
    row_count: int | None
    generated_by: str | None
    generated_at: datetime | None
    duration_ms: float | None
    error: str | None

    model_config = {"from_attributes": True}


class ExecutionResponse(BaseModel):
    """One recorded execution."""

    id: UUID
    prompt_id: UUID
    prompt_version_id: UUID
    status: ExecutionStatus
    model_provider: str | None
    model_name: str | None
    total_tokens: int
    latency_ms: float | None
    cost_usd: float
    executed_at: datetime

    model_config = {"from_attributes": True}


__all__ = [
    "AbTestCreateRequest",
    "AbTestResponse",
    "ApprovalDecideRequest",
    "ApprovalRequestBody",
    "ApprovalResponse",
    "EvaluateRequest",
    "EvaluationResponse",
    "ExecutionRecordRequest",
    "ExecutionResponse",
    "GateResponse",
    "OptimizationResponse",
    "OptimizeRequest",
    "ReportResponse",
    "ReviewRequestBody",
    "ReviewResponse",
    "ReviewSubmitRequest",
    "SecurityScanResponse",
    "StatisticResponse",
    "TestCreateRequest",
    "TestResponse",
    "TestResultResponse",
    "TestRunRequest",
]
