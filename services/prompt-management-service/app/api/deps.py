"""FastAPI dependency injection for the prompt management service.

One factory per business service, each building its own repositories
from the request-scoped session -- routes depend on services only.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from shared_core.database.session import session_scope
from shared_core.exceptions.authentication import AuthenticationError
from shared_core.security.jwt import decode_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import PromptManagementServiceSettings
from app.repositories.analytics import (
    PromptAuditRepository,
    PromptOptimizationRepository,
    PromptReportRepository,
    PromptStatisticRepository,
)
from app.repositories.governance import (
    PromptApprovalRepository,
    PromptReviewRepository,
    PromptSecurityScanRepository,
)
from app.repositories.prompt import PromptRepository, PromptVersionRepository
from app.repositories.template import (
    PromptCategoryRepository,
    PromptTagRepository,
    PromptTemplateRepository,
    PromptVariableRepository,
)
from app.repositories.testing import (
    PromptAbTestRepository,
    PromptExecutionRepository,
    PromptTestRepository,
    PromptTestResultRepository,
)
from app.services.analytics import (
    AuditService,
    EvaluationService,
    ExecutionRecordingService,
    OptimizationService,
    ReportService,
    StatisticsService,
)
from app.services.governance import (
    ApprovalService,
    PublicationGate,
    ReviewService,
    SecurityService,
)
from app.services.prompt import PromptService
from app.services.rendering import RenderingService
from app.services.testing import AbTestingService, PromptTestingService
from app.types import EventPublisher

_bearer_scheme = HTTPBearer(auto_error=False)


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


def get_service_settings(request: Request) -> PromptManagementServiceSettings:
    """This service's own configuration."""
    return request.app.state.service_settings  # type: ignore[no-any-return]


ServiceSettings = Annotated[PromptManagementServiceSettings, Depends(get_service_settings)]


def get_http_client(request: Request) -> httpx.AsyncClient:
    """The process-wide outbound HTTP client."""
    return request.app.state.http_client  # type: ignore[no-any-return]


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


async def get_current_user_id(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> UUID:
    """Resolve the calling user's id from their Bearer token.

    Raises:
        AuthenticationError: If no valid Bearer token is presented.
    """
    if credentials is None:
        raise AuthenticationError("Authentication required.")
    public_key = request.app.state.jwt_public_key
    claims = decode_token(credentials.credentials, public_key=public_key)
    return UUID(str(claims["sub"]))


CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]


async def get_caller_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> str:
    """The raw Bearer token, forwarded to secrets-management-service.

    A prompt's own secret references resolve with the authority of
    whoever asked for the render, never a fixed service credential --
    otherwise any caller could read any secret the service can reach.
    """
    return credentials.credentials if credentials is not None else ""


CallerToken = Annotated[str, Depends(get_caller_token)]


# ---- repositories -----------------------------------------------------------


def get_prompts_repo(session: DbSession) -> PromptRepository:
    """The current request's prompt repository."""
    return PromptRepository(session)


PromptsRepo = Annotated[PromptRepository, Depends(get_prompts_repo)]


def get_versions_repo(session: DbSession) -> PromptVersionRepository:
    """The current request's version repository."""
    return PromptVersionRepository(session)


VersionsRepo = Annotated[PromptVersionRepository, Depends(get_versions_repo)]


def get_variables_repo(session: DbSession) -> PromptVariableRepository:
    """The current request's variable repository."""
    return PromptVariableRepository(session)


VariablesRepo = Annotated[PromptVariableRepository, Depends(get_variables_repo)]


def get_templates_repo(session: DbSession) -> PromptTemplateRepository:
    """The current request's template repository."""
    return PromptTemplateRepository(session)


TemplatesRepo = Annotated[PromptTemplateRepository, Depends(get_templates_repo)]


def get_categories_repo(session: DbSession) -> PromptCategoryRepository:
    """The current request's category repository."""
    return PromptCategoryRepository(session)


CategoriesRepo = Annotated[PromptCategoryRepository, Depends(get_categories_repo)]


def get_tags_repo(session: DbSession) -> PromptTagRepository:
    """The current request's tag repository."""
    return PromptTagRepository(session)


TagsRepo = Annotated[PromptTagRepository, Depends(get_tags_repo)]


