"""The 11 docs/079 REST endpoints.

**Every route requires an administrator role** -- see
``app.api.deps``'s own module docstring for why.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from shared_core.logging.context import get_log_context

from app.api.deps import (
    HardeningRunServiceDep,
    OrganizationId,
    ProductionCertificationServiceDep,
    Repos,
    ServiceSettings,
    require_administrator,
)
from app.models.certification import ProductionCertification
from app.models.compliance import ComplianceResult
from app.models.hardening_definitions import HardeningProfile
from app.models.hardening_execution import HardeningResult, HardeningRun
from app.models.reporting import HardeningReport
from app.models.security_findings import SecurityFinding
from app.models.vulnerabilities import VulnerabilityScan
from app.schemas.hardening import (
    MAX_PAGE_SIZE,
    ComplianceResultResponse,
    ComplianceResultsResponse,
    HardeningProfileResponse,
    HardeningProfilesResponse,
    HardeningReportResponse,
    HardeningReportsResponse,
    HardeningResultResponse,
    HardeningResultsResponse,
    HardeningRunRequest,
    HardeningRunResponse,
    HardeningStatisticsResponse,
    HardeningStatisticWindowResponse,
    ProductionCertificationRequest,
    ProductionCertificationResponse,
    ProductionCertificationsResponse,
    ProductionReadinessResponse,
    SecurityFindingResponse,
    SecurityFindingsResponse,
    VulnerabilityScanResponse,
    VulnerabilityScansResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse
from app.services.production_readiness import ProductionReadinessService
from app.services.statistics import StatisticsService

router = APIRouter(tags=["Production Hardening"], dependencies=[Depends(require_administrator)])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _profile_response(profile: HardeningProfile) -> HardeningProfileResponse:
    return HardeningProfileResponse(
        id=profile.id,
        name=profile.name,
        target_type=profile.target_type,
        benchmark=profile.benchmark,
        description=profile.description,
        is_enabled=profile.is_enabled,
    )


def _run_response(run: HardeningRun) -> HardeningRunResponse:
    return HardeningRunResponse(
        id=run.id,
        hardening_profile_id=run.hardening_profile_id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _result_response(result: HardeningResult) -> HardeningResultResponse:
    return HardeningResultResponse(
        id=result.id,
        hardening_run_id=result.hardening_run_id,
        check_name=result.check_name,
        status=result.status,
        detail=result.detail,
    )


def _finding_response(finding: SecurityFinding) -> SecurityFindingResponse:
    return SecurityFindingResponse(
        id=finding.id,
        target_type=finding.target_type,
        severity=finding.severity,
        title=finding.title,
        detail=finding.detail,
        status=finding.status,
    )


def _vulnerability_response(scan: VulnerabilityScan) -> VulnerabilityScanResponse:
    return VulnerabilityScanResponse(
        id=scan.id,
        scan_type=scan.scan_type,
        cve_id=scan.cve_id,
        severity=scan.severity,
        package_name=scan.package_name,
        package_version=scan.package_version,
        status=scan.status,
    )


def _certification_response(
    certification: ProductionCertification,
) -> ProductionCertificationResponse:
    return ProductionCertificationResponse(
        id=certification.id,
        name=certification.name,
        status=certification.status,
        risk_score=certification.risk_score,
        granted_at=certification.granted_at,
        expires_at=certification.expires_at,
    )


def _compliance_response(result: ComplianceResult) -> ComplianceResultResponse:
    return ComplianceResultResponse(
        id=result.id,
        framework=result.framework,
        control_id=result.control_id,
        is_compliant=result.is_compliant,
        evaluated_at=result.evaluated_at,
    )


def _report_response(report: HardeningReport) -> HardeningReportResponse:
    return HardeningReportResponse(
        id=report.id,
        kind=report.kind,
        report_format=str(report.report_format),
        title=report.title,
        status=str(report.status),
        period_start=report.period_start,
        period_end=report.period_end,
        generated_at=report.generated_at,
        row_count=report.row_count,
    )


# ---- GET /hardening ---------------------------------------------------------------------


@router.get(
    "/hardening",
    response_model=SuccessResponse[HardeningProfilesResponse],
    summary="List hardening profiles",
)
async def list_hardening_profiles(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[HardeningProfilesResponse]:
    rows = await repos.hardening_profiles.list_all(organization_id, limit=limit)
    data = HardeningProfilesResponse(
        profiles=[_profile_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Hardening profiles retrieved.", data=data, meta=_meta())


# ---- POST /hardening/run ----------------------------------------------------------------


@router.post(
    "/hardening/run",
    response_model=SuccessResponse[HardeningRunResponse],
    summary="Start a hardening run",
)
async def run_hardening(
    organization_id: OrganizationId, service: HardeningRunServiceDep, body: HardeningRunRequest
) -> SuccessResponse[HardeningRunResponse]:
    run = await service.create(organization_id, hardening_profile_id=body.hardening_profile_id)
    run = await service.start(run, now=datetime.now(UTC))
    return SuccessResponse(message="Hardening run started.", data=_run_response(run), meta=_meta())


# ---- GET /hardening/results -------------------------------------------------------------


@router.get(
    "/hardening/results",
    response_model=SuccessResponse[HardeningResultsResponse],
    summary="List recent hardening check results",
)
async def list_hardening_results(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[HardeningResultsResponse]:
    rows = await repos.hardening_results.list_recent(organization_id, limit=limit)
    data = HardeningResultsResponse(
        results=[_result_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Hardening results retrieved.", data=data, meta=_meta())


# ---- GET /security/findings -------------------------------------------------------------


@router.get(
    "/security/findings",
    response_model=SuccessResponse[SecurityFindingsResponse],
    summary="List security findings",
)
async def list_security_findings(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[SecurityFindingsResponse]:
    rows = await repos.security_findings.list_all(organization_id, limit=limit)
    data = SecurityFindingsResponse(
        findings=[_finding_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Security findings retrieved.", data=data, meta=_meta())


# ---- GET /vulnerabilities ----------------------------------------------------------------


@router.get(
    "/vulnerabilities",
    response_model=SuccessResponse[VulnerabilityScansResponse],
    summary="List vulnerability scans",
)
async def list_vulnerabilities(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[VulnerabilityScansResponse]:
    rows = await repos.vulnerability_scans.list_all(organization_id, limit=limit)
    data = VulnerabilityScansResponse(
        vulnerabilities=[_vulnerability_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Vulnerability scans retrieved.", data=data, meta=_meta())


# ---- GET/POST /certifications -------------------------------------------------------------


@router.get(
    "/certifications",
    response_model=SuccessResponse[ProductionCertificationsResponse],
    summary="List production certifications",
)
async def list_certifications(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[ProductionCertificationsResponse]:
    rows = await repos.production_certifications.list_all(organization_id, limit=limit)
    data = ProductionCertificationsResponse(
        certifications=[_certification_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Production certifications retrieved.", data=data, meta=_meta())


@router.post(
    "/certifications",
    response_model=SuccessResponse[ProductionCertificationResponse],
    summary="Evaluate and grant (or deny) a production certification",
)
async def create_certification(
    organization_id: OrganizationId,
    service: ProductionCertificationServiceDep,
    settings: ServiceSettings,
    body: ProductionCertificationRequest,
) -> SuccessResponse[ProductionCertificationResponse]:
    certification = await service.evaluate_and_create(
        organization_id,
        name=body.name,
        hardening_rate=body.hardening_rate,
        compliance_rate=body.compliance_rate,
        readiness_rate=body.readiness_rate,
        risk_threshold=settings.certification_risk_threshold,
        now=datetime.now(UTC),
    )
    return SuccessResponse(
        message="Production certification evaluated.",
        data=_certification_response(certification),
        meta=_meta(),
    )


# ---- GET /compliance ---------------------------------------------------------------------


@router.get(
    "/compliance",
    response_model=SuccessResponse[ComplianceResultsResponse],
    summary="List compliance results",
)
async def list_compliance(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[ComplianceResultsResponse]:
    rows = await repos.compliance_results.list_all(organization_id, limit=limit)
    data = ComplianceResultsResponse(
        results=[_compliance_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Compliance results retrieved.", data=data, meta=_meta())


# ---- GET /production-readiness ------------------------------------------------------------


@router.get(
    "/production-readiness",
    response_model=SuccessResponse[ProductionReadinessResponse],
    summary="Compute aggregate production readiness",
)
async def production_readiness(
    organization_id: OrganizationId, repos: Repos, settings: ServiceSettings
) -> SuccessResponse[ProductionReadinessResponse]:
    service = ProductionReadinessService(repos)
    result = await service.compute(
        organization_id, threshold=settings.production_readiness_threshold
    )
    data = ProductionReadinessResponse(
        score=result.score,
        is_ready=result.is_ready,
        hardening_rate=result.hardening_rate,
        compliance_rate=result.compliance_rate,
        operational_readiness_rate=result.operational_readiness_rate,
        disaster_recovery_rate=result.disaster_recovery_rate,
    )
    return SuccessResponse(message="Production readiness computed.", data=data, meta=_meta())


# ---- GET /reports ------------------------------------------------------------------------


@router.get(
    "/reports",
    response_model=SuccessResponse[HardeningReportsResponse],
    summary="Generated hardening reports",
)
async def list_reports(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> SuccessResponse[HardeningReportsResponse]:
    rows = await repos.reports.list_recent(organization_id, limit=limit)
    data = HardeningReportsResponse(
        reports=[_report_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Reports retrieved.", data=data, meta=_meta())


# ---- GET /statistics ---------------------------------------------------------------------


@router.get(
    "/statistics",
    response_model=SuccessResponse[HardeningStatisticsResponse],
    summary="Hardening activity statistics",
)
async def statistics(
    organization_id: OrganizationId, repos: Repos, since: datetime | None = None
) -> SuccessResponse[HardeningStatisticsResponse]:
    service = StatisticsService(repos.statistics)
    window_since = since or (datetime.now(UTC) - timedelta(days=7))
    rows = await service.list_range(organization_id, since=window_since)
    data = HardeningStatisticsResponse(
        windows=[
            HardeningStatisticWindowResponse(
                window_start=row.window_start,
                window_end=row.window_end,
                hardening_run_count=row.hardening_run_count,
                security_finding_count=row.security_finding_count,
                vulnerability_count=row.vulnerability_count,
                avg_hardening_score=row.avg_hardening_score,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Statistics retrieved.", data=data, meta=_meta())


__all__ = ["router"]
