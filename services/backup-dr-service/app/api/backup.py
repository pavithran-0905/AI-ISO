"""The 12 docs/065 REST endpoints.

**Every route derives its tenant from the token.** No query or body
parameter names an organization; see
:func:`app.api.deps.get_organization_id` for why that is not a
convenience.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from shared_core.logging.context import get_log_context

from app.api.deps import (
    CurrentUserId,
    DrTestServiceDep,
    FailoverServiceDep,
    JobServiceDep,
    OrganizationId,
    Repos,
    RestoreServiceDep,
    ScheduleServiceDep,
    require_administrator,
)
from app.failover.engine import HealthCheckResult
from app.models.backup import BackupJob, BackupSchedule
from app.models.enums import FailoverKind
from app.models.recovery import DrPlan
from app.schemas.backup import (
    MAX_PAGE_SIZE,
    DrPlanResponse,
    DrPlansResponse,
    DrTestRequest,
    DrTestResponse,
    FailoverRequest,
    FailoverResponse,
    JobCreateRequest,
    JobResponse,
    JobsResponse,
    PageInfo,
    ReportResponse,
    ReportsResponse,
    RestoreRequest,
    RestoreResponse,
    ScheduleCreateRequest,
    ScheduleResponse,
    SchedulesResponse,
    SnapshotResponse,
    SnapshotsResponse,
    StatisticsResponse,
    StatisticWindowResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse

router = APIRouter(prefix="/backup", tags=["Backup & Disaster Recovery"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _default_window(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(UTC)
    return end - timedelta(days=days), end


def _job_response(job: BackupJob) -> JobResponse:
    return JobResponse(
        id=job.id,
        target_id=job.target_id,
        schedule_id=job.schedule_id,
        parent_job_id=job.parent_job_id,
        backup_type=job.backup_type,
        status=job.status,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_ms=job.duration_ms,
        size_bytes=job.size_bytes,
        checksum=job.checksum,
        error_message=job.error_message,
    )


def _schedule_response(schedule: BackupSchedule) -> ScheduleResponse:
    return ScheduleResponse(
        id=schedule.id,
        target_id=schedule.target_id,
        backup_type=schedule.backup_type,
        frequency=schedule.frequency,
        cron_expression=schedule.cron_expression,
        is_enabled=schedule.is_enabled,
        next_run_at=schedule.next_run_at,
        last_run_at=schedule.last_run_at,
        retention_days=schedule.retention_days,
    )


def _dr_plan_response(plan: DrPlan) -> DrPlanResponse:
    return DrPlanResponse(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        status=plan.status,
        priority=plan.priority,
        rpo_minutes=plan.rpo_minutes,
        rto_minutes=plan.rto_minutes,
        is_active=plan.is_active,
        last_tested_at=plan.last_tested_at,
    )


# ---- GET/POST /backup/jobs -----------------------------------------------------------------


@router.get("/jobs", response_model=SuccessResponse[JobsResponse], summary="List backup jobs")
async def list_jobs(
    organization_id: OrganizationId,
    repos: Repos,
    target_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[JobsResponse]:
    rows = await repos.jobs.list_recent(organization_id, target_id=target_id, limit=limit)
    data = JobsResponse(jobs=[_job_response(row) for row in rows], total=len(rows), page=PageInfo())
    return SuccessResponse(message="Backup jobs retrieved.", data=data, meta=_meta())


@router.post(
    "/jobs",
    response_model=SuccessResponse[JobResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Start a backup job",
    dependencies=[Depends(require_administrator)],
)
async def create_job(
    organization_id: OrganizationId,
    repos: Repos,
    job_service: JobServiceDep,
    body: JobCreateRequest,
    _actor: CurrentUserId,
) -> SuccessResponse[JobResponse]:
    target = await repos.targets.require_in_org(organization_id, body.target_id)
    job = await job_service.start_job(
        organization_id,
        target=target,
        backup_type=body.backup_type,
        schedule_id=body.schedule_id,
        parent_job_id=body.parent_job_id,
        now=datetime.now(UTC),
    )
    return SuccessResponse(message="Backup job started.", data=_job_response(job), meta=_meta())


# ---- GET/POST /backup/schedules ------------------------------------------------------------


@router.get(
    "/schedules", response_model=SuccessResponse[SchedulesResponse], summary="List backup schedules"
)
async def list_schedules(
    organization_id: OrganizationId, repos: Repos
) -> SuccessResponse[SchedulesResponse]:
    rows = await repos.schedules.list_enabled(organization_id)
    data = SchedulesResponse(schedules=[_schedule_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Backup schedules retrieved.", data=data, meta=_meta())


@router.post(
    "/schedules",
    response_model=SuccessResponse[ScheduleResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a backup schedule",
    dependencies=[Depends(require_administrator)],
)
async def create_schedule(
    organization_id: OrganizationId,
    schedule_service: ScheduleServiceDep,
    body: ScheduleCreateRequest,
    actor: CurrentUserId,
) -> SuccessResponse[ScheduleResponse]:
    schedule = await schedule_service.create_schedule(
        organization_id,
        target_id=body.target_id,
        backup_type=body.backup_type,
        frequency=body.frequency,
        cron_expression=body.cron_expression,
        retention_days=body.retention_days,
        actor_id=actor,
        now=datetime.now(UTC),
    )
    return SuccessResponse(
        message="Backup schedule created.", data=_schedule_response(schedule), meta=_meta()
    )


# ---- GET /backup/snapshots -------------------------------------------------------------------


@router.get(
    "/snapshots", response_model=SuccessResponse[SnapshotsResponse], summary="List backup snapshots"
)
async def list_snapshots(
    organization_id: OrganizationId,
    repos: Repos,
    target_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[SnapshotsResponse]:
    rows = await repos.snapshots.list_recent(organization_id, target_id=target_id, limit=limit)
    data = SnapshotsResponse(
        snapshots=[
            SnapshotResponse(
                id=row.id,
                target_id=row.target_id,
                snapshot_kind=row.snapshot_kind,
                status=row.status,
                size_bytes=row.size_bytes,
                created_at_source=row.created_at_source,
                expires_at=row.expires_at,
                is_validated=row.is_validated,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Snapshots retrieved.", data=data, meta=_meta())


# ---- POST /backup/restore --------------------------------------------------------------------


@router.post(
    "/restore",
    response_model=SuccessResponse[RestoreResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Preview or run a restore",
)
async def restore(
    organization_id: OrganizationId,
    repos: Repos,
    restore_service: RestoreServiceDep,
    body: RestoreRequest,
    actor: CurrentUserId,
) -> SuccessResponse[RestoreResponse]:
    """Select a restore point and start (or preview) a restore job.

    ``is_preview`` requests are still persisted as a real ``RestoreJob``
    row with ``is_preview=True`` -- a preview is a real, auditable event,
    not a throwaway computation, since docs/065's own RESTORE VALIDATION
    and AUDIT requirements apply to it equally.
    """
    now = datetime.now(UTC)
    selection = await restore_service.select_point(
        body.target_id, requested_at=body.requested_at, now=now
    )
    if not selection.is_selected:
        data = RestoreResponse(
            restore_job_id=None,
            status=None,
            is_preview=body.is_preview,
            selected_point_at=None,
            refusal=selection.refusal,
            detail=selection.detail,
        )
        return SuccessResponse(
            message="No restore point could be selected.", data=data, meta=_meta()
        )

    assert selection.point is not None
    job = await restore_service.start_job(
        organization_id,
        source_archive_id=(
            UUID(selection.point.source_archive_id) if selection.point.source_archive_id else None
        ),
        restore_point_id=UUID(selection.point.point_id),
        restore_kind=body.restore_kind,
        target_ref=body.target_ref,
        is_preview=body.is_preview,
        requested_by=actor,
        now=now,
    )
    data = RestoreResponse(
        restore_job_id=job.id,
        status=job.status,
        is_preview=job.is_preview,
        selected_point_at=selection.point.available_at,
        refusal=None,
        detail=selection.detail,
    )
    return SuccessResponse(message="Restore job started.", data=data, meta=_meta())


# ---- POST /backup/failover / /backup/failback ------------------------------------------------


async def _run_failover(
    organization_id: UUID,
    failover_service: FailoverServiceDep,
    body: FailoverRequest,
    actor: str,
    *,
    kind_override: str | None = None,
) -> SuccessResponse[FailoverResponse]:
    kind = FailoverKind(kind_override) if kind_override else body.kind
    checks = [
        HealthCheckResult(check_name=c.check_name, is_healthy=c.is_healthy, detail=c.detail)
        for c in body.health_checks
    ]
    authorization = failover_service.authorize(kind, checks)
    if not authorization.is_authorized:
        data = FailoverResponse(
            failover_event_id=None,
            is_authorized=False,
            refusal=authorization.refusal,
            detail=authorization.detail,
            status=None,
        )
        return SuccessResponse(message="Failover was not authorized.", data=data, meta=_meta())

    event = await failover_service.initiate(
        organization_id,
        dr_plan_id=body.dr_plan_id,
        kind=kind,
        source_ref=body.source_ref,
        target_ref=body.target_ref,
        initiated_by=actor,
        health_checks=checks,
        now=datetime.now(UTC),
    )
    data = FailoverResponse(
        failover_event_id=event.id,
        is_authorized=True,
        refusal=None,
        detail=authorization.detail,
        status=event.status,
    )
    return SuccessResponse(message="Failover initiated.", data=data, meta=_meta())


@router.post(
    "/failover",
    response_model=SuccessResponse[FailoverResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a failover",
    dependencies=[Depends(require_administrator)],
)
async def failover(
    organization_id: OrganizationId,
    failover_service: FailoverServiceDep,
    body: FailoverRequest,
    actor: CurrentUserId,
) -> SuccessResponse[FailoverResponse]:
    return await _run_failover(organization_id, failover_service, body, actor)


@router.post(
    "/failback",
    response_model=SuccessResponse[FailoverResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Fail back to the original site",
    dependencies=[Depends(require_administrator)],
)
async def failback(
    organization_id: OrganizationId,
    failover_service: FailoverServiceDep,
    body: FailoverRequest,
    actor: CurrentUserId,
) -> SuccessResponse[FailoverResponse]:
    return await _run_failover(
        organization_id, failover_service, body, actor, kind_override="failback"
    )


# ---- GET /backup/dr-plans, POST /backup/dr-tests ------------------------------------------------


@router.get("/dr-plans", response_model=SuccessResponse[DrPlansResponse], summary="List DR plans")
async def list_dr_plans(
    organization_id: OrganizationId, repos: Repos
) -> SuccessResponse[DrPlansResponse]:
    rows = await repos.dr_plans.list_active(organization_id)
    data = DrPlansResponse(plans=[_dr_plan_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="DR plans retrieved.", data=data, meta=_meta())


@router.post(
    "/dr-tests",
    response_model=SuccessResponse[DrTestResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a DR test / drill result",
    dependencies=[Depends(require_administrator)],
)
async def create_dr_test(
    organization_id: OrganizationId,
    repos: Repos,
    dr_test_service: DrTestServiceDep,
    body: DrTestRequest,
) -> SuccessResponse[DrTestResponse]:
    plan = await repos.dr_plans.require_in_org(organization_id, body.dr_plan_id)
    now = datetime.now(UTC)
    test = await dr_test_service.run_test(
        organization_id,
        dr_plan=plan,
        test_kind=body.test_kind,
        achieved_rpo_minutes=body.achieved_rpo_minutes,
        achieved_rto_minutes=body.achieved_rto_minutes,
        findings=[],
        summary=body.summary,
        started_at=now,
        completed_at=now,
    )
    data = DrTestResponse(
        id=test.id,
        dr_plan_id=test.dr_plan_id,
        test_kind=test.test_kind,
        status=test.status,
        rpo_status=test.rpo_status,
        rto_status=test.rto_status,
        achieved_rpo_minutes=test.achieved_rpo_minutes,
        achieved_rto_minutes=test.achieved_rto_minutes,
        summary=test.summary,
    )
    return SuccessResponse(message="DR test recorded.", data=data, meta=_meta())


# ---- GET /backup/statistics ---------------------------------------------------------------------


@router.get(
    "/statistics",
    response_model=SuccessResponse[StatisticsResponse],
    summary="Backup/DR statistics",
)
async def get_statistics(
    organization_id: OrganizationId,
    repos: Repos,
    start: datetime | None = None,
    end: datetime | None = None,
) -> SuccessResponse[StatisticsResponse]:
    window_start, window_end = (start, end) if start and end else _default_window(7)
    rows = await repos.statistics.list_range(organization_id, start=window_start, end=window_end)
    data = StatisticsResponse(
        windows=[
            StatisticWindowResponse(
                window_start=row.window_start,
                window_end=row.window_end,
                jobs_completed=row.jobs_completed,
                jobs_failed=row.jobs_failed,
                bytes_backed_up=row.bytes_backed_up,
                restore_jobs_completed=row.restore_jobs_completed,
                restore_jobs_failed=row.restore_jobs_failed,
                rpo_compliant_count=row.rpo_compliant_count,
                rpo_violated_count=row.rpo_violated_count,
                rto_compliant_count=row.rto_compliant_count,
                rto_violated_count=row.rto_violated_count,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Statistics retrieved.", data=data, meta=_meta())


# ---- GET /backup/reports ---------------------------------------------------------------


@router.get(
    "/reports", response_model=SuccessResponse[ReportsResponse], summary="Generated reports"
)
async def list_reports(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> SuccessResponse[ReportsResponse]:
    rows = await repos.reports.list_recent(organization_id, limit=limit)
    data = ReportsResponse(
        reports=[
            ReportResponse(
                id=row.id,
                kind=row.kind,
                report_format=row.report_format,
                title=row.title,
                status=row.status,
                period_start=row.period_start,
                period_end=row.period_end,
                generated_at=row.generated_at,
                row_count=row.row_count,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Reports retrieved.", data=data, meta=_meta())


__all__ = ["router"]
