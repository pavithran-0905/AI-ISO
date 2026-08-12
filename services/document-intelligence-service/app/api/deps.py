"""FastAPI dependency injection for the document intelligence service.

One factory per business service, each building its repositories from the
request-scoped session -- routes depend on services only.

**The caller's organization comes from their verified token and from
nowhere else.** Accepting it as a query parameter or a body field would
be a cross-tenant read: every repository here scopes on the value it is
handed, so a caller supplying somebody else's organization id would be
served their documents.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from shared_core.database.session import session_scope
from shared_core.exceptions.authentication import AuthenticationError
from shared_core.exceptions.authorization import AuthorizationError
from shared_core.security.jwt import decode_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import DocumentIntelligenceServiceSettings
from app.notifications.document_notifications import DocumentNotificationService
from app.services.analytics import AnalyticsService, ReportService
from app.services.bundle import Repositories, build_repositories
from app.services.ingestion import IngestionService
from app.services.pipeline import PipelineConfig, PipelineService
from app.services.review import ReviewService
from app.services.storage import DocumentStorage
from app.types import EventPublisher

_bearer_scheme = HTTPBearer(auto_error=False)

ADMINISTRATOR_ROLES = frozenset({"admin", "administrator", "platform_admin", "document_admin"})
"""Roles permitted to read another user's documents within their own
organization. Never across organizations: an administrator's remit is
their tenant, and no role in a token can widen it."""

_ROLES_CLAIM = "roles"
_ORGANIZATION_CLAIM = "organization_id"


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped database session, committing on success."""
    session_factory = request.app.state.db_session_factory
    async with session_scope(session_factory) as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_event_publisher(request: Request) -> EventPublisher:
    """The process-wide domain-event publisher."""
    return request.app.state.publish_event  # type: ignore[no-any-return]


EventPublisherDep = Annotated[EventPublisher, Depends(get_event_publisher)]


def get_service_settings(request: Request) -> DocumentIntelligenceServiceSettings:
    """This service's own configuration."""
    return request.app.state.service_settings  # type: ignore[no-any-return]


ServiceSettings = Annotated[DocumentIntelligenceServiceSettings, Depends(get_service_settings)]


def get_ocr_engine(request: Request) -> object | None:
    """The process-wide OCR engine, or ``None`` when OCR is unavailable.

    ``None`` rather than a stub that returns empty text: a stub would make
    every scanned document look successfully read and empty, which is the
    one failure mode this service must never produce silently.
    """
    return getattr(request.app.state, "ocr_engine", None)


OcrEngine = Annotated[object | None, Depends(get_ocr_engine)]


def get_storage(request: Request) -> DocumentStorage | None:
    """The process-wide document object store, or ``None`` when unconfigured.

    ``None`` is a real deployment state, not a bug: a service brought up
    without MinIO still serves reads and listings. It cannot *process*
    anything, and the endpoints that need bytes say so explicitly rather
    than returning an empty result.
    """
    return getattr(request.app.state, "storage", None)


Storage = Annotated["DocumentStorage | None", Depends(get_storage)]


def get_pipeline_config(request: Request) -> PipelineConfig:
    """The process-wide pipeline configuration."""
    return request.app.state.pipeline_config  # type: ignore[no-any-return]


PipelineConfigDep = Annotated[PipelineConfig, Depends(get_pipeline_config)]


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

    A string rather than a UUID because every actor column in this
    service is a string: an automation or a service account is a valid
    actor and does not have a user UUID.

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
            documents to a token that never claimed it.
    """
    raw = claims.get(_ORGANIZATION_CLAIM)
    if not raw:
        raise AuthorizationError(
            "The token carries no organization claim, so no document scope can " "be established."
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
            "This endpoint requires an administrator role; the token holds "
            f"{sorted(roles) or 'none'}."
        )


# ---- repositories and services -------------------------------------------------------


async def get_repositories(session: DbSession) -> Repositories:
    """Every repository over the request's session."""
    return build_repositories(session)


Repos = Annotated[Repositories, Depends(get_repositories)]


async def get_ingestion_service(
    repos: Repos, publish: EventPublisherDep, settings: ServiceSettings, storage: Storage
) -> IngestionService:
    """The ingestion service for this request."""
    return IngestionService(
        documents=repos.documents,
        jobs=repos.jobs,
        audits=repos.audits,
        publish=publish,
        max_bytes=settings.max_document_bytes,
        storage=storage,
    )


Ingestion = Annotated[IngestionService, Depends(get_ingestion_service)]


async def get_pipeline_service(
    repos: Repos,
    publish: EventPublisherDep,
    config: PipelineConfigDep,
    ocr: OcrEngine,
) -> PipelineService:
    """The pipeline service for this request."""
    return PipelineService(repositories=repos, publish=publish, config=config, ocr_engine=ocr)


Pipeline = Annotated[PipelineService, Depends(get_pipeline_service)]


async def get_review_service(
    repos: Repos, publish: EventPublisherDep, settings: ServiceSettings
) -> ReviewService:
    """The review service for this request."""
    return ReviewService(
        repositories=repos,
        publish=publish,
        # Converted from the configured SLA in seconds: one number
        # governs the deadline, so a change to the SLA cannot leave the
        # review deadline behind at an older value.
        default_hours=max(1, settings.review_sla_seconds // 3_600),
    )


Review = Annotated[ReviewService, Depends(get_review_service)]


async def get_analytics_service(repos: Repos) -> AnalyticsService:
    """The analytics service for this request."""
    return AnalyticsService(repositories=repos)


Analytics = Annotated[AnalyticsService, Depends(get_analytics_service)]


async def get_report_service(repos: Repos) -> ReportService:
    """The report service for this request."""
    return ReportService(repositories=repos)


Reports = Annotated[ReportService, Depends(get_report_service)]


def get_notification_service(request: Request) -> DocumentNotificationService | None:
    """The notification service, or ``None`` when none is configured."""
    return getattr(request.app.state, "notifications", None)


Notifications = Annotated["DocumentNotificationService | None", Depends(get_notification_service)]


__all__ = [
    "ADMINISTRATOR_ROLES",
    "Analytics",
    "CurrentUserId",
    "DbSession",
    "EventPublisherDep",
    "Ingestion",
    "Notifications",
    "OcrEngine",
    "OrganizationId",
    "Pipeline",
    "PipelineConfigDep",
    "Reports",
    "Repos",
    "Review",
    "Roles",
    "ServiceSettings",
    "Storage",
    "TokenClaims",
    "get_organization_id",
    "get_token_claims",
    "require_administrator",
]