def get_tests_repo(session: DbSession) -> PromptTestRepository:
    """The current request's test repository."""
    return PromptTestRepository(session)


TestsRepo = Annotated[PromptTestRepository, Depends(get_tests_repo)]


def get_ab_tests_repo(session: DbSession) -> PromptAbTestRepository:
    """The current request's A/B experiment repository."""
    return PromptAbTestRepository(session)


AbTestsRepo = Annotated[PromptAbTestRepository, Depends(get_ab_tests_repo)]


def get_optimizations_repo(session: DbSession) -> PromptOptimizationRepository:
    """The current request's optimization repository."""
    return PromptOptimizationRepository(session)


OptimizationsRepo = Annotated[PromptOptimizationRepository, Depends(get_optimizations_repo)]


def get_reviews_repo(session: DbSession) -> PromptReviewRepository:
    """The current request's review repository."""
    return PromptReviewRepository(session)


ReviewsRepo = Annotated[PromptReviewRepository, Depends(get_reviews_repo)]


def get_approvals_repo(session: DbSession) -> PromptApprovalRepository:
    """The current request's approval repository."""
    return PromptApprovalRepository(session)


ApprovalsRepo = Annotated[PromptApprovalRepository, Depends(get_approvals_repo)]


def get_scans_repo(session: DbSession) -> PromptSecurityScanRepository:
    """The current request's security scan repository."""
    return PromptSecurityScanRepository(session)


ScansRepo = Annotated[PromptSecurityScanRepository, Depends(get_scans_repo)]


def get_executions_repo(session: DbSession) -> PromptExecutionRepository:
    """The current request's execution repository."""
    return PromptExecutionRepository(session)


ExecutionsRepo = Annotated[PromptExecutionRepository, Depends(get_executions_repo)]


# ---- services -----------------------------------------------------------


def get_prompt_service(session: DbSession, publish_event: EventPublisherDep) -> PromptService:
    """The current request's prompt lifecycle service."""
    return PromptService(
        PromptRepository(session),
        PromptVersionRepository(session),
        PromptAuditRepository(session),
        publish_event=publish_event,
        variables=PromptVariableRepository(session),
    )


PromptSvc = Annotated[PromptService, Depends(get_prompt_service)]


def get_rendering_service(session: DbSession, settings: ServiceSettings) -> RenderingService:
    """The current request's rendering service."""
    return RenderingService(
        PromptRepository(session),
        PromptVersionRepository(session),
        PromptTemplateRepository(session),
        PromptVariableRepository(session),
        max_depth=settings.max_template_depth,
        max_length=settings.max_rendered_length,
    )


RenderingSvc = Annotated[RenderingService, Depends(get_rendering_service)]


def get_review_service(session: DbSession) -> ReviewService:
    """The current request's review service."""
    return ReviewService(PromptReviewRepository(session))


ReviewSvc = Annotated[ReviewService, Depends(get_review_service)]


def get_approval_service(session: DbSession, publish_event: EventPublisherDep) -> ApprovalService:
    """The current request's approval service."""
    return ApprovalService(
        PromptApprovalRepository(session),
        PromptAuditRepository(session),
        publish_event=publish_event,
    )


ApprovalSvc = Annotated[ApprovalService, Depends(get_approval_service)]


def get_security_service(session: DbSession, publish_event: EventPublisherDep) -> SecurityService:
    """The current request's security scanning service."""
    return SecurityService(
        PromptSecurityScanRepository(session),
        PromptVariableRepository(session),
        publish_event=publish_event,
    )


SecuritySvc = Annotated[SecurityService, Depends(get_security_service)]


def get_publication_gate(session: DbSession) -> PublicationGate:
    """The current request's publication gate."""
    return PublicationGate(
        PromptReviewRepository(session),
        PromptApprovalRepository(session),
        PromptSecurityScanRepository(session),
    )


Gate = Annotated[PublicationGate, Depends(get_publication_gate)]


def get_testing_service(session: DbSession, settings: ServiceSettings) -> PromptTestingService:
    """The current request's prompt testing service."""
    return PromptTestingService(
        PromptTestRepository(session),
        PromptTestResultRepository(session),
        get_rendering_service(session, settings),
    )


TestingSvc = Annotated[PromptTestingService, Depends(get_testing_service)]


