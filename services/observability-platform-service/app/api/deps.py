"""FastAPI dependency injection for the observability platform service.

One factory per business service, each building its repositories from the
request-scoped session -- routes depend on services only.

**The caller's organization comes from their verified token and from
nowhere else.** Accepting it as a query parameter or a body field would
be a cross-tenant read: every repository here scopes on the value it is
handed, so a caller supplying somebody else's organization id would be
served their signals.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from shared_core.database.session import session_scope
from shared_core.exceptions.authentication import AuthenticationError
from shared_core.exceptions.authorization import AuthorizationError
from shared_core.security.jwt import decode_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import ObservabilityPlatformServiceSettings
from app.ingestion.pipeline import IngestionLimits
from app.search.query import QueryLimits
from app.services.anomaly import AnomalyDetectionService
from app.services.bundle import Repositories, build_repositories
from app.services.capacity import CapacityForecastService
from app.services.cost import CostReportingService
from app.services.ingestion import IngestionService
from app.services.notifications import ObservabilityNotifier
from app.services.retention import RetentionService
from app.services.root_cause import RootCauseAnalysisService
from app.services.search import SearchService
from app.services.slo import SloEvaluationService
from app.services.topology import TopologyService
from app.types import EventPublisher

_bearer_scheme = HTTPBearer(auto_error=False)

ADMINISTRATOR_ROLES = frozenset({"admin", "administrator", "platform_admin", "observability_admin"})
"""Roles permitted to create and manage SLOs and retention policy within
their own organization. Never across organizations: an administrator's
remit is their tenant, and no role in a token can widen it."""

_ROLES_CLAIM = "roles"
_ORGANIZATION_CLAIM = "organization_id"


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped database session, committing on success."""
    session_factory = request.app.state.db_session_factory
    async with session_scope(session_factory) as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_event_publisher(request: Request) -> EventPublisher:
    """The process-wide domain-event publisher (wrapped for notifications)."""
    return request.app.state.publish_event  # type: ignore[no-any-return]


EventPublisherDep = Annotated[EventPublisher, Depends(get_event_publisher)]


def get_service_settings(request: Request) -> ObservabilityPlatformServiceSettings:
    """This service's own configuration."""
    return request.app.state.service_settings  # type: ignore[no-any-return]


ServiceSettings = Annotated[ObservabilityPlatformServiceSettings, Depends(get_service_settings)]


def get_notifier(request: Request) -> ObservabilityNotifier | None:
    """The process-wide notifier, or ``None`` when notifications are unconfigured."""
    return getattr(request.app.state, "notifier", None)


Notifier = Annotated["ObservabilityNotifier | None", Depends(get_notifier)]


# ---- authentication -----------------------------------------------------------------


