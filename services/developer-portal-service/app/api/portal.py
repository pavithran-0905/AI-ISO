"""The 12 docs/074 REST endpoints.

**Every route derives its tenant from the token.** No query or body
parameter names an organization; see
:func:`app.api.deps.get_organization_id` for why that is not a
convenience.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from shared_core.logging.context import get_log_context

from app.api.deps import (
    CommunityPostServiceDep,
    CurrentUserId,
    OrganizationId,
    PluginSubmissionServiceDep,
    Repos,
    SearchServiceDep,
    StatisticsServiceDep,
    require_administrator,
)
from app.models.community import CommunityPost
from app.models.documentation import DocumentationPage
from app.models.enums import SampleProjectCategory
from app.models.learning import Tutorial
from app.models.plugins import PluginSubmission
from app.models.reporting import PortalReport
from app.models.samples import SampleProject
from app.schemas.portal import (
    MAX_PAGE_SIZE,
    CommunityPostRequest,
    CommunityPostResponse,
    CommunityPostsResponse,
    DocumentationListResponse,
    DocumentationPageResponse,
    HomeResponse,
    PlaygroundSessionResponse,
    PlaygroundSessionsResponse,
    PluginSubmissionResponse,
    PluginSubmissionsResponse,
    PluginSubmitRequest,
    ReportResponse,
    ReportsResponse,
    SampleProjectResponse,
    SamplesResponse,
    SearchRequest,
    SearchResponse,
    SearchResultResponse,
    StatisticsResponse,
    StatisticWindowResponse,
    TutorialResponse,
    TutorialsResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse

router = APIRouter(tags=["Developer Portal"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _documentation_response(page: DocumentationPage) -> DocumentationPageResponse:
    return DocumentationPageResponse(
        id=page.id,
        slug=page.slug,
        title=page.title,
        category=page.category,
        status=page.status,
        published_at=page.published_at,
    )


def _tutorial_response(tutorial: Tutorial) -> TutorialResponse:
    return TutorialResponse(
        id=tutorial.id,
        slug=tutorial.slug,
        title=tutorial.title,
        difficulty=tutorial.difficulty,
        estimated_minutes=tutorial.estimated_minutes,
        status=tutorial.status,
    )


def _sample_response(sample: SampleProject) -> SampleProjectResponse:
    return SampleProjectResponse(
        id=sample.id,
        slug=sample.slug,
        title=sample.title,
        category=sample.category,
        repository_url=sample.repository_url,
        status=sample.status,
    )


def _plugin_submission_response(submission: PluginSubmission) -> PluginSubmissionResponse:
    return PluginSubmissionResponse(
        id=submission.id,
        plugin_name=submission.plugin_name,
        version=submission.version_label,
        status=submission.status,
        submitted_at=submission.submitted_at,
    )


def _community_post_response(post: CommunityPost) -> CommunityPostResponse:
    return CommunityPostResponse(
        id=post.id,
        post_type=post.post_type,
        title=post.title,
        status=post.status,
        upvotes=post.upvotes,
        tags=post.tags,
    )


def _report_response(report: PortalReport) -> ReportResponse:
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


# ---- GET /portal/home -----------------------------------------------------------------------


@router.get(
    "/portal/home",
    response_model=SuccessResponse[HomeResponse],
    summary="The caller's own portal dashboard",
)
async def get_home(
    organization_id: OrganizationId, actor: CurrentUserId, repos: Repos
) -> SuccessResponse[HomeResponse]:
    profile = await repos.profiles.find_by_user(organization_id, user_id=actor)
    bookmarks = await repos.bookmarks.list_for_user(organization_id, user_id=actor)
    favorites = await repos.favorites.list_for_user(organization_id, user_id=actor)
    recent_docs = await repos.documentation_pages.list_published(organization_id, limit=5)
    data = HomeResponse(
        user_id=actor,
        display_name=profile.display_name if profile is not None else "",
        bookmark_count=len(bookmarks),
        favorite_count=len(favorites),
        recent_documentation_titles=[page.title for page in recent_docs],
    )
    return SuccessResponse(message="Dashboard retrieved.", data=data, meta=_meta())


# ---- GET /portal/documentation ------------------------------------------------------------


@router.get(
    "/portal/documentation",
    response_model=SuccessResponse[DocumentationListResponse],
    summary="List published documentation pages",
)
async def list_documentation(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[DocumentationListResponse]:
    rows = await repos.documentation_pages.list_published(organization_id, limit=limit)
    data = DocumentationListResponse(
        pages=[_documentation_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Documentation retrieved.", data=data, meta=_meta())


# ---- GET /portal/tutorials ------------------------------------------------------------------


@router.get(
    "/portal/tutorials",
    response_model=SuccessResponse[TutorialsResponse],
    summary="List published tutorials",
)
async def list_tutorials(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[TutorialsResponse]:
    rows = await repos.tutorials.list_published(organization_id, limit=limit)
    data = TutorialsResponse(tutorials=[_tutorial_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Tutorials retrieved.", data=data, meta=_meta())


# ---- GET /portal/samples ------------------------------------------------------------------


@router.get(
    "/portal/samples",
    response_model=SuccessResponse[SamplesResponse],
    summary="List published sample projects",
)
async def list_samples(
    organization_id: OrganizationId,
    repos: Repos,
    category: SampleProjectCategory | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[SamplesResponse]:
    rows = await repos.sample_projects.list_published(
        organization_id, category=category, limit=limit
    )
    data = SamplesResponse(samples=[_sample_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Sample projects retrieved.", data=data, meta=_meta())


# ---- GET/POST /portal/plugins ---------------------------------------------------------------


@router.get(
    "/portal/plugins",
    response_model=SuccessResponse[PluginSubmissionsResponse],
    summary="List the caller's own plugin submissions",
)
async def list_plugin_submissions(
    organization_id: OrganizationId,
    actor: CurrentUserId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[PluginSubmissionsResponse]:
    rows = await repos.plugin_submissions.list_for_user(organization_id, user_id=actor, limit=limit)
    data = PluginSubmissionsResponse(
        submissions=[_plugin_submission_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Plugin submissions retrieved.", data=data, meta=_meta())


@router.post(
    "/portal/plugins",
    response_model=SuccessResponse[PluginSubmissionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Submit a plugin for publishing",
)
async def submit_plugin(
    organization_id: OrganizationId,
    actor: CurrentUserId,
    service: PluginSubmissionServiceDep,
    body: PluginSubmitRequest,
) -> SuccessResponse[PluginSubmissionResponse]:
    submission = await service.submit(
        organization_id,
        user_id=actor,
        plugin_name=body.plugin_name,
        version=body.version,
        checksum_sha256=body.checksum_sha256,
        now=datetime.now(UTC),
    )
    return SuccessResponse(
        message="Plugin submitted.", data=_plugin_submission_response(submission), meta=_meta()
    )


# ---- GET /portal/playground -----------------------------------------------------------------


@router.get(
    "/portal/playground",
    response_model=SuccessResponse[PlaygroundSessionsResponse],
    summary="List the caller's own code playground sessions",
)
async def list_playground_sessions(
    organization_id: OrganizationId,
    actor: CurrentUserId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[PlaygroundSessionsResponse]:
    rows = await repos.playground_sessions.list_for_user(
        organization_id, user_id=actor, limit=limit
    )
    data = PlaygroundSessionsResponse(
        sessions=[
            PlaygroundSessionResponse(
                id=row.id,
                example_type=str(row.example_type),
                status=str(row.status),
                started_at=row.started_at,
                last_active_at=row.last_active_at,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Playground sessions retrieved.", data=data, meta=_meta())


# ---- POST /portal/search -----------------------------------------------------------------


@router.post(
    "/portal/search",
    response_model=SuccessResponse[SearchResponse],
    summary="Search the portal's indexed content",
)
async def search(
    organization_id: OrganizationId,
    actor: CurrentUserId,
    service: SearchServiceDep,
    body: SearchRequest,
) -> SuccessResponse[SearchResponse]:
    results = await service.search(
        organization_id,
        query=body.query,
        user_id=actor,
        content_type=body.content_type,
        limit=body.limit,
    )
    data = SearchResponse(
        results=[
            SearchResultResponse(content_id=content_id, score=score)
            for content_id, score in results
        ],
        total=len(results),
    )
    return SuccessResponse(message="Search completed.", data=data, meta=_meta())


# ---- GET/POST /portal/community --------------------------------------------------------------


@router.get(
    "/portal/community",
    response_model=SuccessResponse[CommunityPostsResponse],
    summary="List community posts",
)
async def list_community_posts(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[CommunityPostsResponse]:
    rows = await repos.community_posts.list_visible(organization_id, limit=limit)
    data = CommunityPostsResponse(
        posts=[_community_post_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Community posts retrieved.", data=data, meta=_meta())


@router.post(
    "/portal/community",
    response_model=SuccessResponse[CommunityPostResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a community post",
)
async def create_community_post(
    organization_id: OrganizationId,
    actor: CurrentUserId,
    service: CommunityPostServiceDep,
    body: CommunityPostRequest,
) -> SuccessResponse[CommunityPostResponse]:
    post = await service.create(
        organization_id,
        user_id=actor,
        post_type=body.post_type,
        title=body.title,
        body=body.body,
        tags=body.tags,
    )
    return SuccessResponse(
        message="Community post created.", data=_community_post_response(post), meta=_meta()
    )


# ---- GET /portal/statistics, GET /portal/reports ------------------------------------------------


@router.get(
    "/portal/statistics",
    response_model=SuccessResponse[StatisticsResponse],
    summary="Fleet-wide portal statistics",
    dependencies=[Depends(require_administrator)],
)
async def get_statistics(
    organization_id: OrganizationId, service: StatisticsServiceDep, since: datetime | None = None
) -> SuccessResponse[StatisticsResponse]:
    window_since = since or (datetime.now(UTC) - timedelta(days=7))
    rows = await service.list_range(organization_id, since=window_since)
    data = StatisticsResponse(
        windows=[
            StatisticWindowResponse(
                window_start=row.window_start,
                window_end=row.window_end,
                portal_visit_count=row.portal_visit_count,
                documentation_view_count=row.documentation_view_count,
                sdk_download_count=row.sdk_download_count,
                search_query_count=row.search_query_count,
                tutorial_completion_count=row.tutorial_completion_count,
                plugin_publication_count=row.plugin_publication_count,
                community_activity_count=row.community_activity_count,
                ai_assistant_usage_count=row.ai_assistant_usage_count,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Statistics retrieved.", data=data, meta=_meta())


@router.get(
    "/portal/reports",
    response_model=SuccessResponse[ReportsResponse],
    summary="Generated portal reports",
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