def get_ab_service(session: DbSession, publish_event: EventPublisherDep) -> AbTestingService:
    """The current request's A/B experiment service."""
    return AbTestingService(
        PromptAbTestRepository(session),
        PromptExecutionRepository(session),
        PromptAuditRepository(session),
        publish_event=publish_event,
    )


AbSvc = Annotated[AbTestingService, Depends(get_ab_service)]


def get_optimization_service(
    session: DbSession, publish_event: EventPublisherDep
) -> OptimizationService:
    """The current request's optimization service."""
    return OptimizationService(
        PromptOptimizationRepository(session),
        get_prompt_service(session, publish_event),
        publish_event=publish_event,
    )


OptimizationSvc = Annotated[OptimizationService, Depends(get_optimization_service)]


def get_evaluation_service(
    session: DbSession, publish_event: EventPublisherDep
) -> EvaluationService:
    """The current request's evaluation service."""
    return EvaluationService(PromptVersionRepository(session), publish_event=publish_event)


EvaluationSvc = Annotated[EvaluationService, Depends(get_evaluation_service)]


def get_execution_service(
    session: DbSession, publish_event: EventPublisherDep
) -> ExecutionRecordingService:
    """The current request's execution recording service."""
    return ExecutionRecordingService(
        PromptExecutionRepository(session),
        PromptRepository(session),
        publish_event=publish_event,
    )


ExecutionSvc = Annotated[ExecutionRecordingService, Depends(get_execution_service)]


def get_statistics_service(session: DbSession) -> StatisticsService:
    """The current request's statistics service."""
    return StatisticsService(
        PromptStatisticRepository(session),
        PromptRepository(session),
        PromptExecutionRepository(session),
        PromptOptimizationRepository(session),
        PromptSecurityScanRepository(session),
    )


StatisticsSvc = Annotated[StatisticsService, Depends(get_statistics_service)]


def get_report_service(session: DbSession, settings: ServiceSettings) -> ReportService:
    """The current request's report service."""
    return ReportService(
        PromptReportRepository(session),
        PromptRepository(session),
        PromptOptimizationRepository(session),
        PromptSecurityScanRepository(session),
        PromptAuditRepository(session),
        max_rows=settings.max_report_rows,
    )


ReportSvc = Annotated[ReportService, Depends(get_report_service)]


def get_audit_service(session: DbSession) -> AuditService:
    """The current request's audit service."""
    return AuditService(PromptAuditRepository(session))


AuditSvc = Annotated[AuditService, Depends(get_audit_service)]


__all__ = [
    "AbSvc",
    "AbTestsRepo",
    "ApprovalSvc",
    "ApprovalsRepo",
    "AuditSvc",
    "CallerToken",
    "CategoriesRepo",
    "CurrentUserId",
    "DbSession",
    "EvaluationSvc",
    "EventPublisherDep",
    "ExecutionSvc",
    "ExecutionsRepo",
    "Gate",
    "HttpClientDep",
    "OptimizationSvc",
    "OptimizationsRepo",
    "PromptSvc",
    "PromptsRepo",
    "RenderingSvc",
    "ReportSvc",
    "ReviewSvc",
    "ReviewsRepo",
    "ScansRepo",
    "SecuritySvc",
    "ServiceSettings",
    "StatisticsSvc",
    "TagsRepo",
    "TemplatesRepo",
    "TestingSvc",
    "TestsRepo",
    "VariablesRepo",
    "VersionsRepo",
    "get_ab_service",
    "get_ab_tests_repo",
    "get_approval_service",
    "get_approvals_repo",
    "get_audit_service",
    "get_caller_token",
    "get_categories_repo",
    "get_current_user_id",
    "get_db_session",
    "get_evaluation_service",
    "get_event_publisher",
    "get_execution_service",
    "get_executions_repo",
    "get_http_client",
    "get_optimization_service",
    "get_optimizations_repo",
    "get_prompt_service",
    "get_prompts_repo",
    "get_publication_gate",
    "get_rendering_service",
    "get_report_service",
    "get_review_service",
    "get_reviews_repo",
    "get_scans_repo",
    "get_security_service",
    "get_service_settings",
    "get_statistics_service",
    "get_tags_repo",
    "get_templates_repo",
    "get_testing_service",
    "get_tests_repo",
    "get_variables_repo",
    "get_versions_repo",
]