async def get_token_claims(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> dict[str, Any]:
    """Verified claims from the caller's Bearer token.

    Raises:
        AuthenticationError: If no valid Bearer token is presented.
    """
    if credentials is None:
        raise AuthenticationError("Authentication required.")
    public_key = request.app.state.jwt_public_key
    return dict(decode_token(credentials.credentials, public_key=public_key))


TokenClaims = Annotated[dict[str, Any], Depends(get_token_claims)]


async def get_current_user_id(claims: TokenClaims) -> str:
    """The calling user's id, as a string.

    Raises:
        AuthenticationError: If the token carries no subject.
    """
    subject = claims.get("sub")
    if not subject:
        raise AuthenticationError("The token carries no valid subject claim.")
    return str(subject)


CurrentUserId = Annotated[str, Depends(get_current_user_id)]


async def get_organization_id(claims: TokenClaims) -> UUID:
    """The calling user's organization, from their token.

    Raises:
        AuthorizationError: If the token names no organization. Falling
            back to a default tenant here would serve one organization's
            signals to a token that never claimed it.
    """
    raw = claims.get(_ORGANIZATION_CLAIM)
    if not raw:
        raise AuthorizationError(
            "The token carries no organization claim, so no observability scope can be established."
        )
    try:
        return UUID(str(raw))
    except ValueError as exc:
        raise AuthorizationError(
            f"The token's organization claim {raw!r} is not a valid identifier."
        ) from exc


OrganizationId = Annotated[UUID, Depends(get_organization_id)]


async def get_roles(claims: TokenClaims) -> frozenset[str]:
    """The caller's roles, lowercased."""
    raw = claims.get(_ROLES_CLAIM) or []
    if isinstance(raw, str):
        raw = [raw]
    return frozenset(str(role).strip().lower() for role in raw if str(role).strip())


Roles = Annotated[frozenset[str], Depends(get_roles)]


async def require_administrator(roles: Roles) -> None:
    """Gate an endpoint on an administrator role.

    Raises:
        AuthorizationError: If the caller holds none.
    """
    if not roles & ADMINISTRATOR_ROLES:
        raise AuthorizationError(
            f"This endpoint requires an administrator role; the token holds "
            f"{sorted(roles) or 'none'}."
        )


# ---- repositories and services -------------------------------------------------------


async def get_repositories(session: DbSession) -> Repositories:
    """Every repository over the request's session."""
    return build_repositories(session)


Repos = Annotated[Repositories, Depends(get_repositories)]


def get_ingestion_limits(settings: ServiceSettings) -> IngestionLimits:
    return IngestionLimits(
        max_batch_size=settings.max_batch_size,
        max_label_count=settings.max_label_count,
        max_label_value_length=settings.max_label_value_length,
        max_message_length=settings.max_log_message_length,
        clock_skew_tolerance=timedelta(seconds=settings.clock_skew_tolerance_seconds),
        max_age=timedelta(days=settings.max_ingest_age_days),
    )


async def get_ingestion_service(
    session: DbSession,
    organization_id: OrganizationId,
    settings: ServiceSettings,
    publish: EventPublisherDep,
) -> IngestionService:
    return IngestionService(
        session,
        organization_id=organization_id,
        limits=get_ingestion_limits(settings),
        publish=publish,
    )


Ingestion = Annotated[IngestionService, Depends(get_ingestion_service)]


async def get_search_limits(settings: ServiceSettings) -> QueryLimits:
    return QueryLimits(
        max_range=timedelta(days=settings.max_query_range_days),
        max_filters=16,
        max_page_size=min(settings.max_query_results, 500),
        default_page_size=100,
    )


async def get_search_service(repos: Repos, settings: ServiceSettings) -> SearchService:
    return SearchService(repos.logs, repos.events, limits=await get_search_limits(settings))


Search = Annotated[SearchService, Depends(get_search_service)]


async def get_slo_service(repos: Repos, publish: EventPublisherDep) -> SloEvaluationService:
    return SloEvaluationService(repos.slos, repos.slis, publish=publish)


SloService = Annotated[SloEvaluationService, Depends(get_slo_service)]


async def get_anomaly_service(repos: Repos, publish: EventPublisherDep) -> AnomalyDetectionService:
    return AnomalyDetectionService(repos.anomalies, publish=publish)


AnomalyService = Annotated[AnomalyDetectionService, Depends(get_anomaly_service)]


async def get_capacity_service(repos: Repos, publish: EventPublisherDep) -> CapacityForecastService:
    return CapacityForecastService(repos.forecasts, publish=publish)


CapacityService = Annotated[CapacityForecastService, Depends(get_capacity_service)]


async def get_cost_service(repos: Repos) -> CostReportingService:
    return CostReportingService(repos.costs)


CostService = Annotated[CostReportingService, Depends(get_cost_service)]


async def get_root_cause_service(
    repos: Repos, publish: EventPublisherDep
) -> RootCauseAnalysisService:
    return RootCauseAnalysisService(repos.root_causes, publish=publish)


RootCauseService = Annotated[RootCauseAnalysisService, Depends(get_root_cause_service)]


async def get_topology_service(repos: Repos) -> TopologyService:
    return TopologyService(repos.dependencies, repos.topology_nodes)


TopologyServiceDep = Annotated[TopologyService, Depends(get_topology_service)]


async def get_retention_service(repos: Repos) -> RetentionService:
    return RetentionService(repos.retention_policies)


RetentionServiceDep = Annotated[RetentionService, Depends(get_retention_service)]


__all__ = [
    "ADMINISTRATOR_ROLES",
    "AnomalyService",
    "CapacityService",
    "CostService",
    "CurrentUserId",
    "DbSession",
    "EventPublisherDep",
    "Ingestion",
    "Notifier",
    "OrganizationId",
    "Repos",
    "RetentionServiceDep",
    "Roles",
    "RootCauseService",
    "Search",
    "ServiceSettings",
    "SloService",
    "TokenClaims",
    "TopologyServiceDep",
    "get_organization_id",
    "get_token_claims",
    "require_administrator",
]
