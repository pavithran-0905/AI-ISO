"""Integration tests for every repository, against real PostgreSQL."""

from __future__ import annotations

import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import CommunityComment, CommunityPost
from app.models.developers import DeveloperBookmark, DeveloperProfile, DeveloperSession
from app.models.documentation import DocumentationFeedback, DocumentationPage, DocumentationVersion
from app.models.enums import (
    CommunityPostType,
    ContentStatus,
    FeedbackSentiment,
    KnowledgeArticleCategory,
    ModerationStatus,
    PlaygroundExampleType,
    PluginSubmissionStatus,
    PortalAuditAction,
    ReportFormat,
    ReportKind,
    ReportStatus,
    SampleProjectCategory,
    SearchContentType,
)
from app.models.explorer import GraphQlQuery, PlaygroundSession, WebhookTest
from app.models.knowledge import KnowledgeArticle, SearchIndexEntry
from app.models.learning import LearningPath, Tutorial
from app.models.plugins import PluginReview, PluginSubmission
from app.models.reporting import PortalAudit, PortalReport, PortalStatistic
from app.models.samples import CodeSnippet, SampleProject
from app.models.sdk import SdkDownload
from app.services.bundle import Repositories
from tests.conftest import hours_ago, hours_ahead, utcnow


class TestDeveloperRepositories:
    async def test_profile_find_by_user(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        profile = await repos.profiles.create(
            DeveloperProfile(organization_id=organization_id, user_id="u1", display_name="Ada")
        )
        found = await repos.profiles.find_by_user(organization_id, user_id="u1")
        assert found is not None
        assert found.id == profile.id

    async def test_session_list_active_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.sessions.create(
            DeveloperSession(
                organization_id=organization_id,
                user_id="u1",
                issued_at=utcnow(),
                expires_at=hours_ahead(1),
            )
        )
        active = await repos.sessions.list_active(organization_id)
        assert len(active) == 1
        assert organization_id in await repos.sessions.list_organization_ids()

    async def test_bookmark_find_and_list(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        content_id = uuid.uuid4()
        bookmark = await repos.bookmarks.create(
            DeveloperBookmark(
                organization_id=organization_id,
                user_id="u1",
                content_type=SearchContentType.DOCUMENTATION,
                content_id=content_id,
            )
        )
        found = await repos.bookmarks.find(
            organization_id,
            user_id="u1",
            content_type=SearchContentType.DOCUMENTATION,
            content_id=content_id,
        )
        assert found is not None
        assert found.id == bookmark.id
        assert len(await repos.bookmarks.list_for_user(organization_id, user_id="u1")) == 1

    async def test_favorite_find_and_list(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        content_id = uuid.uuid4()
        await repos.favorites.create(
            __import__("app.models.developers", fromlist=["DeveloperFavorite"]).DeveloperFavorite(
                organization_id=organization_id,
                user_id="u1",
                content_type=SearchContentType.TUTORIAL,
                content_id=content_id,
            )
        )
        found = await repos.favorites.find(
            organization_id,
            user_id="u1",
            content_type=SearchContentType.TUTORIAL,
            content_id=content_id,
        )
        assert found is not None
        assert len(await repos.favorites.list_for_user(organization_id, user_id="u1")) == 1


class TestDocumentationRepositories:
    async def test_find_by_slug_and_list_published(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.documentation_pages.create(
            DocumentationPage(
                organization_id=organization_id,
                slug="intro",
                title="Intro",
                status=ContentStatus.PUBLISHED,
                published_at=utcnow(),
            )
        )
        await repos.documentation_pages.create(
            DocumentationPage(organization_id=organization_id, slug="draft-page", title="Draft")
        )
        found = await repos.documentation_pages.find_by_slug(organization_id, slug="intro")
        assert found is not None
        published = await repos.documentation_pages.list_published(organization_id)
        assert len(published) == 1
        assert len(await repos.documentation_pages.list_recent(organization_id)) == 2
        assert organization_id in await repos.documentation_pages.list_organization_ids()

    async def test_version_and_feedback(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        page = await repos.documentation_pages.create(
            DocumentationPage(organization_id=organization_id, slug="p2", title="P2")
        )
        await repos.documentation_versions.create(
            DocumentationVersion(
                organization_id=organization_id,
                documentation_page_id=page.id,
                version_label="v1",
                content="hello",
                published_at=utcnow(),
            )
        )
        assert len(await repos.documentation_versions.list_for_page(page.id)) == 1

        await repos.documentation_feedback.create(
            DocumentationFeedback(
                organization_id=organization_id,
                documentation_page_id=page.id,
                user_id="u1",
                sentiment=FeedbackSentiment.HELPFUL,
            )
        )
        assert len(await repos.documentation_feedback.list_for_page(page.id)) == 1


class TestLearningRepositories:
    async def test_tutorial_find_and_list_published(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.tutorials.create(
            Tutorial(
                organization_id=organization_id,
                slug="t1",
                title="T1",
                status=ContentStatus.PUBLISHED,
                published_at=utcnow(),
            )
        )
        found = await repos.tutorials.find_by_slug(organization_id, slug="t1")
        assert found is not None
        assert len(await repos.tutorials.list_published(organization_id)) == 1
        assert organization_id in await repos.tutorials.list_organization_ids()

    async def test_learning_path_find_and_list_published(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.learning_paths.create(
            LearningPath(
                organization_id=organization_id,
                slug="lp1",
                title="LP1",
                status=ContentStatus.PUBLISHED,
                published_at=utcnow(),
            )
        )
        found = await repos.learning_paths.find_by_slug(organization_id, slug="lp1")
        assert found is not None
        assert len(await repos.learning_paths.list_published(organization_id)) == 1


class TestSamplesRepositories:
    async def test_find_by_slug_and_list_published_by_category(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.sample_projects.create(
            SampleProject(
                organization_id=organization_id,
                slug="s1",
                title="S1",
                category=SampleProjectCategory.STARTER,
                status=ContentStatus.PUBLISHED,
                published_at=utcnow(),
            )
        )
        found = await repos.sample_projects.find_by_slug(organization_id, slug="s1")
        assert found is not None
        by_category = await repos.sample_projects.list_published(
            organization_id, category=SampleProjectCategory.STARTER
        )
        assert len(by_category) == 1
        assert organization_id in await repos.sample_projects.list_organization_ids()

    async def test_code_snippet_list_for_sample(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        sample = await repos.sample_projects.create(
            SampleProject(
                organization_id=organization_id,
                slug="s2",
                title="S2",
                category=SampleProjectCategory.AI,
            )
        )
        await repos.code_snippets.create(
            CodeSnippet(
                organization_id=organization_id,
                sample_project_id=sample.id,
                title="Snippet",
                language="python",
                code="print(1)",
            )
        )
        assert len(await repos.code_snippets.list_for_sample(sample.id)) == 1


class TestExplorerRepositories:
    async def test_playground_session_active_and_for_user(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.playground_sessions.create(
            PlaygroundSession(
                organization_id=organization_id,
                user_id="u1",
                example_type=PlaygroundExampleType.REST,
                started_at=utcnow(),
                last_active_at=utcnow(),
            )
        )
        assert len(await repos.playground_sessions.list_active(organization_id)) == 1
        assert (
            len(await repos.playground_sessions.list_for_user(organization_id, user_id="u1")) == 1
        )
        assert organization_id in await repos.playground_sessions.list_organization_ids()

    async def test_graphql_query_list_for_user(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.graphql_queries.create(
            GraphQlQuery(organization_id=organization_id, user_id="u1", query_text="{ hello }")
        )
        assert len(await repos.graphql_queries.list_for_user(organization_id, user_id="u1")) == 1

    async def test_webhook_test_list_for_user(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.webhook_tests.create(
            WebhookTest(
                organization_id=organization_id, user_id="u1", target_url="https://example.com/hook"
            )
        )
        assert len(await repos.webhook_tests.list_for_user(organization_id, user_id="u1")) == 1


class TestSdkRepository:
    async def test_list_for_user_since_and_exists(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.sdk_downloads.create(
            SdkDownload(
                organization_id=organization_id,
                user_id="u1",
                language="python",
                version_label="1.0.0",
                downloaded_at=utcnow(),
            )
        )
        assert len(await repos.sdk_downloads.list_for_user(organization_id, user_id="u1")) == 1
        assert await repos.sdk_downloads.count_since(organization_id, since=hours_ago(1)) == 1
        assert len(await repos.sdk_downloads.list_since(organization_id, since=hours_ago(1))) == 1
        assert await repos.sdk_downloads.exists_for_version(
            organization_id, language="python", version_label="1.0.0"
        )
        assert not await repos.sdk_downloads.exists_for_version(
            organization_id, language="python", version_label="9.9.9"
        )
        assert organization_id in await repos.sdk_downloads.list_organization_ids()


class TestPluginsRepositories:
    async def test_submission_list_for_user_and_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.plugin_submissions.create(
            PluginSubmission(
                organization_id=organization_id,
                user_id="u1",
                plugin_name="my-plugin",
                version_label="1.0.0",
                checksum_sha256="a" * 64,
                submitted_at=utcnow(),
            )
        )
        assert len(await repos.plugin_submissions.list_for_user(organization_id, user_id="u1")) == 1
        assert (
            len(
                await repos.plugin_submissions.list_recent(
                    organization_id, status=PluginSubmissionStatus.SUBMITTED
                )
            )
            == 1
        )
        assert organization_id in await repos.plugin_submissions.list_organization_ids()

    async def test_submission_list_stale_validating(
        self, repos: Repositories, db_session: AsyncSession, organization_id: uuid.UUID
    ) -> None:
        submission = await repos.plugin_submissions.create(
            PluginSubmission(
                organization_id=organization_id,
                user_id="u1",
                plugin_name="stale-plugin",
                version_label="1.0.0",
                checksum_sha256="b" * 64,
                status=PluginSubmissionStatus.VALIDATING,
                submitted_at=hours_ago(48),
            )
        )
        # staleness is judged by how long the row has sat untouched
        # (updated_at), not by its original submission time -- backdate it
        # directly to simulate a submission that has been stuck for days.
        await db_session.execute(
            update(PluginSubmission)
            .where(PluginSubmission.id == submission.id)
            .values(updated_at=hours_ago(48))
        )
        stale = await repos.plugin_submissions.list_stale_validating(
            organization_id, before=hours_ago(1)
        )
        assert any(row.id == submission.id for row in stale)

    async def test_review_list_for_submission(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        submission = await repos.plugin_submissions.create(
            PluginSubmission(
                organization_id=organization_id,
                user_id="u1",
                plugin_name="p3",
                version_label="1.0.0",
                checksum_sha256="c" * 64,
                submitted_at=utcnow(),
            )
        )
        await repos.plugin_reviews.create(
            PluginReview(
                organization_id=organization_id,
                plugin_submission_id=submission.id,
                reviewer_id="rev1",
                decision="approved",
                reviewed_at=utcnow(),
            )
        )
        assert len(await repos.plugin_reviews.list_for_submission(submission.id)) == 1


class TestCommunityRepositories:
    async def test_post_list_visible_by_type(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.community_posts.create(
            CommunityPost(
                organization_id=organization_id,
                user_id="u1",
                post_type=CommunityPostType.QUESTION,
                title="Q1",
                body="body",
            )
        )
        await repos.community_posts.create(
            CommunityPost(
                organization_id=organization_id,
                user_id="u1",
                post_type=CommunityPostType.QUESTION,
                title="Hidden",
                body="body",
                moderation_status=ModerationStatus.HIDDEN,
            )
        )
        visible = await repos.community_posts.list_visible(
            organization_id, post_type=CommunityPostType.QUESTION
        )
        assert len(visible) == 1
        assert organization_id in await repos.community_posts.list_organization_ids()

    async def test_comment_list_for_post(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        post = await repos.community_posts.create(
            CommunityPost(
                organization_id=organization_id,
                user_id="u1",
                post_type=CommunityPostType.DISCUSSION,
                title="D1",
                body="body",
            )
        )
        await repos.community_comments.create(
            CommunityComment(
                organization_id=organization_id,
                community_post_id=post.id,
                user_id="u2",
                body="reply",
            )
        )
        assert len(await repos.community_comments.list_for_post(post.id)) == 1


class TestKnowledgeRepositories:
    async def test_article_find_and_list_published(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.knowledge_articles.create(
            KnowledgeArticle(
                organization_id=organization_id,
                slug="k1",
                title="K1",
                content="content",
                category=KnowledgeArticleCategory.TECHNICAL,
                status=ContentStatus.PUBLISHED,
                published_at=utcnow(),
            )
        )
        found = await repos.knowledge_articles.find_by_slug(organization_id, slug="k1")
        assert found is not None
        assert len(await repos.knowledge_articles.list_published(organization_id)) == 1
        assert organization_id in await repos.knowledge_articles.list_organization_ids()

    async def test_search_index_find_and_list(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        content_id = uuid.uuid4()
        await repos.search_index.create(
            SearchIndexEntry(
                organization_id=organization_id,
                content_type=SearchContentType.DOCUMENTATION,
                content_id=content_id,
                title="Entry",
                indexed_at=utcnow(),
            )
        )
        found = await repos.search_index.find(
            organization_id, content_type=SearchContentType.DOCUMENTATION, content_id=content_id
        )
        assert found is not None
        assert len(await repos.search_index.list_all(organization_id)) == 1
        assert organization_id in await repos.search_index.list_organization_ids()


class TestReportingRepositories:
    async def test_statistic_find_window_and_range(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        window_start = utcnow()
        await repos.statistics.create(
            PortalStatistic(
                organization_id=organization_id,
                window_start=window_start,
                window_end=hours_ahead(1),
            )
        )
        found = await repos.statistics.find_window(organization_id, window_start=window_start)
        assert found is not None
        assert len(await repos.statistics.list_range(organization_id, since=hours_ago(1))) == 1

    async def test_report_list_recent_filters(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.reports.create(
            PortalReport(
                organization_id=organization_id,
                kind=ReportKind.PORTAL_USAGE,
                report_format=ReportFormat.JSON,
                title="Usage",
                status=ReportStatus.COMPLETED,
                period_start=hours_ago(1),
                period_end=utcnow(),
            )
        )
        assert (
            len(await repos.reports.list_recent(organization_id, kind=ReportKind.PORTAL_USAGE)) == 1
        )
        assert (
            len(await repos.reports.list_recent(organization_id, status=ReportStatus.COMPLETED))
            == 1
        )

    async def test_audit_list_recent_and_for_entity(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        entity_id = uuid.uuid4()
        await repos.audit.create(
            PortalAudit(
                organization_id=organization_id,
                action=PortalAuditAction.ADMINISTRATIVE,
                entity_type="x",
                entity_id=entity_id,
                summary="s",
                occurred_at=utcnow(),
            )
        )
        assert len(await repos.audit.list_recent(organization_id)) == 1
        assert len(await repos.audit.list_for_entity("x", entity_id)) == 1

    async def test_audit_since_filter(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.audit.create(
            PortalAudit(
                organization_id=organization_id,
                action=PortalAuditAction.ADMINISTRATIVE,
                entity_type="x",
                entity_id=uuid.uuid4(),
                summary="old",
                occurred_at=hours_ago(48),
            )
        )
        assert len(await repos.audit.list_recent(organization_id, since=hours_ago(1))) == 0
