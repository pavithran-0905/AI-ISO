"""The 15 docs/073 REST endpoints.

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
from shared_core.exceptions.not_found import NotFoundError
from shared_core.logging.context import get_log_context

from app.api.deps import (
    ApiKeyServiceDep,
    ApiSubscriptionServiceDep,
    ApplicationServiceDep,
    CurrentDeveloper,
    DeveloperAccountServiceDep,
    OAuthClientServiceDep,
    OrganizationId,
    Repos,
    ServiceSettings,
    StatisticsServiceDep,
    require_administrator,
)
from app.models.applications import DeveloperApplication
from app.models.developers import DeveloperAccount
from app.models.enums import ApiProductStatus
from app.models.products import ApiPlan, ApiProduct
from app.models.reporting import DeveloperReport
from app.models.usage import ApiQuota, ApiUsageEvent
from app.schemas.public_api import (
    MAX_PAGE_SIZE,
    ApiKeyRegisterRequest,
    ApiKeyResponse,
    ApplicationRegisterRequest,
    ApplicationResponse,
    ApplicationsResponse,
    DeveloperAccountResponse,
    DeveloperRegisterRequest,
    GraphQlSchemaResponse,
    OAuthClientRegisterRequest,
    OAuthClientResponse,
    OpenApiDocumentResponse,
    PlanResponse,
    PlansResponse,
    ProductResponse,
    ProductsResponse,
    QuotaResponse,
    QuotasResponse,
    ReportResponse,
    ReportsResponse,
    StatisticsResponse,
    StatisticWindowResponse,
    SubscriptionRequest,
    SubscriptionResponse,
    UsageEventResponse,
    UsageResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse

router = APIRouter(tags=["Public API Platform"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _developer_response(account: DeveloperAccount) -> DeveloperAccountResponse:
    return DeveloperAccountResponse(
        id=account.id,
        email=account.email,
        display_name=account.display_name,
        status=account.status,
        mfa_enabled=account.mfa_enabled,
        email_verified_at=account.email_verified_at,
    )


def _application_response(application: DeveloperApplication) -> ApplicationResponse:
    return ApplicationResponse(
        id=application.id,
        name=application.name,
        description=application.description,
        status=application.status,
        redirect_uris=application.redirect_uris,
        allowed_origins=application.allowed_origins,
        scopes=application.scopes,
    )


def _product_response(product: ApiProduct) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        name=product.name,
        description=product.description,
        product_type=product.product_type,
    )


def _plan_response(plan: ApiPlan) -> PlanResponse:
    return PlanResponse(
        id=plan.id,
        api_product_id=plan.api_product_id,
        name=plan.name,
        rate_limit_per_minute=plan.rate_limit_per_minute,
        quota_per_month=plan.quota_per_month,
    )


def _usage_response(event: ApiUsageEvent) -> UsageEventResponse:
    return UsageEventResponse(
        id=event.id,
        application_id=event.application_id,
        api_product_id=event.api_product_id,
        endpoint=event.endpoint,
        status_code=event.status_code,
        latency_ms=event.latency_ms,
        occurred_at=event.occurred_at,
    )


def _quota_response(quota: ApiQuota) -> QuotaResponse:
    return QuotaResponse(
        id=quota.id,
        quota_type=quota.quota_type,
        limit_value=quota.limit_value,
        used_value=quota.used_value,
        period_start=quota.period_start,
        period_end=quota.period_end,
    )


def _report_response(report: DeveloperReport) -> ReportResponse:
    return ReportResponse(
        id=report.id,
        kind=str(report.kind),
        report_format=str(report.report_format),
        title=report.title,
        status=str(report.status),
        period_start=report.period_start,
        period_end=report.period_end,
        generated_at=report.generated_at,
        row_count=report.row_count,
    )


# ---- POST /developers/register, GET /developers/profile ---------------------------------------


@router.post(
    "/developers/register",
    response_model=SuccessResponse[DeveloperAccountResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a developer account",
)
async def register_developer(
    organization_id: OrganizationId,
    service: DeveloperAccountServiceDep,
    body: DeveloperRegisterRequest,
) -> SuccessResponse[DeveloperAccountResponse]:
    account = await service.register(
        organization_id, email=body.email, display_name=body.display_name, now=datetime.now(UTC)
    )
    return SuccessResponse(
        message="Developer account registered.", data=_developer_response(account), meta=_meta()
    )


@router.get(
    "/developers/profile",
    response_model=SuccessResponse[DeveloperAccountResponse],
    summary="Get the caller's own developer profile",
)
async def get_developer_profile(
    current: CurrentDeveloper,
) -> SuccessResponse[DeveloperAccountResponse]:
    return SuccessResponse(
        message="Developer profile retrieved.", data=_developer_response(current), meta=_meta()
    )


# ---- POST /applications, GET /applications -----------------------------------------------------


@router.post(
    "/applications",
    response_model=SuccessResponse[ApplicationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a developer application",
)
async def create_application(
    organization_id: OrganizationId,
    current: CurrentDeveloper,
    service: ApplicationServiceDep,
    body: ApplicationRegisterRequest,
) -> SuccessResponse[ApplicationResponse]:
    application = await service.register(
        organization_id,
        developer_account_id=current.id,
        name=body.name,
        description=body.description,
        redirect_uris=body.redirect_uris,
        allowed_origins=body.allowed_origins,
        scopes=body.scopes,
        now=datetime.now(UTC),
        actor_id=current.email,
    )
    return SuccessResponse(
        message="Application registered.", data=_application_response(application), meta=_meta()
    )


@router.get(
    "/applications",
    response_model=SuccessResponse[ApplicationsResponse],
    summary="List the caller's own applications",
)
async def list_applications(
    organization_id: OrganizationId,
    current: CurrentDeveloper,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[ApplicationsResponse]:
    rows = await repos.applications.list_for_developer(
        organization_id, developer_account_id=current.id, limit=limit
    )
    data = ApplicationsResponse(
        applications=[_application_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Applications retrieved.", data=data, meta=_meta())


# ---- POST /oauth/clients -----------------------------------------------------------------------


async def _require_owned_application(
    repos: Repos, *, application_id: UUID, developer_account_id: UUID
) -> DeveloperApplication:
    application = await repos.applications.get_by_id(application_id)
    if application is None or application.developer_account_id != developer_account_id:
        raise NotFoundError(f"Application {application_id!s} was not found.")
    return application


@router.post(
    "/oauth/clients",
    response_model=SuccessResponse[OAuthClientResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register an OAuth2 client for an application",
)
async def create_oauth_client(
    organization_id: OrganizationId,
    current: CurrentDeveloper,
    repos: Repos,
    service: OAuthClientServiceDep,
    body: OAuthClientRegisterRequest,
) -> SuccessResponse[OAuthClientResponse]:
    await _require_owned_application(
        repos, application_id=body.application_id, developer_account_id=current.id
    )
    client, raw_secret = await service.register(
        organization_id,
        application_id=body.application_id,
        grant_types=body.grant_types,
        redirect_uris=body.redirect_uris,
        now=datetime.now(UTC),
    )
    data = OAuthClientResponse(
        id=client.id,
        application_id=client.application_id,
        client_id=client.client_id,
        client_secret=raw_secret,
        grant_types=client.grant_types,
        redirect_uris=client.redirect_uris,
        status=client.status,
    )
    return SuccessResponse(message="OAuth client registered.", data=data, meta=_meta())


# ---- POST /api-keys -----------------------------------------------------------------------------


@router.post(
    "/api-keys",
    response_model=SuccessResponse[ApiKeyResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Issue an API key for an application",
)
async def create_api_key(
    organization_id: OrganizationId,
    current: CurrentDeveloper,
    repos: Repos,
    service: ApiKeyServiceDep,
    settings: ServiceSettings,
    body: ApiKeyRegisterRequest,
) -> SuccessResponse[ApiKeyResponse]:
    await _require_owned_application(
        repos, application_id=body.application_id, developer_account_id=current.id
    )
    key, raw_key = await service.issue(
        organization_id,
        application_id=body.application_id,
        now=datetime.now(UTC),
        max_age_days=settings.api_key_max_age_days,
    )
    data = ApiKeyResponse(
        id=key.id,
        application_id=key.application_id,
        api_key=raw_key,
        status=key.status,
        expires_at=key.expires_at,
    )
    return SuccessResponse(message="API key issued.", data=data, meta=_meta())


# ---- GET /products, GET /plans -------------------------------------------------------------------


@router.get(
    "/products",
    response_model=SuccessResponse[ProductsResponse],
    summary="List approved API products",
)
async def list_products(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[ProductsResponse]:
    rows = await repos.api_products.list_recent(
        organization_id, status=ApiProductStatus.APPROVED, limit=limit
    )
    data = ProductsResponse(products=[_product_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Products retrieved.", data=data, meta=_meta())


@router.get(
    "/plans", response_model=SuccessResponse[PlansResponse], summary="List an API product's plans"
)
async def list_plans(
    organization_id: OrganizationId, repos: Repos, api_product_id: UUID
) -> SuccessResponse[PlansResponse]:
    rows = await repos.api_plans.list_for_product(api_product_id)
    data = PlansResponse(plans=[_plan_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Plans retrieved.", data=data, meta=_meta())


# ---- POST /subscriptions -----------------------------------------------------------------------


@router.post(
    "/subscriptions",
    response_model=SuccessResponse[SubscriptionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe to an API plan",
)
async def create_subscription(
    organization_id: OrganizationId,
    current: CurrentDeveloper,
    service: ApiSubscriptionServiceDep,
    body: SubscriptionRequest,
) -> SuccessResponse[SubscriptionResponse]:
    subscription = await service.subscribe(
        organization_id,
        developer_account_id=current.id,
        api_plan_id=body.api_plan_id,
        now=datetime.now(UTC),
    )
    data = SubscriptionResponse(
        id=subscription.id,
        api_plan_id=subscription.api_plan_id,
        status=subscription.status,
        activated_at=subscription.activated_at,
    )
    return SuccessResponse(message="Subscribed.", data=data, meta=_meta())


# ---- GET /usage, GET /quotas --------------------------------------------------------------------


@router.get(
    "/usage",
    response_model=SuccessResponse[UsageResponse],
    summary="Get the caller's own API usage",
)
async def get_usage(
    organization_id: OrganizationId,
    current: CurrentDeveloper,
    repos: Repos,
    since: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[UsageResponse]:
    window_since = since or (datetime.now(UTC) - timedelta(days=30))
    rows = await repos.api_usage.list_for_developer(
        organization_id, developer_account_id=current.id, since=window_since, limit=limit
    )
    data = UsageResponse(events=[_usage_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Usage retrieved.", data=data, meta=_meta())


@router.get(
    "/quotas", response_model=SuccessResponse[QuotasResponse], summary="Get the caller's own quotas"
)
async def get_quotas(
    organization_id: OrganizationId, current: CurrentDeveloper, repos: Repos
) -> SuccessResponse[QuotasResponse]:
    rows = await repos.api_quotas.list_for_developer(
        organization_id, developer_account_id=current.id
    )
    data = QuotasResponse(quotas=[_quota_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Quotas retrieved.", data=data, meta=_meta())


# ---- GET /openapi, GET /graphql/schema -----------------------------------------------------------


@router.get(
    "/openapi",
    response_model=SuccessResponse[OpenApiDocumentResponse],
    summary="Get the published OpenAPI document for a product",
)
async def get_openapi_document(
    organization_id: OrganizationId, repos: Repos, api_product_id: UUID
) -> SuccessResponse[OpenApiDocumentResponse]:
    document = await repos.openapi_documents.find_published_for_product(
        organization_id, api_product_id=api_product_id
    )
    if document is None:
        raise NotFoundError(f"No published OpenAPI document exists for product {api_product_id!s}.")
    data = OpenApiDocumentResponse(
        api_product_id=document.api_product_id,
        api_version_id=document.api_version_id,
        document=document.document,
        published_at=document.published_at,
    )
    return SuccessResponse(message="OpenAPI document retrieved.", data=data, meta=_meta())


@router.get(
    "/graphql/schema",
    response_model=SuccessResponse[GraphQlSchemaResponse],
    summary="Get the published GraphQL schema for a product",
)
async def get_graphql_schema(
    organization_id: OrganizationId, repos: Repos, api_product_id: UUID
) -> SuccessResponse[GraphQlSchemaResponse]:
    schema = await repos.graphql_schemas.find_published_for_product(
        organization_id, api_product_id=api_product_id
    )
    if schema is None:
        raise NotFoundError(f"No published GraphQL schema exists for product {api_product_id!s}.")
    data = GraphQlSchemaResponse(
        api_product_id=schema.api_product_id,
        api_version_id=schema.api_version_id,
        schema_sdl=schema.schema_sdl,
        published_at=schema.published_at,
    )
    return SuccessResponse(message="GraphQL schema retrieved.", data=data, meta=_meta())


# ---- GET /statistics, GET /reports -----------------------------------------------------------


@router.get(
    "/statistics",
    response_model=SuccessResponse[StatisticsResponse],
    summary="Fleet-wide developer platform statistics",
    dependencies=[Depends(require_administrator)],
)
async def get_statistics(
    organization_id: OrganizationId,
    stats_service: StatisticsServiceDep,
    since: datetime | None = None,
) -> SuccessResponse[StatisticsResponse]:
    window_since = since or (datetime.now(UTC) - timedelta(days=7))
    rows = await stats_service.list_range(organization_id, since=window_since)
    data = StatisticsResponse(
        windows=[
            StatisticWindowResponse(
                window_start=row.window_start,
                window_end=row.window_end,
                api_call_count=row.api_call_count,
                registration_count=row.registration_count,
                application_count=row.application_count,
                sdk_download_count=row.sdk_download_count,
                error_count=row.error_count,
                average_latency_ms=row.average_latency_ms,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Statistics retrieved.", data=data, meta=_meta())


@router.get(
    "/reports",
    response_model=SuccessResponse[ReportsResponse],
    summary="Generated developer platform reports",
    dependencies=[Depends(require_administrator)],
)
async def get_reports(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> SuccessResponse[ReportsResponse]:
    rows = await repos.reports.list_recent(organization_id, limit=limit)
    data = ReportsResponse(reports=[_report_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Reports retrieved.", data=data, meta=_meta())


__all__ = ["router"]
