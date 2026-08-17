"""The repository bundle every route works through.

One object rather than twenty-four constructor arguments, all sharing
one tenant scope: a bundle where one repository was built without it
would enforce tenant isolation everywhere except the one query that
forgot, and that query is the leak.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.community import CommunityCommentRepository, CommunityPostRepository
from app.repositories.developers import (
    DeveloperBookmarkRepository,
    DeveloperFavoriteRepository,
    DeveloperProfileRepository,
    DeveloperSessionRepository,
)
from app.repositories.documentation import (
    DocumentationFeedbackRepository,
    DocumentationPageRepository,
    DocumentationVersionRepository,
)
from app.repositories.explorer import (
    GraphQlQueryRepository,
    PlaygroundSessionRepository,
    WebhookTestRepository,
)
from app.repositories.knowledge import KnowledgeArticleRepository, SearchIndexEntryRepository
from app.repositories.learning import LearningPathRepository, TutorialRepository
from app.repositories.plugins import PluginReviewRepository, PluginSubmissionRepository
from app.repositories.reporting import (
    PortalAuditRepository,
    PortalReportRepository,
    PortalStatisticRepository,
)
from app.repositories.samples import CodeSnippetRepository, SampleProjectRepository
from app.repositories.sdk import SdkDownloadRepository


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    profiles: DeveloperProfileRepository
    sessions: DeveloperSessionRepository
    bookmarks: DeveloperBookmarkRepository
    favorites: DeveloperFavoriteRepository

    documentation_pages: DocumentationPageRepository
    documentation_versions: DocumentationVersionRepository
    documentation_feedback: DocumentationFeedbackRepository

    tutorials: TutorialRepository
    learning_paths: LearningPathRepository

    sample_projects: SampleProjectRepository
    code_snippets: CodeSnippetRepository

    playground_sessions: PlaygroundSessionRepository
    graphql_queries: GraphQlQueryRepository
    webhook_tests: WebhookTestRepository

    sdk_downloads: SdkDownloadRepository

    plugin_submissions: PluginSubmissionRepository
    plugin_reviews: PluginReviewRepository

    community_posts: CommunityPostRepository
    community_comments: CommunityCommentRepository

    knowledge_articles: KnowledgeArticleRepository
    search_index: SearchIndexEntryRepository

    statistics: PortalStatisticRepository
    reports: PortalReportRepository
    audit: PortalAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        profiles=DeveloperProfileRepository(session, tenant_scope=tenant_scope),
        sessions=DeveloperSessionRepository(session, tenant_scope=tenant_scope),
        bookmarks=DeveloperBookmarkRepository(session, tenant_scope=tenant_scope),
        favorites=DeveloperFavoriteRepository(session, tenant_scope=tenant_scope),
        documentation_pages=DocumentationPageRepository(session, tenant_scope=tenant_scope),
        documentation_versions=DocumentationVersionRepository(session, tenant_scope=tenant_scope),
        documentation_feedback=DocumentationFeedbackRepository(session, tenant_scope=tenant_scope),
        tutorials=TutorialRepository(session, tenant_scope=tenant_scope),
        learning_paths=LearningPathRepository(session, tenant_scope=tenant_scope),
        sample_projects=SampleProjectRepository(session, tenant_scope=tenant_scope),
        code_snippets=CodeSnippetRepository(session, tenant_scope=tenant_scope),
        playground_sessions=PlaygroundSessionRepository(session, tenant_scope=tenant_scope),
        graphql_queries=GraphQlQueryRepository(session, tenant_scope=tenant_scope),
        webhook_tests=WebhookTestRepository(session, tenant_scope=tenant_scope),
        sdk_downloads=SdkDownloadRepository(session, tenant_scope=tenant_scope),
        plugin_submissions=PluginSubmissionRepository(session, tenant_scope=tenant_scope),
        plugin_reviews=PluginReviewRepository(session, tenant_scope=tenant_scope),
        community_posts=CommunityPostRepository(session, tenant_scope=tenant_scope),
        community_comments=CommunityCommentRepository(session, tenant_scope=tenant_scope),
        knowledge_articles=KnowledgeArticleRepository(session, tenant_scope=tenant_scope),
        search_index=SearchIndexEntryRepository(session, tenant_scope=tenant_scope),
        statistics=PortalStatisticRepository(session, tenant_scope=tenant_scope),
        reports=PortalReportRepository(session, tenant_scope=tenant_scope),
        audit=PortalAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
