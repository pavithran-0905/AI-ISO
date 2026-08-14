"""The 16 docs/070 REST endpoints.

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
from shared_core.exceptions.conflict import ConflictError
from shared_core.logging.context import get_log_context

from app.api.deps import (
    CurrentUserId,
    DashboardServiceDep,
    DiagnosticsServiceDep,
    FeatureFlagServiceDep,
    JobServiceDep,
    OrganizationId,
    PlatformSettingServiceDep,
    Repos,
    TenantServiceDep,
    require_administrator,
)
from app.models.enums import TenantStatus
from app.models.jobs import SystemJob
from app.models.settings import FeatureFlag
from app.models.tenants import Tenant
from app.schemas.admin import (
    MAX_PAGE_SIZE,
    DashboardResponse,
    DiagnosticResponse,
    DiagnosticsResponse,
    FeatureFlagCreateRequest,
    FeatureFlagResponse,
    FeatureFlagsResponse,
    FeatureFlagUpdateRequest,
    HealthCheckComponentResponse,
    JobCreateRequest,
    JobResponse,
    JobsResponse,
    PageInfo,
    PlatformHealthResponse,
    ReportResponse,
    ReportsResponse,
    SettingResponse,
    SettingsResponse,
    SettingUpsertRequest,
    StatisticsResponse,
    StatisticWindowResponse,
    TenantCreateRequest,
    TenantResponse,
    TenantsResponse,
    TenantUpdateRequest,
)
from app.schemas.response import ResponseMeta, SuccessResponse
from app.services.tenants import TransitionRefusedError

router = APIRouter(tags=["Administration Portal"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _default_window(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(UTC)
    return end - timedelta(days=days), end


def _tenant_response(tenant: Tenant) -> TenantResponse:
    return TenantResponse(
        id=tenant.id,
        organization_ref_id=tenant.organization_ref_id,
        name=tenant.name,
        status=tenant.status,
        isolation_key=tenant.isolation_key,
    )


def _feature_flag_response(flag: FeatureFlag) -> FeatureFlagResponse:
    return FeatureFlagResponse(
        id=flag.id,
        name=flag.name,
        scope=flag.scope,
        target_ref=flag.target_ref,
        is_enabled=flag.is_enabled,
        is_killed=flag.is_killed,
        rollout_percentage=flag.rollout_percentage,
    )


def _job_response(job: SystemJob) -> JobResponse:
    return JobResponse(
        id=job.id,
        job_key=job.job_key,
        status=job.status,
        priority=job.priority,
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        queued_at=job.queued_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


# ---- GET /admin/dashboard ---------------------------------------------------------------------


@router.get(
    "/admin/dashboard",
    response_model=SuccessResponse[DashboardResponse],
    summary="Platform dashboard",
)
async def get_dashboard(
    organization_id: OrganizationId, dashboard_service: DashboardServiceDep
) -> SuccessResponse[DashboardResponse]:
    snapshot = await dashboard_service.snapshot(organization_id)
    data = DashboardResponse(
        tenant_count=snapshot.tenant_count,
        active_tenant_count=snapshot.active_tenant_count,
        organization_count=snapshot.organization_count,
        running_job_count=snapshot.running_job_count,
        failed_job_count=snapshot.failed_job_count,
        open_maintenance_window_count=snapshot.open_maintenance_window_count,
        overall_health=snapshot.overall_health,
    )
    return SuccessResponse(message="Dashboard retrieved.", data=data, meta=_meta())


# ---- GET/PUT /admin/settings ---------------------------------------------------------------------


@router.get(
    "/admin/settings",
    response_model=SuccessResponse[SettingsResponse],
    summary="List platform settings",
)
async def list_settings(
    organization_id: OrganizationId, repos: Repos
) -> SuccessResponse[SettingsResponse]:
    rows = await repos.platform_settings.list_all(organization_id)
    data = SettingsResponse(
        settings=[
            SettingResponse(id=row.id, key=row.key, value=row.value, description=row.description)
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Settings retrieved.", data=data, meta=_meta())


@router.put(
    "/admin/settings",
    response_model=SuccessResponse[SettingResponse],
    summary="Create or update one platform setting",
    dependencies=[Depends(require_administrator)],
)
async def update_settings(
    organization_id: OrganizationId,
    setting_service: PlatformSettingServiceDep,
    body: SettingUpsertRequest,
) -> SuccessResponse[SettingResponse]:
    setting = await setting_service.upsert(
        organization_id, key=body.key, value=body.value, description=body.description
    )
    data = SettingResponse(
        id=setting.id, key=setting.key, value=setting.value, description=setting.description
    )
    return SuccessResponse(message="Setting saved.", data=data, meta=_meta())


# ---- GET/POST /admin/tenants, PUT/DELETE /admin/tenants/{id} -------------------------------------


@router.get(
    "/admin/tenants", response_model=SuccessResponse[TenantsResponse], summary="List tenants"
)
async def list_tenants(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[TenantsResponse]:
    rows = await repos.tenants.list_recent(organization_id, limit=limit)
    data = TenantsResponse(
        tenants=[_tenant_response(row) for row in rows], total=len(rows), page=PageInfo()
    )
    return SuccessResponse(message="Tenants retrieved.", data=data, meta=_meta())


@router.post(
    "/admin/tenants",
    response_model=SuccessResponse[TenantResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Provision a tenant",
    dependencies=[Depends(require_administrator)],
)
async def create_tenant(
    organization_id: OrganizationId,
    tenant_service: TenantServiceDep,
    body: TenantCreateRequest,
    actor: CurrentUserId,
) -> SuccessResponse[TenantResponse]:
    tenant = await tenant_service.provision(
        organization_id,
        organization_ref_id=body.organization_ref_id,
        name=body.name,
        actor_id=actor,
        now=datetime.now(UTC),
    )
    return SuccessResponse(
        message="Tenant provisioned.", data=_tenant_response(tenant), meta=_meta()
    )


@router.put(
    "/admin/tenants/{tenant_id}",
    response_model=SuccessResponse[TenantResponse],
    summary="Advance a tenant's lifecycle",
    dependencies=[Depends(require_administrator)],
)
async def update_tenant(
    organization_id: OrganizationId,
    repos: Repos,
    tenant_service: TenantServiceDep,
    tenant_id: UUID,
    body: TenantUpdateRequest,
    actor: CurrentUserId,
) -> SuccessResponse[TenantResponse]:
    tenant = await repos.tenants.require_in_org(organization_id, tenant_id)
    try:
        tenant = await tenant_service.transition(
            tenant, target=body.target_status, actor_id=actor, now=datetime.now(UTC)
        )
    except TransitionRefusedError as exc:
        raise ConflictError(
            f"Tenant {tenant_id!s} cannot move to {body.target_status.value}: {exc.result.detail}"
        ) from exc
    return SuccessResponse(message="Tenant updated.", data=_tenant_response(tenant), meta=_meta())


@router.delete(
    "/admin/tenants/{tenant_id}",
    response_model=SuccessResponse[TenantResponse],
    summary="Start deleting a tenant",
    dependencies=[Depends(require_administrator)],
)
async def delete_tenant(
    organization_id: OrganizationId,
    repos: Repos,
    tenant_service: TenantServiceDep,
    tenant_id: UUID,
    actor: CurrentUserId,
) -> SuccessResponse[TenantResponse]:
    tenant = await repos.tenants.require_in_org(organization_id, tenant_id)
    try:
        tenant = await tenant_service.transition(
            tenant, target=TenantStatus.DELETING, actor_id=actor, now=datetime.now(UTC)
        )
    except TransitionRefusedError as exc:
        raise ConflictError(
            f"Tenant {tenant_id!s} cannot start deleting right now: {exc.result.detail}"
        ) from exc
    return SuccessResponse(
        message="Tenant deletion started.", data=_tenant_response(tenant), meta=_meta()
    )


# ---- GET/POST /admin/feature-flags, PUT /admin/feature-flags/{id} --------------------------------


@router.get(
    "/admin/feature-flags",
    response_model=SuccessResponse[FeatureFlagsResponse],
    summary="List feature flags",
)
async def list_feature_flags(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[FeatureFlagsResponse]:
    rows = await repos.feature_flags.list_recent(organization_id, limit=limit)
    data = FeatureFlagsResponse(
        feature_flags=[_feature_flag_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Feature flags retrieved.", data=data, meta=_meta())


@router.post(
    "/admin/feature-flags",
    response_model=SuccessResponse[FeatureFlagResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a feature flag",
    dependencies=[Depends(require_administrator)],
)
async def create_feature_flag(
    organization_id: OrganizationId,
    flag_service: FeatureFlagServiceDep,
    body: FeatureFlagCreateRequest,
) -> SuccessResponse[FeatureFlagResponse]:
    flag = await flag_service.create_flag(
        organization_id,
        name=body.name,
        scope=body.scope,
        target_ref=body.target_ref,
        rollout_percentage=body.rollout_percentage,
    )
    return SuccessResponse(
        message="Feature flag created.", data=_feature_flag_response(flag), meta=_meta()
    )


@router.put(
    "/admin/feature-flags/{flag_id}",
    response_model=SuccessResponse[FeatureFlagResponse],
    summary="Update a feature flag",
    dependencies=[Depends(require_administrator)],
)
async def update_feature_flag(
    organization_id: OrganizationId,
    repos: Repos,
    flag_service: FeatureFlagServiceDep,
    flag_id: UUID,
    body: FeatureFlagUpdateRequest,
) -> SuccessResponse[FeatureFlagResponse]:
    flag = await repos.feature_flags.require_by_id(flag_id)
    flag = await flag_service.update_flag(
        flag,
        is_enabled=body.is_enabled,
        is_killed=body.is_killed,
        rollout_percentage=body.rollout_percentage,
    )
    return SuccessResponse(
        message="Feature flag updated.", data=_feature_flag_response(flag), meta=_meta()
    )


# ---- GET/POST /admin/jobs ---------------------------------------------------------------------


@router.get(
    "/admin/jobs", response_model=SuccessResponse[JobsResponse], summary="List background jobs"
)
async def list_jobs(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[JobsResponse]:
    rows = await repos.jobs.list_recent(organization_id, limit=limit)
    data = JobsResponse(jobs=[_job_response(row) for row in rows], total=len(rows), page=PageInfo())
    return SuccessResponse(message="Jobs retrieved.", data=data, meta=_meta())


@router.post(
    "/admin/jobs",
    response_model=SuccessResponse[JobResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Enqueue a background job",
    dependencies=[Depends(require_administrator)],
)
async def create_job(
    organization_id: OrganizationId, job_service: JobServiceDep, body: JobCreateRequest
) -> SuccessResponse[JobResponse]:
    job = await job_service.enqueue(
        organization_id,
        job_key=body.job_key,
        priority=body.priority,
        payload=body.payload,
        max_attempts=body.max_attempts,
        now=datetime.now(UTC),
    )
    return SuccessResponse(message="Job enqueued.", data=_job_response(job), meta=_meta())


# ---- GET /admin/diagnostics, /admin/health, /admin/statistics, /admin/reports -------------------


@router.get(
    "/admin/diagnostics",
    response_model=SuccessResponse[DiagnosticsResponse],
    summary="Recent diagnostics",
)
async def get_diagnostics(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[DiagnosticsResponse]:
    rows = await repos.diagnostics.list_recent(organization_id, limit=limit)
    data = DiagnosticsResponse(
        diagnostics=[
            DiagnosticResponse(
                id=row.id,
                category=row.category.value,
                status=row.status,
                latency_ms=row.latency_ms,
                ran_at=row.ran_at,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Diagnostics retrieved.", data=data, meta=_meta())


@router.get(
    "/admin/health",
    response_model=SuccessResponse[PlatformHealthResponse],
    summary="Platform health",
)
async def get_health(
    organization_id: OrganizationId, repos: Repos, diagnostics_service: DiagnosticsServiceDep
) -> SuccessResponse[PlatformHealthResponse]:
    overall = await diagnostics_service.overall_status(organization_id)
    checks = await repos.health_checks.list_all(organization_id)
    data = PlatformHealthResponse(
        overall_status=overall,
        components=[
            HealthCheckComponentResponse(
                component=c.component, status=c.status, checked_at=c.checked_at
            )
            for c in checks
        ],
    )
    return SuccessResponse(message="Platform health retrieved.", data=data, meta=_meta())


@router.get(
    "/admin/statistics",
    response_model=SuccessResponse[StatisticsResponse],
    summary="Platform statistics",
)
async def get_statistics(
    organization_id: OrganizationId, repos: Repos, since: datetime | None = None
) -> SuccessResponse[StatisticsResponse]:
    window_since = since or _default_window(7)[0]
    rows = await repos.statistics.list_range(organization_id, since=window_since)
    data = StatisticsResponse(
        windows=[
            StatisticWindowResponse(
                window_start=row.window_start,
                window_end=row.window_end,
                tenant_count=row.tenant_count,
                user_count=row.user_count,
                api_request_count=row.api_request_count,
                background_job_count=row.background_job_count,
                security_event_count=row.security_event_count,
                platform_availability_fraction=row.platform_availability_fraction,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Platform statistics retrieved.", data=data, meta=_meta())


@router.get(
    "/admin/reports", response_model=SuccessResponse[ReportsResponse], summary="Generated reports"
)
async def get_reports(
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
