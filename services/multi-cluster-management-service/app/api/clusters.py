"""The 15 docs/066 REST endpoints.

**Every route derives its tenant from the token.** No query or body
parameter names an organization; see
:func:`app.api.deps.get_organization_id` for why that is not a
convenience.

**Literal-path routes are registered before ``/clusters/{cluster_id}``.**
FastAPI matches routes in registration order, so ``/clusters/health``
must be declared ahead of the parameterized detail route or it would be
swallowed as a request for the cluster literally named ``"health"``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from shared_core.exceptions.conflict import ConflictError
from shared_core.logging.context import get_log_context

from app.api.deps import (
    ClusterServiceDep,
    CredentialServiceDep,
    CurrentUserId,
    OrganizationId,
    PlacementServiceDep,
    Repos,
    UpgradeServiceDep,
    require_administrator,
)
from app.capacity.engine import compute_utilization
from app.models.enums import CapacityResourceKind, ClusterLifecycleState, ComplianceFramework
from app.models.fleet import Cluster
from app.schemas.cluster import (
    MAX_PAGE_SIZE,
    ClusterCapacityResponse,
    ClusterComplianceResponse,
    ClusterCreateRequest,
    ClusterHealthResponse,
    ClusterResponse,
    ClustersResponse,
    ClusterUpdateRequest,
    ClusterValidationResponse,
    DrainResponse,
    FleetCapacityResponse,
    FleetComplianceResponse,
    FleetHealthResponse,
    PageInfo,
    ReportResponse,
    ReportsResponse,
    StatisticsResponse,
    StatisticWindowResponse,
    UpgradeRequest,
    UpgradeResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse
from app.services.fleet import TransitionRefusedError
from app.services.upgrades import UpgradePlanRefusedError

router = APIRouter(prefix="/clusters", tags=["Multi-Cluster Management"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _default_window(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(UTC)
    return end - timedelta(days=days), end


def _cluster_response(cluster: Cluster) -> ClusterResponse:
    return ClusterResponse(
        id=cluster.id,
        name=cluster.name,
        cluster_type=cluster.cluster_type,
        lifecycle_state=cluster.lifecycle_state,
        environment=cluster.environment,
        group_id=cluster.group_id,
        region_id=cluster.region_id,
        api_endpoint=cluster.api_endpoint,
        kubernetes_version=cluster.kubernetes_version,
        node_count=cluster.node_count,
        health_status=cluster.health_status,
        is_schedulable=cluster.is_schedulable,
        registered_at=cluster.registered_at,
        last_seen_at=cluster.last_seen_at,
    )


# ---- GET /clusters/health, /capacity, /compliance, /statistics, /reports -------------------
# (registered ahead of /clusters/{cluster_id} -- see module docstring)


@router.get(
    "/health", response_model=SuccessResponse[FleetHealthResponse], summary="Fleet-wide health"
)
async def fleet_health(
    organization_id: OrganizationId, repos: Repos
) -> SuccessResponse[FleetHealthResponse]:
    clusters = await repos.clusters.list_recent(organization_id, limit=MAX_PAGE_SIZE)
    data = FleetHealthResponse(
        clusters=[
            ClusterHealthResponse(
                cluster_id=c.id,
                health_status=c.health_status,
                last_health_check_at=c.last_health_check_at,
            )
            for c in clusters
        ],
        total=len(clusters),
    )
    return SuccessResponse(message="Fleet health retrieved.", data=data, meta=_meta())


@router.get(
    "/capacity",
    response_model=SuccessResponse[FleetCapacityResponse],
    summary="Fleet-wide capacity",
)
async def fleet_capacity(
    organization_id: OrganizationId,
    repos: Repos,
    resource_kind: CapacityResourceKind = CapacityResourceKind.CPU,
) -> SuccessResponse[FleetCapacityResponse]:
    clusters = await repos.clusters.list_recent(organization_id, limit=MAX_PAGE_SIZE)
    readings: list[ClusterCapacityResponse] = []
    for cluster in clusters:
        reading = await repos.capacity.latest_for_resource(cluster.id, resource_kind=resource_kind)
        if reading is None:
            continue
        readings.append(
            ClusterCapacityResponse(
                cluster_id=cluster.id,
                resource_kind=reading.resource_kind,
                total=reading.total,
                used=reading.used,
                utilization_fraction=compute_utilization(reading.total, reading.used),
                measured_at=reading.measured_at,
            )
        )
    data = FleetCapacityResponse(readings=readings, total=len(readings))
    return SuccessResponse(message="Fleet capacity retrieved.", data=data, meta=_meta())


@router.get(
    "/compliance",
    response_model=SuccessResponse[FleetComplianceResponse],
    summary="Fleet-wide compliance",
)
async def fleet_compliance(
    organization_id: OrganizationId,
    repos: Repos,
    framework: ComplianceFramework = ComplianceFramework.CIS_KUBERNETES,
) -> SuccessResponse[FleetComplianceResponse]:
    clusters = await repos.clusters.list_recent(organization_id, limit=MAX_PAGE_SIZE)
    assessments: list[ClusterComplianceResponse] = []
    for cluster in clusters:
        assessment = await repos.compliance.latest_for_framework(cluster.id, framework=framework)
        if assessment is None:
            continue
        assessments.append(
            ClusterComplianceResponse(
                cluster_id=cluster.id,
                framework=assessment.framework,
                status=assessment.status,
                score=assessment.score,
                assessed_at=assessment.assessed_at,
            )
        )
    data = FleetComplianceResponse(assessments=assessments, total=len(assessments))
    return SuccessResponse(message="Fleet compliance retrieved.", data=data, meta=_meta())


@router.get(
    "/statistics", response_model=SuccessResponse[StatisticsResponse], summary="Fleet statistics"
)
async def fleet_statistics(
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
                clusters_registered=row.clusters_registered,
                clusters_healthy=row.clusters_healthy,
                clusters_degraded=row.clusters_degraded,
                clusters_unhealthy=row.clusters_unhealthy,
                policy_violations=row.policy_violations,
                compliance_violations=row.compliance_violations,
                upgrades_completed=row.upgrades_completed,
                upgrades_failed=row.upgrades_failed,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Fleet statistics retrieved.", data=data, meta=_meta())


@router.get(
    "/reports", response_model=SuccessResponse[ReportsResponse], summary="Generated reports"
)
async def fleet_reports(
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


# ---- GET/POST /clusters, GET/PUT/DELETE /clusters/{cluster_id} -----------------------------


@router.get("", response_model=SuccessResponse[ClustersResponse], summary="List clusters")
async def list_clusters(
    organization_id: OrganizationId,
    repos: Repos,
    lifecycle_state: ClusterLifecycleState | None = None,
    group_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[ClustersResponse]:
    rows = await repos.clusters.list_recent(
        organization_id, lifecycle_state=lifecycle_state, group_id=group_id, limit=limit
    )
    data = ClustersResponse(
        clusters=[_cluster_response(row) for row in rows], total=len(rows), page=PageInfo()
    )
    return SuccessResponse(message="Clusters retrieved.", data=data, meta=_meta())


@router.post(
    "",
    response_model=SuccessResponse[ClusterResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a cluster",
    dependencies=[Depends(require_administrator)],
)
async def create_cluster(
    organization_id: OrganizationId,
    cluster_service: ClusterServiceDep,
    body: ClusterCreateRequest,
    actor: CurrentUserId,
) -> SuccessResponse[ClusterResponse]:
    cluster = await cluster_service.register_cluster(
        organization_id,
        name=body.name,
        cluster_type=body.cluster_type,
        environment=body.environment,
        group_id=body.group_id,
        region_id=body.region_id,
        actor_id=actor,
        now=datetime.now(UTC),
    )
    return SuccessResponse(
        message="Cluster registered.", data=_cluster_response(cluster), meta=_meta()
    )


@router.get(
    "/{cluster_id}", response_model=SuccessResponse[ClusterResponse], summary="Get a cluster"
)
async def get_cluster(
    organization_id: OrganizationId, repos: Repos, cluster_id: UUID
) -> SuccessResponse[ClusterResponse]:
    cluster = await repos.clusters.require_in_org(organization_id, cluster_id)
    return SuccessResponse(
        message="Cluster retrieved.", data=_cluster_response(cluster), meta=_meta()
    )


@router.put(
    "/{cluster_id}",
    response_model=SuccessResponse[ClusterResponse],
    summary="Update a cluster",
    dependencies=[Depends(require_administrator)],
)
async def update_cluster(
    organization_id: OrganizationId, repos: Repos, cluster_id: UUID, body: ClusterUpdateRequest
) -> SuccessResponse[ClusterResponse]:
    cluster = await repos.clusters.require_in_org(organization_id, cluster_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(cluster, field, value)
    await repos.clusters.update(cluster)
    return SuccessResponse(
        message="Cluster updated.", data=_cluster_response(cluster), meta=_meta()
    )


@router.delete(
    "/{cluster_id}",
    response_model=SuccessResponse[ClusterResponse],
    summary="Decommission a cluster",
    dependencies=[Depends(require_administrator)],
)
async def delete_cluster(
    organization_id: OrganizationId,
    repos: Repos,
    cluster_service: ClusterServiceDep,
    cluster_id: UUID,
) -> SuccessResponse[ClusterResponse]:
    cluster = await repos.clusters.require_in_org(organization_id, cluster_id)
    try:
        cluster = await cluster_service.transition_lifecycle(
            cluster, target=ClusterLifecycleState.DECOMMISSIONING, now=datetime.now(UTC)
        )
    except TransitionRefusedError as exc:
        raise ConflictError(
            f"Cluster {cluster_id!s} cannot be decommissioned right now: {exc.result.detail}"
        ) from exc
    return SuccessResponse(
        message="Cluster decommissioning started.", data=_cluster_response(cluster), meta=_meta()
    )


# ---- POST /clusters/{cluster_id}/validate ---------------------------------------------------


@router.post(
    "/{cluster_id}/validate",
    response_model=SuccessResponse[ClusterValidationResponse],
    summary="Validate a cluster's credential",
)
async def validate_cluster(
    organization_id: OrganizationId,
    repos: Repos,
    credential_service: CredentialServiceDep,
    cluster_id: UUID,
) -> SuccessResponse[ClusterValidationResponse]:
    await repos.clusters.require_in_org(organization_id, cluster_id)
    credential = await repos.credentials.latest_for_cluster(cluster_id)
    if credential is None:
        data = ClusterValidationResponse(
            cluster_id=cluster_id,
            is_valid=False,
            detail="No credential is registered for this cluster.",
        )
        return SuccessResponse(message="No credential to validate.", data=data, meta=_meta())

    revalidated = await credential_service.revalidate(credential, now=datetime.now(UTC))
    data = ClusterValidationResponse(
        cluster_id=cluster_id,
        is_valid=revalidated.is_valid,
        detail=(
            "Credential is usable." if revalidated.is_valid else "Credential is no longer usable."
        ),
    )
    return SuccessResponse(message="Cluster validated.", data=data, meta=_meta())


# ---- POST /clusters/{cluster_id}/upgrade ----------------------------------------------------


@router.post(
    "/{cluster_id}/upgrade",
    response_model=SuccessResponse[UpgradeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Plan a cluster upgrade",
    dependencies=[Depends(require_administrator)],
)
async def upgrade_cluster(
    organization_id: OrganizationId,
    repos: Repos,
    upgrade_service: UpgradeServiceDep,
    cluster_id: UUID,
    body: UpgradeRequest,
    actor: CurrentUserId,
) -> SuccessResponse[UpgradeResponse]:
    cluster = await repos.clusters.require_in_org(organization_id, cluster_id)
    try:
        upgrade = await upgrade_service.plan_upgrade(
            cluster,
            to_version=body.to_version,
            strategy=body.strategy,
            max_skew=2,
            actor_id=actor,
            now=datetime.now(UTC),
        )
    except UpgradePlanRefusedError as exc:
        data = UpgradeResponse(
            upgrade_id=None,
            cluster_id=cluster_id,
            to_version=body.to_version,
            status=None,
            refusal=exc.validation.refusal,
            detail=exc.validation.detail,
        )
        return SuccessResponse(message="Upgrade was not planned.", data=data, meta=_meta())

    data = UpgradeResponse(
        upgrade_id=upgrade.id,
        cluster_id=cluster_id,
        to_version=body.to_version,
        status=upgrade.status,
        refusal=None,
        detail="Upgrade planned.",
    )
    return SuccessResponse(message="Upgrade planned.", data=data, meta=_meta())


# ---- POST /clusters/{cluster_id}/drain, /cordon, /uncordon ----------------------------------


@router.post(
    "/{cluster_id}/drain",
    response_model=SuccessResponse[DrainResponse],
    summary="Drain a cluster's workloads",
    dependencies=[Depends(require_administrator)],
)
async def drain_cluster(
    organization_id: OrganizationId,
    repos: Repos,
    placement_service: PlacementServiceDep,
    cluster_id: UUID,
) -> SuccessResponse[DrainResponse]:
    await repos.clusters.require_in_org(organization_id, cluster_id)
    marked = await placement_service.drain_cluster(cluster_id)
    data = DrainResponse(cluster_id=cluster_id, workloads_marked=marked)
    return SuccessResponse(message="Cluster drain initiated.", data=data, meta=_meta())


@router.post(
    "/{cluster_id}/cordon",
    response_model=SuccessResponse[ClusterResponse],
    summary="Cordon a cluster",
    dependencies=[Depends(require_administrator)],
)
async def cordon_cluster(
    organization_id: OrganizationId,
    repos: Repos,
    cluster_service: ClusterServiceDep,
    cluster_id: UUID,
) -> SuccessResponse[ClusterResponse]:
    cluster = await repos.clusters.require_in_org(organization_id, cluster_id)
    cluster = await cluster_service.cordon(cluster)
    return SuccessResponse(
        message="Cluster cordoned.", data=_cluster_response(cluster), meta=_meta()
    )


@router.post(
    "/{cluster_id}/uncordon",
    response_model=SuccessResponse[ClusterResponse],
    summary="Uncordon a cluster",
    dependencies=[Depends(require_administrator)],
)
async def uncordon_cluster(
    organization_id: OrganizationId,
    repos: Repos,
    cluster_service: ClusterServiceDep,
    cluster_id: UUID,
) -> SuccessResponse[ClusterResponse]:
    cluster = await repos.clusters.require_in_org(organization_id, cluster_id)
    cluster = await cluster_service.uncordon(cluster)
    return SuccessResponse(
        message="Cluster uncordoned.", data=_cluster_response(cluster), meta=_meta()
    )


__all__ = ["router"]
