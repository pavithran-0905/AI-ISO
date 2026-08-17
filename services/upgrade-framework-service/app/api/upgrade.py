"""The 10 docs/076 REST endpoints.

**Every route requires an administrator role** -- see
``app.api.deps``'s own module docstring for why.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from shared_core.logging.context import get_log_context

from app.api.deps import (
    OrganizationId,
    Repos,
    RollbackServiceDep,
    StatisticsServiceDep,
    UpgradeExecutionServiceDep,
    require_administrator,
)
from app.models.releases import ReleaseChannel, ReleaseVersion
from app.models.reporting import UpgradeReport
from app.models.upgrade import UpgradeHistory, UpgradeJob
from app.schemas.response import ResponseMeta, SuccessResponse
from app.schemas.upgrade import (
    MAX_PAGE_SIZE,
    CompatibilityEntriesResponse,
    CompatibilityEntryResponse,
    ReleaseChannelResponse,
    ReleaseChannelsResponse,
    ReleaseVersionResponse,
    ReleaseVersionsResponse,
    ReportResponse,
    ReportsResponse,
    RollbackHistoryResponse,
    RollbackRequest,
    SimulateRequest,
    SimulationResponse,
    StatisticsResponse,
    StatisticWindowResponse,
    UpgradeHistoryEntryResponse,
    UpgradeHistoryListResponse,
    UpgradeJobResponse,
    UpgradeJobsResponse,
    UpgradeRequest,
)
from app.services.simulation import SimulationService

router = APIRouter(tags=["Upgrade Framework"], dependencies=[Depends(require_administrator)])

_simulation_service = SimulationService()


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _release_version_response(version: ReleaseVersion) -> ReleaseVersionResponse:
    return ReleaseVersionResponse(
        id=version.id,
        release_channel_id=version.release_channel_id,
        version_label=version.version_label,
        released_at=version.released_at,
        is_current=version.is_current,
    )


def _release_channel_response(channel: ReleaseChannel) -> ReleaseChannelResponse:
    return ReleaseChannelResponse(
        id=channel.id,
        name=channel.name,
        channel_type=channel.channel_type,
        is_enabled=channel.is_enabled,
    )


def _job_response(job: UpgradeJob) -> UpgradeJobResponse:
    return UpgradeJobResponse(
        id=job.id,
        upgrade_plan_id=job.upgrade_plan_id,
        status=job.status,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
    )


def _history_response(entry: UpgradeHistory) -> UpgradeHistoryEntryResponse:
    return UpgradeHistoryEntryResponse(
        id=entry.id,
        upgrade_job_id=entry.upgrade_job_id,
        event_type=entry.event_type,
        detail=entry.detail,
        occurred_at=entry.occurred_at,
    )


def _report_response(report: UpgradeReport) -> ReportResponse:
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


# ---- GET /releases -------------------------------------------------------------------------


@router.get(
    "/releases",
    response_model=SuccessResponse[ReleaseVersionsResponse],
    summary="List published releases",
)
async def list_releases(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[ReleaseVersionsResponse]:
    rows = await repos.versions.list_all(organization_id, limit=limit)
    data = ReleaseVersionsResponse(
        releases=[_release_version_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Releases retrieved.", data=data, meta=_meta())


# ---- GET /channels ------------------------------------------------------------------------


@router.get(
    "/channels",
    response_model=SuccessResponse[ReleaseChannelsResponse],
    summary="List release channels",
)
async def list_channels(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[ReleaseChannelsResponse]:
    rows = await repos.channels.list_all(organization_id, limit=limit)
    data = ReleaseChannelsResponse(
        channels=[_release_channel_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Release channels retrieved.", data=data, meta=_meta())


# ---- POST /upgrade -------------------------------------------------------------------------


@router.post(
    "/upgrade",
    response_model=SuccessResponse[UpgradeJobResponse],
    summary="Schedule and start an upgrade",
)
async def start_upgrade(
    organization_id: OrganizationId, service: UpgradeExecutionServiceDep, body: UpgradeRequest
) -> SuccessResponse[UpgradeJobResponse]:
    job = await service.schedule_and_start(
        organization_id,
        upgrade_plan_id=body.upgrade_plan_id,
        plan_name=body.plan_name,
        now=datetime.now(UTC),
    )
    return SuccessResponse(message="Upgrade started.", data=_job_response(job), meta=_meta())


# ---- POST /upgrade/simulate ----------------------------------------------------------------


@router.post(
    "/upgrade/simulate",
    response_model=SuccessResponse[SimulationResponse],
    summary="Dry-run an upgrade",
)
async def simulate_upgrade(
    organization_id: OrganizationId, body: SimulateRequest
) -> SuccessResponse[SimulationResponse]:
    outcome = _simulation_service.simulate(
        compatibility_results=body.compatibility_results,
        dependency_results=body.dependency_results,
        target_count=body.target_count,
        seconds_per_target=body.seconds_per_target,
    )
    data = SimulationResponse(
        risk_level=outcome.risk_level,
        estimated_duration_seconds=outcome.estimated_duration_seconds,
        check_count=outcome.check_count,
    )
    return SuccessResponse(message="Simulation completed.", data=data, meta=_meta())


# ---- GET /upgrade/jobs --------------------------------------------------------------------


@router.get(
    "/upgrade/jobs",
    response_model=SuccessResponse[UpgradeJobsResponse],
    summary="List recent upgrade jobs",
)
async def list_upgrade_jobs(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[UpgradeJobsResponse]:
    rows = await repos.jobs.list_recent(organization_id, limit=limit)
    data = UpgradeJobsResponse(jobs=[_job_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Upgrade jobs retrieved.", data=data, meta=_meta())


# ---- GET /upgrade/history -----------------------------------------------------------------


@router.get(
    "/upgrade/history",
    response_model=SuccessResponse[UpgradeHistoryListResponse],
    summary="List upgrade history",
)
async def list_upgrade_history(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[UpgradeHistoryListResponse]:
    rows = await repos.history.list_recent(organization_id, limit=limit)
    data = UpgradeHistoryListResponse(
        entries=[_history_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Upgrade history retrieved.", data=data, meta=_meta())


# ---- POST /rollback -----------------------------------------------------------------------


@router.post(
    "/rollback",
    response_model=SuccessResponse[RollbackHistoryResponse],
    summary="Initiate an upgrade rollback",
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
        upgrade_plan_id=body.upgrade_plan_id,
        current_version=body.current_version,
        target_version=body.target_version,
        available_versions=available_versions,
        reason=body.reason,
        now=datetime.now(UTC),
    )
    return SuccessResponse(
        message="Rollback started.",
        data=RollbackHistoryResponse(
            id=history.id,
            upgrade_job_id=history.upgrade_job_id,
            from_version=history.from_version,
            to_version=history.to_version,
            reason=history.reason,
            status=history.status,
            started_at=history.started_at,
            completed_at=history.completed_at,
        ),
        meta=_meta(),
    )


# ---- GET /compatibility -------------------------------------------------------------------


@router.get(
    "/compatibility",
    response_model=SuccessResponse[CompatibilityEntriesResponse],
    summary="List compatibility matrix entries",
)
async def list_compatibility(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[CompatibilityEntriesResponse]:
    rows = await repos.compatibility.list_all(organization_id, limit=limit)
    data = CompatibilityEntriesResponse(
        entries=[
            CompatibilityEntryResponse(
                id=row.id,
                from_version=row.from_version,
                to_version=row.to_version,
                compatibility_type=row.compatibility_type,
                status=row.status,
                detail=row.detail,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Compatibility matrix retrieved.", data=data, meta=_meta())


# ---- GET /reports -------------------------------------------------------------------------


@router.get(
    "/reports",
    response_model=SuccessResponse[ReportsResponse],
    summary="Generated upgrade/migration/rollback reports",
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
    summary="Upgrade/rollback/migration statistics",
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
                upgrade_count=row.upgrade_count,
                rollback_count=row.rollback_count,
                migration_count=row.migration_count,
                compatibility_failure_count=row.compatibility_failure_count,
                success_count=row.success_count,
                failure_count=row.failure_count,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Statistics retrieved.", data=data, meta=_meta())


__all__ = ["router"]
