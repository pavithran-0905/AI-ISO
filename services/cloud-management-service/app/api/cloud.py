"""The 15 docs/068 REST endpoints.

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
    AccountServiceDep,
    BudgetServiceDep,
    CurrentUserId,
    OrganizationId,
    Repos,
    ResourceServiceDep,
    require_administrator,
)
from app.finops.engine import is_idle_resource, recommend_rightsizing
from app.models.accounts import CloudAccount
from app.models.enums import CloudResourceLifecycleState, CloudResourceType
from app.models.resources import CloudResource
from app.schemas.cloud import (
    MAX_PAGE_SIZE,
    AccountCreateRequest,
    AccountResponse,
    AccountsResponse,
    BudgetCreateRequest,
    BudgetResponse,
    BudgetsResponse,
    ComplianceAssessmentResponse,
    ComplianceResponse,
    CostItemResponse,
    CostResponse,
    OptimizationRecommendation,
    OptimizationResponse,
    PageInfo,
    ProviderResponse,
    ProvidersResponse,
    ReportResponse,
    ReportsResponse,
    ResourceDiscoverRequest,
    ResourceProvisionRequest,
    ResourceResponse,
    ResourcesResponse,
    ResourceUpdateRequest,
    StatisticsResponse,
    StatisticWindowResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse
from app.services.accounts import CredentialRefusedError
from app.services.resources import TransitionRefusedError

router = APIRouter(prefix="/cloud", tags=["Cloud Management"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _default_window(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(UTC)
    return end - timedelta(days=days), end


def _account_response(account: CloudAccount) -> AccountResponse:
    return AccountResponse(
        id=account.id,
        provider_id=account.provider_id,
        external_account_id=account.external_account_id,
        name=account.name,
        is_valid=account.is_valid,
        health_status=str(account.health_status),
        last_validated_at=account.last_validated_at,
        registered_at=account.registered_at,
    )


def _resource_response(resource: CloudResource) -> ResourceResponse:
    return ResourceResponse(
        id=resource.id,
        account_id=resource.account_id,
        cloud_project_id=resource.cloud_project_id,
        region_id=resource.region_id,
        resource_type=resource.resource_type,
        external_id=resource.external_id,
        name=resource.name,
        lifecycle_state=resource.lifecycle_state,
        tags=resource.tags,
        discovered_at=resource.discovered_at,
        last_synced_at=resource.last_synced_at,
        provisioned_at=resource.provisioned_at,
    )


# ---- GET /cloud/providers --------------------------------------------------------------------


@router.get(
    "/providers", response_model=SuccessResponse[ProvidersResponse], summary="List cloud providers"
)
async def list_providers(
    organization_id: OrganizationId, repos: Repos
) -> SuccessResponse[ProvidersResponse]:
    rows = await repos.providers.list_recent(organization_id, limit=MAX_PAGE_SIZE)
    data = ProvidersResponse(
        providers=[
            ProviderResponse(
                id=row.id, provider_type=row.provider_type, name=row.name, is_enabled=row.is_enabled
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Providers retrieved.", data=data, meta=_meta())


# ---- GET/POST /cloud/accounts -----------------------------------------------------------------


@router.get(
    "/accounts", response_model=SuccessResponse[AccountsResponse], summary="List cloud accounts"
)
async def list_accounts(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[AccountsResponse]:
    rows = await repos.accounts.list_recent(organization_id, limit=limit)
    data = AccountsResponse(
        accounts=[_account_response(row) for row in rows], total=len(rows), page=PageInfo()
    )
    return SuccessResponse(message="Accounts retrieved.", data=data, meta=_meta())


@router.post(
    "/accounts",
    response_model=SuccessResponse[AccountResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a cloud account",
    dependencies=[Depends(require_administrator)],
)
async def create_account(
    organization_id: OrganizationId,
    account_service: AccountServiceDep,
    body: AccountCreateRequest,
    actor: CurrentUserId,
) -> SuccessResponse[AccountResponse]:
    try:
        account = await account_service.register_account(
            organization_id,
            provider_id=body.provider_id,
            external_account_id=body.external_account_id,
            name=body.name,
            credential_ref=body.credential_ref,
            credential_expires_at=body.credential_expires_at,
            actor_id=actor,
            now=datetime.now(UTC),
        )
    except CredentialRefusedError as exc:
        raise ConflictError(
            f"Account {body.name!r} cannot be registered: {exc.validation.detail}"
        ) from exc
    return SuccessResponse(
        message="Account registered.", data=_account_response(account), meta=_meta()
    )


# ---- GET/POST /cloud/resources, resources/discover, resources/provision, {id} ------------------


@router.get(
    "/resources", response_model=SuccessResponse[ResourcesResponse], summary="List cloud resources"
)
async def list_resources(
    organization_id: OrganizationId,
    repos: Repos,
    account_id: UUID | None = None,
    resource_type: CloudResourceType | None = None,
    lifecycle_state: CloudResourceLifecycleState | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[ResourcesResponse]:
    rows = await repos.resources.list_recent(
        organization_id,
        account_id=account_id,
        resource_type=resource_type,
        lifecycle_state=lifecycle_state,
        limit=limit,
    )
    data = ResourcesResponse(
        resources=[_resource_response(row) for row in rows], total=len(rows), page=PageInfo()
    )
    return SuccessResponse(message="Resources retrieved.", data=data, meta=_meta())


@router.post(
    "/resources/discover",
    response_model=SuccessResponse[ResourceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Discover a cloud resource",
    dependencies=[Depends(require_administrator)],
)
async def discover_resource(
    organization_id: OrganizationId,
    resource_service: ResourceServiceDep,
    body: ResourceDiscoverRequest,
) -> SuccessResponse[ResourceResponse]:
    resource = await resource_service.discover(
        organization_id,
        account_id=body.account_id,
        resource_type=body.resource_type,
        external_id=body.external_id,
        name=body.name,
        cloud_project_id=body.cloud_project_id,
        region_id=body.region_id,
        tags=body.tags,
        now=datetime.now(UTC),
    )
    return SuccessResponse(
        message="Resource discovered.", data=_resource_response(resource), meta=_meta()
    )


@router.post(
    "/resources/provision",
    response_model=SuccessResponse[ResourceResponse],
    summary="Advance a resource's lifecycle",
    dependencies=[Depends(require_administrator)],
)
async def provision_resource(
    organization_id: OrganizationId,
    repos: Repos,
    resource_service: ResourceServiceDep,
    body: ResourceProvisionRequest,
    actor: CurrentUserId,
) -> SuccessResponse[ResourceResponse]:
    resource = await repos.resources.require_in_org(organization_id, body.resource_id)
    try:
        resource = await resource_service.transition_lifecycle(
            resource, target=body.target_state, actor_id=actor, now=datetime.now(UTC)
        )
    except TransitionRefusedError as exc:
        raise ConflictError(
            f"Resource {body.resource_id!s} cannot move to {body.target_state.value}: "
            f"{exc.result.detail}"
        ) from exc
    return SuccessResponse(
        message="Resource lifecycle advanced.", data=_resource_response(resource), meta=_meta()
    )


@router.put(
    "/resources/{resource_id}",
    response_model=SuccessResponse[ResourceResponse],
    summary="Update a resource",
    dependencies=[Depends(require_administrator)],
)
async def update_resource(
    organization_id: OrganizationId, repos: Repos, resource_id: UUID, body: ResourceUpdateRequest
) -> SuccessResponse[ResourceResponse]:
    resource = await repos.resources.require_in_org(organization_id, resource_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(resource, field, value)
    await repos.resources.update(resource)
    return SuccessResponse(
        message="Resource updated.", data=_resource_response(resource), meta=_meta()
    )


@router.delete(
    "/resources/{resource_id}",
    response_model=SuccessResponse[ResourceResponse],
    summary="Start deleting a resource",
    dependencies=[Depends(require_administrator)],
)
async def delete_resource(
    organization_id: OrganizationId,
    repos: Repos,
    resource_service: ResourceServiceDep,
    resource_id: UUID,
    actor: CurrentUserId,
) -> SuccessResponse[ResourceResponse]:
    resource = await repos.resources.require_in_org(organization_id, resource_id)
    try:
        resource = await resource_service.transition_lifecycle(
            resource,
            target=CloudResourceLifecycleState.DELETING,
            actor_id=actor,
            now=datetime.now(UTC),
        )
    except TransitionRefusedError as exc:
        raise ConflictError(
            f"Resource {resource_id!s} cannot be deleted right now: {exc.result.detail}"
        ) from exc
    return SuccessResponse(
        message="Resource deletion started.", data=_resource_response(resource), meta=_meta()
    )


# ---- GET /cloud/cost ----------------------------------------------------------------------------


@router.get(
    "/cost", response_model=SuccessResponse[CostResponse], summary="Cost line items for an account"
)
async def get_cost(
    organization_id: OrganizationId,
    repos: Repos,
    account_id: UUID,
    since: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[CostResponse]:
    await repos.accounts.require_in_org(organization_id, account_id)
    window_since = since or _default_window(30)[0]
    rows = await repos.costs.list_for_account(account_id, since=window_since, limit=limit)
    data = CostResponse(
        items=[
            CostItemResponse(
                id=row.id,
                account_id=row.account_id,
                resource_id=row.resource_id,
                amount=row.amount,
                currency=row.currency,
                cost_category=row.cost_category,
                period_start=row.period_start,
                period_end=row.period_end,
            )
            for row in rows
        ],
        total_amount=sum(row.amount for row in rows),
        total=len(rows),
    )
    return SuccessResponse(message="Cost retrieved.", data=data, meta=_meta())


# ---- GET/POST /cloud/budgets ---------------------------------------------------------------------


@router.get("/budgets", response_model=SuccessResponse[BudgetsResponse], summary="List budgets")
async def list_budgets(
    organization_id: OrganizationId, repos: Repos
) -> SuccessResponse[BudgetsResponse]:
    rows = await repos.budgets.list_recent(organization_id, limit=MAX_PAGE_SIZE)
    data = BudgetsResponse(
        budgets=[
            BudgetResponse(
                id=row.id,
                account_id=row.account_id,
                name=row.name,
                amount=row.amount,
                period=row.period,
                threshold_fraction=row.threshold_fraction,
                current_spend=row.current_spend,
                period_start=row.period_start,
                period_end=row.period_end,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Budgets retrieved.", data=data, meta=_meta())


@router.post(
    "/budgets",
    response_model=SuccessResponse[BudgetResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a budget",
    dependencies=[Depends(require_administrator)],
)
async def create_budget(
    organization_id: OrganizationId, budget_service: BudgetServiceDep, body: BudgetCreateRequest
) -> SuccessResponse[BudgetResponse]:
    budget = await budget_service.create_budget(
        organization_id,
        account_id=body.account_id,
        name=body.name,
        amount=body.amount,
        period=body.period,
        threshold_fraction=body.threshold_fraction,
        period_start=body.period_start,
        period_end=body.period_end,
    )
    data = BudgetResponse(
        id=budget.id,
        account_id=budget.account_id,
        name=budget.name,
        amount=budget.amount,
        period=budget.period,
        threshold_fraction=budget.threshold_fraction,
        current_spend=budget.current_spend,
        period_start=budget.period_start,
        period_end=budget.period_end,
    )
    return SuccessResponse(message="Budget created.", data=data, meta=_meta())


# ---- GET /cloud/optimization -------------------------------------------------------------


@router.get(
    "/optimization",
    response_model=SuccessResponse[OptimizationResponse],
    summary="FinOps recommendations",
)
async def get_optimization(
    organization_id: OrganizationId, repos: Repos
) -> SuccessResponse[OptimizationResponse]:
    idle_threshold = 0.05
    compute_rows = await repos.compute.list_for_org(organization_id)
    recommendations = [
        OptimizationRecommendation(
            resource_id=row.resource_id,
            is_idle=is_idle_resource(
                row.utilization_fraction, idle_threshold_fraction=idle_threshold
            ),
            recommendation=recommend_rightsizing(
                row.utilization_fraction, low_threshold=0.1, high_threshold=0.9
            ),
        )
        for row in compute_rows
        if row.utilization_fraction is not None
    ]
    data = OptimizationResponse(recommendations=recommendations, total=len(recommendations))
    return SuccessResponse(
        message="Optimization recommendations retrieved.", data=data, meta=_meta()
    )


# ---- GET /cloud/compliance ---------------------------------------------------------------


@router.get(
    "/compliance",
    response_model=SuccessResponse[ComplianceResponse],
    summary="Compliance assessments",
)
async def get_compliance(
    organization_id: OrganizationId, repos: Repos
) -> SuccessResponse[ComplianceResponse]:
    rows = await repos.compliance.list_recent(organization_id, limit=MAX_PAGE_SIZE)
    data = ComplianceResponse(
        assessments=[
            ComplianceAssessmentResponse(
                account_id=row.account_id,
                framework=row.framework,
                status=row.status,
                score=row.score,
                assessed_at=row.assessed_at,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Compliance assessments retrieved.", data=data, meta=_meta())


# ---- GET /cloud/statistics, /cloud/reports -------------------------------------------------


@router.get(
    "/statistics", response_model=SuccessResponse[StatisticsResponse], summary="Fleet statistics"
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
                resources_discovered=row.resources_discovered,
                resources_provisioned=row.resources_provisioned,
                total_cost=row.total_cost,
                budgets_exceeded=row.budgets_exceeded,
                drift_detected_count=row.drift_detected_count,
                compliance_violations=row.compliance_violations,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Fleet statistics retrieved.", data=data, meta=_meta())


@router.get(
    "/reports", response_model=SuccessResponse[ReportsResponse], summary="Generated reports"
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
