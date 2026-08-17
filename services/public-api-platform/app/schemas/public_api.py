"""Request/response shapes for the 15 docs/073 REST endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import (
    ApiProductType,
    ApplicationStatus,
    CredentialStatus,
    DeveloperAccountStatus,
    QuotaType,
    SubscriptionStatus,
)

MAX_PAGE_SIZE = 500


# ---- POST /developers/register, GET /developers/profile ---------------------------------------


class DeveloperRegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(default="", max_length=128)


class DeveloperAccountResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    status: DeveloperAccountStatus
    mfa_enabled: bool
    email_verified_at: datetime | None


# ---- POST /applications, GET /applications ---------------------------------------------------


class ApplicationRegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=2048)
    redirect_uris: list[str] = Field(default_factory=list)
    allowed_origins: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)


class ApplicationResponse(BaseModel):
    id: UUID
    name: str
    description: str
    status: ApplicationStatus
    redirect_uris: list[str]
    allowed_origins: list[str]
    scopes: list[str]


class ApplicationsResponse(BaseModel):
    applications: list[ApplicationResponse]
    total: int


# ---- POST /oauth/clients -----------------------------------------------------------------------


class OAuthClientRegisterRequest(BaseModel):
    application_id: UUID
    grant_types: list[str] = Field(min_length=1)
    redirect_uris: list[str] = Field(default_factory=list)


class OAuthClientResponse(BaseModel):
    id: UUID
    application_id: UUID
    client_id: str
    client_secret: str
    grant_types: list[str]
    redirect_uris: list[str]
    status: CredentialStatus


# ---- POST /api-keys ----------------------------------------------------------------------------


class ApiKeyRegisterRequest(BaseModel):
    application_id: UUID


class ApiKeyResponse(BaseModel):
    id: UUID
    application_id: UUID
    api_key: str
    status: CredentialStatus
    expires_at: datetime


# ---- GET /products, GET /plans -----------------------------------------------------------------


class ProductResponse(BaseModel):
    id: UUID
    name: str
    description: str
    product_type: ApiProductType


class ProductsResponse(BaseModel):
    products: list[ProductResponse]
    total: int


class PlanResponse(BaseModel):
    id: UUID
    api_product_id: UUID
    name: str
    rate_limit_per_minute: int
    quota_per_month: int


class PlansResponse(BaseModel):
    plans: list[PlanResponse]
    total: int


# ---- POST /subscriptions ------------------------------------------------------------------------


class SubscriptionRequest(BaseModel):
    api_plan_id: UUID


class SubscriptionResponse(BaseModel):
    id: UUID
    api_plan_id: UUID
    status: SubscriptionStatus
    activated_at: datetime


# ---- GET /usage -----------------------------------------------------------------------------


class UsageEventResponse(BaseModel):
    id: UUID
    application_id: UUID
    api_product_id: UUID
    endpoint: str
    status_code: int
    latency_ms: float
    occurred_at: datetime


class UsageResponse(BaseModel):
    events: list[UsageEventResponse]
    total: int


# ---- GET /quotas --------------------------------------------------------------------------------


class QuotaResponse(BaseModel):
    id: UUID
    quota_type: QuotaType
    limit_value: int
    used_value: int
    period_start: datetime
    period_end: datetime


class QuotasResponse(BaseModel):
    quotas: list[QuotaResponse]
    total: int


# ---- GET /openapi, GET /graphql/schema -----------------------------------------------------------


class OpenApiDocumentResponse(BaseModel):
    api_product_id: UUID
    api_version_id: UUID
    document: dict[str, Any]
    published_at: datetime | None


class GraphQlSchemaResponse(BaseModel):
    api_product_id: UUID
    api_version_id: UUID
    schema_sdl: str
    published_at: datetime | None


# ---- GET /statistics ----------------------------------------------------------------------------


class StatisticWindowResponse(BaseModel):
    window_start: datetime
    window_end: datetime
    api_call_count: int
    registration_count: int
    application_count: int
    sdk_download_count: int
    error_count: int
    average_latency_ms: float


class StatisticsResponse(BaseModel):
    windows: list[StatisticWindowResponse]
    total: int


# ---- GET /reports -------------------------------------------------------------------------------


class ReportResponse(BaseModel):
    id: UUID
    kind: str
    report_format: str
    title: str
    status: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime | None
    row_count: int


class ReportsResponse(BaseModel):
    reports: list[ReportResponse]
    total: int


__all__ = [
    "MAX_PAGE_SIZE",
    "ApiKeyRegisterRequest",
    "ApiKeyResponse",
    "ApplicationRegisterRequest",
    "ApplicationResponse",
    "ApplicationsResponse",
    "DeveloperAccountResponse",
    "DeveloperRegisterRequest",
    "GraphQlSchemaResponse",
    "OAuthClientRegisterRequest",
    "OAuthClientResponse",
    "OpenApiDocumentResponse",
    "PlanResponse",
    "PlansResponse",
    "ProductResponse",
    "ProductsResponse",
    "QuotaResponse",
    "QuotasResponse",
    "ReportResponse",
    "ReportsResponse",
    "StatisticWindowResponse",
    "StatisticsResponse",
    "SubscriptionRequest",
    "SubscriptionResponse",
    "UsageEventResponse",
    "UsageResponse",
]
