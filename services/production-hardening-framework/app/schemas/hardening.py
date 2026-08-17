"""Request/response shapes for the 11 docs/079 REST endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    CertificationStatus,
    CheckResultStatus,
    CisBenchmark,
    ComplianceFramework,
    FindingSeverity,
    FindingStatus,
    HardeningReportKind,
    HardeningRunStatus,
    HardeningTargetType,
    RemediationStatus,
    VulnerabilityScanType,
)

MAX_PAGE_SIZE = 500


# ---- GET /hardening --------------------------------------------------------------------------


class HardeningProfileResponse(BaseModel):
    id: UUID
    name: str
    target_type: HardeningTargetType
    benchmark: CisBenchmark
    description: str
    is_enabled: bool


class HardeningProfilesResponse(BaseModel):
    profiles: list[HardeningProfileResponse]
    total: int


# ---- POST /hardening/run ---------------------------------------------------------------------


class HardeningRunRequest(BaseModel):
    hardening_profile_id: UUID


class HardeningRunResponse(BaseModel):
    id: UUID
    hardening_profile_id: UUID
    status: HardeningRunStatus
    started_at: datetime | None
    completed_at: datetime | None


# ---- GET /hardening/results -------------------------------------------------------------------


class HardeningResultResponse(BaseModel):
    id: UUID
    hardening_run_id: UUID
    check_name: str
    status: CheckResultStatus
    detail: str


class HardeningResultsResponse(BaseModel):
    results: list[HardeningResultResponse]
    total: int


# ---- GET /security/findings -------------------------------------------------------------------


class SecurityFindingResponse(BaseModel):
    id: UUID
    target_type: HardeningTargetType
    severity: FindingSeverity
    title: str
    detail: str
    status: FindingStatus


class SecurityFindingsResponse(BaseModel):
    findings: list[SecurityFindingResponse]
    total: int


# ---- GET /vulnerabilities ---------------------------------------------------------------------


class VulnerabilityScanResponse(BaseModel):
    id: UUID
    scan_type: VulnerabilityScanType
    cve_id: str
    severity: FindingSeverity
    package_name: str
    package_version: str
    status: RemediationStatus


class VulnerabilityScansResponse(BaseModel):
    vulnerabilities: list[VulnerabilityScanResponse]
    total: int


# ---- GET/POST /certifications ------------------------------------------------------------------


class ProductionCertificationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    hardening_rate: float = Field(ge=0.0, le=1.0)
    compliance_rate: float = Field(ge=0.0, le=1.0)
    readiness_rate: float = Field(ge=0.0, le=1.0)


class ProductionCertificationResponse(BaseModel):
    id: UUID
    name: str
    status: CertificationStatus
    risk_score: float
    granted_at: datetime | None
    expires_at: datetime | None


class ProductionCertificationsResponse(BaseModel):
    certifications: list[ProductionCertificationResponse]
    total: int


# ---- GET /compliance --------------------------------------------------------------------------


class ComplianceResultResponse(BaseModel):
    id: UUID
    framework: ComplianceFramework
    control_id: str
    is_compliant: bool
    evaluated_at: datetime


class ComplianceResultsResponse(BaseModel):
    results: list[ComplianceResultResponse]
    total: int


# ---- GET /production-readiness ----------------------------------------------------------------


class ProductionReadinessResponse(BaseModel):
    """Computed live from current signals -- there is no dedicated
    persisted table for this endpoint's own result."""

    score: float
    is_ready: bool
    hardening_rate: float
    compliance_rate: float
    operational_readiness_rate: float
    disaster_recovery_rate: float


# ---- GET /reports -----------------------------------------------------------------------------


class HardeningReportResponse(BaseModel):
    id: UUID
    kind: HardeningReportKind
    report_format: str
    title: str
    status: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime | None
    row_count: int


class HardeningReportsResponse(BaseModel):
    reports: list[HardeningReportResponse]
    total: int


# ---- GET /statistics --------------------------------------------------------------------------


class HardeningStatisticWindowResponse(BaseModel):
    window_start: datetime
    window_end: datetime
    hardening_run_count: int
    security_finding_count: int
    vulnerability_count: int
    avg_hardening_score: float


class HardeningStatisticsResponse(BaseModel):
    windows: list[HardeningStatisticWindowResponse]
    total: int


__all__ = [
    "MAX_PAGE_SIZE",
    "ComplianceResultResponse",
    "ComplianceResultsResponse",
    "HardeningProfileResponse",
    "HardeningProfilesResponse",
    "HardeningReportResponse",
    "HardeningReportsResponse",
    "HardeningResultResponse",
    "HardeningResultsResponse",
    "HardeningRunRequest",
    "HardeningRunResponse",
    "HardeningStatisticWindowResponse",
    "HardeningStatisticsResponse",
    "ProductionCertificationRequest",
    "ProductionCertificationResponse",
    "ProductionCertificationsResponse",
    "ProductionReadinessResponse",
    "SecurityFindingResponse",
    "SecurityFindingsResponse",
    "VulnerabilityScanResponse",
    "VulnerabilityScansResponse",
]
