"""Request/response shapes for the 12 docs/074 REST endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    CommunityPostStatus,
    CommunityPostType,
    ContentStatus,
    PluginSubmissionStatus,
    SampleProjectCategory,
    SearchContentType,
    TutorialDifficulty,
)

MAX_PAGE_SIZE = 500


# ---- GET /portal/home -----------------------------------------------------------------------


class HomeResponse(BaseModel):
    user_id: str
    display_name: str
    bookmark_count: int
    favorite_count: int
    recent_documentation_titles: list[str]


# ---- GET /portal/documentation -----------------------------------------------------------


class DocumentationPageResponse(BaseModel):
    id: UUID
    slug: str
    title: str
    category: str
    status: ContentStatus
    published_at: datetime | None


class DocumentationListResponse(BaseModel):
    pages: list[DocumentationPageResponse]
    total: int


# ---- GET /portal/tutorials -----------------------------------------------------------------


class TutorialResponse(BaseModel):
    id: UUID
    slug: str
    title: str
    difficulty: TutorialDifficulty
    estimated_minutes: int
    status: ContentStatus


class TutorialsResponse(BaseModel):
    tutorials: list[TutorialResponse]
    total: int


# ---- GET /portal/samples -----------------------------------------------------------------


class SampleProjectResponse(BaseModel):
    id: UUID
    slug: str
    title: str
    category: SampleProjectCategory
    repository_url: str
    status: ContentStatus


class SamplesResponse(BaseModel):
    samples: list[SampleProjectResponse]
    total: int


# ---- GET/POST /portal/plugins --------------------------------------------------------------


class PluginSubmitRequest(BaseModel):
    plugin_name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=32)
    checksum_sha256: str = Field(min_length=64, max_length=64)


class PluginSubmissionResponse(BaseModel):
    id: UUID
    plugin_name: str
    version: str
    status: PluginSubmissionStatus
    submitted_at: datetime


class PluginSubmissionsResponse(BaseModel):
    submissions: list[PluginSubmissionResponse]
    total: int


# ---- GET /portal/playground -----------------------------------------------------------------


class PlaygroundSessionResponse(BaseModel):
    id: UUID
    example_type: str
    status: str
    started_at: datetime
    last_active_at: datetime


class PlaygroundSessionsResponse(BaseModel):
    sessions: list[PlaygroundSessionResponse]
    total: int


# ---- POST /portal/search -----------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=256)
    content_type: SearchContentType | None = None
    limit: int = Field(default=20, ge=1, le=MAX_PAGE_SIZE)


class SearchResultResponse(BaseModel):
    content_id: UUID
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
    total: int


# ---- GET/POST /portal/community --------------------------------------------------------------


class CommunityPostRequest(BaseModel):
    post_type: CommunityPostType
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class CommunityPostResponse(BaseModel):
    id: UUID
    post_type: CommunityPostType
    title: str
    status: CommunityPostStatus
    upvotes: int
    tags: list[str]


class CommunityPostsResponse(BaseModel):
    posts: list[CommunityPostResponse]
    total: int


# ---- GET /portal/statistics -----------------------------------------------------------------


class StatisticWindowResponse(BaseModel):
    window_start: datetime
    window_end: datetime
    portal_visit_count: int
    documentation_view_count: int
    sdk_download_count: int
    search_query_count: int
    tutorial_completion_count: int
    plugin_publication_count: int
    community_activity_count: int
    ai_assistant_usage_count: int


class StatisticsResponse(BaseModel):
    windows: list[StatisticWindowResponse]
    total: int


# ---- GET /portal/reports -----------------------------------------------------------------------


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
    "CommunityPostRequest",
    "CommunityPostResponse",
    "CommunityPostsResponse",
    "DocumentationListResponse",
    "DocumentationPageResponse",
    "HomeResponse",
    "PlaygroundSessionResponse",
    "PlaygroundSessionsResponse",
    "PluginSubmissionResponse",
    "PluginSubmissionsResponse",
    "PluginSubmitRequest",
    "ReportResponse",
    "ReportsResponse",
    "SampleProjectResponse",
    "SamplesResponse",
    "SearchRequest",
    "SearchResponse",
    "SearchResultResponse",
    "StatisticWindowResponse",
    "StatisticsResponse",
    "TutorialResponse",
    "TutorialsResponse",
]
