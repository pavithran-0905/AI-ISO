"""The 10 docs/075 REST endpoints.

**Every route requires an administrator role** -- see
``app.api.deps``'s own module docstring for why.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from shared_core.logging.context import get_log_context

from app.api.deps import (
    CurrentUserId,
    DeploymentJobServiceDep,
    InstallationSessionServiceDep,
    OrganizationId,
    PreflightServiceDep,
    Repos,
    RollbackServiceDep,
    StatisticsServiceDep,
    UpgradeServiceDep,
    require_administrator,
)
from app.models.deployment import DeploymentJob
from app.models.installation import InstallationSession
from app.models.reporting import DeploymentReport
from app.models.upgrade_rollback import RollbackHistory, UpgradeHistory
from app.models.validation import PreflightResult
from app.models.verification import VerificationResult
from app.schemas.deployment import (
    MAX_PAGE_SIZE,
    DeploymentJobResponse,
    DeployRequest,
    InstallationSessionResponse,
    InstallStartRequest,
    PreflightResultResponse,
    PreflightValidateRequest,
    ReportResponse,
    ReportsResponse,
    RollbackHistoryResponse,
    RollbackRequest,
    StatisticsResponse,
    StatisticWindowResponse,
    UpgradeHistoryResponse,
    UpgradeRequest,
    VerificationResultResponse,
    VerificationResultsResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse

router = APIRouter(
    tags=["Installation & Deployment"], dependencies=[Depends(require_administrator)]
)


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _session_response(session: InstallationSession) -> InstallationSessionResponse:
    return InstallationSessionResponse(
        id=session.id,
        mode=session.mode,
        status=session.status,
        started_at=session.started_at,
        completed_at=session.completed_at,
    )


def _job_response(job: DeploymentJob) -> DeploymentJobResponse:
    return DeploymentJobResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
    )


def _preflight_response(result: PreflightResult) -> PreflightResultResponse:
    return PreflightResultResponse(
        id=result.id,
        check_type=result.check_type,
        status=result.status,
        detail=result.detail,
        checked_at=result.checked_at,
    )


def _upgrade_response(history: UpgradeHistory) -> UpgradeHistoryResponse:
    return UpgradeHistoryResponse(
        id=history.id,
        deployment_job_id=history.deployment_job_id,
        from_version=history.from_version,
        to_version=history.to_version,
        status=history.status,
        started_at=history.started_at,
        completed_at=history.completed_at,
    )


def _rollback_response(history: RollbackHistory) -> RollbackHistoryResponse:
    return RollbackHistoryResponse(
        id=history.id,
        deployment_job_id=history.deployment_job_id,
        from_version=history.from_version,
        to_version=history.to_version,
        reason=history.reason,
        status=history.status,
        started_at=history.started_at,
        completed_at=history.completed_at,
    )


def _verification_response(result: VerificationResult) -> VerificationResultResponse:
    return VerificationResultResponse(
        id=result.id,
        check_type=result.check_type,
        status=result.status,
        detail=result.detail,
        verified_at=result.verified_at,
    )


def _report_response(report: DeploymentReport) -> ReportResponse:
    return ReportResponse(
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


# ---- POST /install/start, GET /install/status ------------------------------------------------


@router.post(
    "/install/start",
    response_model=SuccessResponse[InstallationSessionResponse],
    summary="Begin a new installation session",
)
async def install_start(
    organization_id: OrganizationId,
    actor: CurrentUserId,
    service: InstallationSessionServiceDep,
    body: InstallStartRequest,
) -> SuccessResponse[InstallationSessionResponse]:
    session = await service.create(organization_id, mode=body.mode, actor_id=actor)
    session = await service.start(session, now=datetime.now(UTC))
    return SuccessResponse(
        message="Installation started.", data=_session_response(session), meta=_meta()
    )


@router.get(
    "/install/status",
    response_model=SuccessResponse[InstallationSessionResponse],
    summary="Check an installation session's own status",
)
async def install_status(
    organization_id: OrganizationId, repos: Repos, installation_session_id: UUID
) -> SuccessResponse[InstallationSessionResponse]:
    session = await repos.installation_sessions.require_by_id(installation_session_id)
    return SuccessResponse(
        message="Installation status retrieved.", data=_session_response(session), meta=_meta()
    )


# ---- POST /install/validate --------------------------------------------------------------


@router.post(
    "/install/validate",
    response_model=SuccessResponse[PreflightResultResponse],
    summary="Record a pre-flight infrastructure readiness check outcome",
)
async def install_validate(
    organization_id: OrganizationId, service: PreflightServiceDep, body: PreflightValidateRequest
) -> SuccessResponse[PreflightResultResponse]:
    result = await service.record_result(
        organization_id,
        check_type=body.check_type,
        status=body.status,
        detail=body.detail,
        installation_session_id=body.installation_session_id,
        now=datetime.now(UTC),
    )
    return SuccessResponse(
        message="Validation recorded.", data=_preflight_response(result), meta=_meta()
    )


# ---- POST /deploy, GET /deploy/status ------------------------------------------------------


@router.post(
    "/deploy",
    response_model=SuccessResponse[DeploymentJobResponse],
    summary="Start a deployment job",
)
async def deploy(
    organization_id: OrganizationId, service: DeploymentJobServiceDep, body: DeployRequest
) -> SuccessResponse[DeploymentJobResponse]:
    job = await service.create(
        organization_id, deployment_profile_id=body.deployment_profile_id, job_type=body.job_type
    )
    job = await service.start(job, now=datetime.now(UTC))
    return SuccessResponse(message="Deployment started.", data=_job_response(job), meta=_meta())


@router.get(
    "/deploy/status",
    response_model=SuccessResponse[DeploymentJobResponse],
    summary="Check a deployment job's own status",
)
async def deploy_status(
    organization_id: OrganizationId, repos: Repos, deployment_job_id: UUID
) -> SuccessResponse[DeploymentJobResponse]:
    job = await repos.jobs.require_by_id(deployment_job_id)
    return SuccessResponse(
        message="Deployment status retrieved.", data=_job_response(job), meta=_meta()
    )


# ---- POST /upgrade -----------------------------------------------------------------------


@router.post(
    "/upgrade",
    response_model=SuccessResponse[UpgradeHistoryResponse],
    summary="Initiate a platform upgrade",
)
async def upgrade(
    organization_id: OrganizationId, service: UpgradeServiceDep, body: UpgradeRequest
) -> SuccessResponse[UpgradeHistoryResponse]:
    history = await service.initiate(
        organization_id,
        deployment_profile_id=body.deployment_profile_id,
        from_version=body.from_version,
        to_version=body.to_version,
        now=datetime.now(UTC),
    )
    return SuccessResponse(
        message="Upgrade started.", data=_upgrade_response(history), meta=_meta()
    )


# ---- POST /rollback ----------------------------------------------------------------------


@router.post(
    "/rollback",
    response_model=SuccessResponse[RollbackHistoryResponse],
    summary="Initiate a platform rollback",
)
async def rollback(
    organization_id: OrganizationId,
    repos: Repos,
    service: RollbackServiceDep,
    body: RollbackRequest,
) -> SuccessResponse[RollbackHistoryResponse]:
    available_versions = [
        version.version_label for version in await repos.versions.list_all(organization_id)
    ]
    history = await service.initiate(
        organization_id,
        deployment_profile_id=body.deployment_profile_id,
        current_version=body.current_version,
        target_version=body.target_version,
        available_versions=available_versions,
        reason=body.reason,
        now=datetime.now(UTC),
    )
    return SuccessResponse(
        message="Rollback started.", data=_rollback_response(history), meta=_meta()
    )


# ---- GET /verification --------------------------------------------------------------------


@router.get(
    "/verification",
    response_model=SuccessResponse[VerificationResultsResponse],
    summary="List recent post-install/post-upgrade verification results",
)
async def verification(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[VerificationResultsResponse]:
    rows = await repos.verification_results.list_recent(organization_id, limit=limit)
    data = VerificationResultsResponse(
        results=[_verification_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Verification results retrieved.", data=data, meta=_meta())


# ---- GET /reports -------------------------------------------------------------------------


@router.get(
    "/reports",
    response_model=SuccessResponse[ReportsResponse],
    summary="Generated installation/deployment reports",
)
async def reports(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> SuccessResponse[ReportsResponse]:
    rows = await repos.reports.list_recent(organization_id, limit=limit)
    data = ReportsResponse(reports=[_report_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Reports retrieved.", data=data, meta=_meta())


# ---- GET /statistics -----------------------------------------------------------------------


@router.get(
    "/statistics",
    response_model=SuccessResponse[StatisticsResponse],
    summary="Installation/deployment statistics",
)
async def statistics(
    organization_id: OrganizationId, service: StatisticsServiceDep, since: datetime | None = None
) -> SuccessResponse[StatisticsResponse]:
    window_since = since or (datetime.now(UTC) - timedelta(days=7))
    rows = await service.list_range(organization_id, since=window_since)
    data = StatisticsResponse(
        windows=[
            StatisticWindowResponse(
                window_start=row.window_start,
                window_end=row.window_end,
                installation_count=row.installation_count,
                deployment_count=row.deployment_count,
                upgrade_count=row.upgrade_count,
                rollback_count=row.rollback_count,
                validation_failure_count=row.validation_failure_count,
                success_count=row.success_count,
                failure_count=row.failure_count,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Statistics retrieved.", data=data, meta=_meta())


__all__ = ["router"]
