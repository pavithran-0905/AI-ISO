"""Unit/integration tests for every service, against real PostgreSQL."""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import (
    CommunityPostStatus,
    CommunityPostType,
    ContentStatus,
    FeedbackSentiment,
    KnowledgeArticleCategory,
    PlaygroundExampleType,
    PluginReviewDecision,
    ReportKind,
    SampleProjectCategory,
    SearchContentType,
    TutorialDifficulty,
)
from app.services import documentation as documentation_services
from app.services import explorer as explorer_services
from app.services import learning as learning_services
from app.services import plugins as plugins_services
from app.services import samples as samples_services
from app.services.assistant import AssistantService
from app.services.audit import AuditService
from app.services.bundle import Repositories
from app.services.community import CommunityCommentService, CommunityPostService
from app.services.developers import (
    BookmarkService,
    DeveloperProfileService,
    DeveloperSessionService,
    FavoriteService,
)
from app.services.documentation import DocumentationFeedbackService, DocumentationPageService
from app.services.explorer import GraphQlQueryService, PlaygroundService, WebhookTestService
from app.services.knowledge import KnowledgeArticleService, SearchIndexService
from app.services.learning import LearningPathService, TutorialService
from app.services.plugins import PluginSubmissionService
from app.services.reports import ReportService
from app.services.samples import CodeSnippetService, SampleProjectService
from app.services.sdk import SdkDownloadService
from app.services.search import SearchService
from app.services.statistics import StatisticsService
from tests.conftest import RecordingNotifier, RecordingPublisher, hours_ago, utcnow


class TestDeveloperServices:
    async def test_profile_get_or_create_is_idempotent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = DeveloperProfileService(repos.profiles)
        first = await service.get_or_create(organization_id, user_id="u1")
        second = await service.get_or_create(organization_id, user_id="u1")
        assert first.id == second.id

    async def test_profile_update(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = DeveloperProfileService(repos.profiles)
        profile = await service.get_or_create(organization_id, user_id="u1")
        updated = await service.update(profile, display_name="Ada", bio="hi")
        assert updated.display_name == "Ada"
        assert updated.bio == "hi"

    async def test_session_login_publishes_and_expire(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = DeveloperSessionService(repos.sessions, publish=publisher)
        session = await service.login(organization_id, user_id="u1", now=utcnow(), max_age_hours=12)
        assert "DeveloperLoggedIn" in publisher.names()
        assert not service.is_expired(session, now=utcnow())
        expired = await service.expire(session)
        assert expired.status == "expired"

    async def test_bookmark_add_idempotent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = BookmarkService(repos.bookmarks)
        content_id = uuid.uuid4()
        first = await service.add(
            organization_id,
            user_id="u1",
            content_type=SearchContentType.DOCUMENTATION,
            content_id=content_id,
        )
        second = await service.add(
            organization_id,
            user_id="u1",
            content_type=SearchContentType.DOCUMENTATION,
            content_id=content_id,
        )
        assert first.id == second.id

    async def test_favorite_add_idempotent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = FavoriteService(repos.favorites)
        content_id = uuid.uuid4()
        first = await service.add(
            organization_id,
            user_id="u1",
            content_type=SearchContentType.TUTORIAL,
            content_id=content_id,
        )
        second = await service.add(
            organization_id,
            user_id="u1",
            content_type=SearchContentType.TUTORIAL,
            content_id=content_id,
        )
        assert first.id == second.id


class TestDocumentationServices:
    async def test_create_and_publish_snapshots_version_and_publishes(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
    ) -> None:
        audit = AuditService(repos.audit)
        service = DocumentationPageService(
            repos.documentation_pages, repos.documentation_versions, publish=publisher, audit=audit
        )
        page = await service.create(organization_id, slug="intro", title="Intro", content="hello")
        published = await service.transition(
            page, target=ContentStatus.PUBLISHED, now=utcnow(), actor_id="u1"
        )
        assert published.status == "published"
        assert len(await repos.documentation_versions.list_for_page(page.id)) == 1
        assert "DocumentationPublished" in publisher.names()
        assert len(await repos.audit.list_recent(organization_id)) == 1

    async def test_invalid_transition_raises(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = DocumentationPageService(repos.documentation_pages, repos.documentation_versions)
        page = await service.create(organization_id, slug="p2", title="P2", content="x")
        await service.transition(page, target=ContentStatus.PUBLISHED, now=utcnow())
        await service.transition(page, target=ContentStatus.ARCHIVED, now=utcnow())
        with pytest.raises(documentation_services.TransitionRefusedError):
            await service.transition(page, target=ContentStatus.PUBLISHED, now=utcnow())

    async def test_feedback_submit(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        page_service = DocumentationPageService(
            repos.documentation_pages, repos.documentation_versions
        )
        page = await page_service.create(organization_id, slug="p3", title="P3", content="x")
        feedback_service = DocumentationFeedbackService(repos.documentation_feedback)
        feedback = await feedback_service.submit(
            organization_id,
            documentation_page_id=page.id,
            user_id="u1",
            sentiment=FeedbackSentiment.HELPFUL,
        )
        assert feedback.sentiment == "helpful"


class TestLearningServices:
    async def test_tutorial_publish_notifies_and_complete_publishes_without_row(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        service = TutorialService(repos.tutorials, publish=publisher, notifier=notifier)  # type: ignore[arg-type]
        tutorial = await service.create(
            organization_id, slug="t1", title="T1", difficulty=TutorialDifficulty.BEGINNER
        )
        await service.transition(tutorial, target=ContentStatus.PUBLISHED, now=utcnow())
        assert ("notify_tutorial_available", {"title": "T1"}) in notifier.calls
        await service.complete(tutorial, user_id="u2")
        assert "TutorialCompleted" in publisher.names()

    async def test_invalid_transition_raises(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = TutorialService(repos.tutorials)
        tutorial = await service.create(organization_id, slug="t2", title="T2")
        await service.transition(tutorial, target=ContentStatus.PUBLISHED, now=utcnow())
        await service.transition(tutorial, target=ContentStatus.ARCHIVED, now=utcnow())
        with pytest.raises(learning_services.TransitionRefusedError):
            await service.transition(tutorial, target=ContentStatus.PUBLISHED, now=utcnow())

    async def test_learning_path_create(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = LearningPathService(repos.learning_paths)
        path = await service.create(
            organization_id, slug="lp1", title="LP1", tutorial_ids=["a", "b"]
        )
        assert path.tutorial_ids == ["a", "b"]


class TestSamplesServices:
    async def test_project_create_and_transition(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = SampleProjectService(repos.sample_projects)
        project = await service.create(
            organization_id, slug="s1", title="S1", category=SampleProjectCategory.STARTER
        )
        published = await service.transition(project, target=ContentStatus.PUBLISHED, now=utcnow())
        assert published.published_at is not None

    async def test_invalid_transition_raises(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = SampleProjectService(repos.sample_projects)
        project = await service.create(
            organization_id, slug="s2", title="S2", category=SampleProjectCategory.AI
        )
        await service.transition(project, target=ContentStatus.PUBLISHED, now=utcnow())
        await service.transition(project, target=ContentStatus.ARCHIVED, now=utcnow())
        with pytest.raises(samples_services.TransitionRefusedError):
            await service.transition(project, target=ContentStatus.PUBLISHED, now=utcnow())

    async def test_snippet_create(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = CodeSnippetService(repos.code_snippets)
        snippet = await service.create(
            organization_id, title="Snippet", language="python", code="print(1)"
        )
        assert snippet.language == "python"


class TestExplorerServices:
    async def test_playground_start_run_expire(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = PlaygroundService(repos.playground_sessions)
        session = await service.start(
            organization_id, user_id="u1", example_type=PlaygroundExampleType.REST, now=utcnow()
        )
        ran = await service.run(session, code="print(1)", output="1", now=utcnow())
        assert ran.output == "1"
        expired = await service.expire(ran)
        assert expired.status == "expired"

    async def test_graphql_save_rejects_malformed(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = GraphQlQueryService(repos.graphql_queries)
        saved = await service.save(organization_id, user_id="u1", name="q1", query_text="{ hello }")
        assert saved.is_saved is True
        with pytest.raises(explorer_services.MalformedGraphQlQueryError):
            await service.save(organization_id, user_id="u1", name="bad", query_text="not graphql")

    async def test_webhook_test_create_and_record_result(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = WebhookTestService(repos.webhook_tests)
        test = await service.create(
            organization_id, user_id="u1", target_url="https://example.com/hook", payload={"x": 1}
        )
        recorded = await service.record_result(
            test, response_status_code=204, response_body="", now=utcnow()
        )
        assert recorded.status == "succeeded"


class TestSdkService:
    async def test_record_notifies_only_on_first_sighting(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        service = SdkDownloadService(repos.sdk_downloads, publish=publisher, notifier=notifier)  # type: ignore[arg-type]
        await service.record(
            organization_id, user_id="u1", language="python", version="1.0.0", now=utcnow()
        )
        assert ("notify_sdk_released", {"language": "python", "version": "1.0.0"}) in notifier.calls
        notifier.calls.clear()
        await service.record(
            organization_id, user_id="u2", language="python", version="1.0.0", now=utcnow()
        )
        assert notifier.calls == []
        assert publisher.names().count("SDKDownloaded") == 2


class TestPluginsService:
    async def test_full_lifecycle_approved(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        audit = AuditService(repos.audit)
        service = PluginSubmissionService(
            repos.plugin_submissions,
            repos.plugin_reviews,
            publish=publisher,
            audit=audit,
            notifier=notifier,  # type: ignore[arg-type]
        )
        submission = await service.submit(
            organization_id,
            user_id="u1",
            plugin_name="my-plugin",
            version="1.0.0",
            checksum_sha256="a" * 64,
            now=utcnow(),
        )
        assert "PluginSubmitted" in publisher.names()

        await service.begin_validation(submission)
        await service.submit_for_approval(submission, now=utcnow())
        review = await service.review(
            submission, reviewer_id="rev1", decision=PluginReviewDecision.APPROVED, now=utcnow()
        )
        assert review.decision == "approved"
        assert submission.status == "approved"
        assert "PluginPublished" in publisher.names()
        assert ("notify_plugin_approved", {"plugin_name": "my-plugin"}) in notifier.calls

    async def test_rejected_notifies_with_reason(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        service = PluginSubmissionService(
            repos.plugin_submissions, repos.plugin_reviews, notifier=notifier  # type: ignore[arg-type]
        )
        submission = await service.submit(
            organization_id,
            user_id="u1",
            plugin_name="bad-plugin",
            version="1.0.0",
            checksum_sha256="b" * 64,
            now=utcnow(),
        )
        await service.begin_validation(submission)
        await service.submit_for_approval(submission, now=utcnow())
        await service.review(
            submission,
            reviewer_id="rev1",
            decision=PluginReviewDecision.REJECTED,
            comments="checksum mismatch",
            now=utcnow(),
        )
        assert submission.status == "rejected"
        assert (
            "notify_plugin_rejected",
            {"plugin_name": "bad-plugin", "reason": "checksum mismatch"},
        ) in notifier.calls

    async def test_changes_requested_leaves_status_untouched(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = PluginSubmissionService(repos.plugin_submissions, repos.plugin_reviews)
        submission = await service.submit(
            organization_id,
            user_id="u1",
            plugin_name="wip-plugin",
            version="1.0.0",
            checksum_sha256="c" * 64,
            now=utcnow(),
        )
        await service.begin_validation(submission)
        await service.submit_for_approval(submission, now=utcnow())
        await service.review(
            submission,
            reviewer_id="rev1",
            decision=PluginReviewDecision.CHANGES_REQUESTED,
            now=utcnow(),
        )
        assert submission.status == "pending_approval"

    async def test_invalid_transition_raises(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = PluginSubmissionService(repos.plugin_submissions, repos.plugin_reviews)
        submission = await service.submit(
            organization_id,
            user_id="u1",
            plugin_name="p4",
            version="1.0.0",
            checksum_sha256="d" * 64,
            now=utcnow(),
        )
        with pytest.raises(plugins_services.TransitionRefusedError):
            await service.submit_for_approval(submission, now=utcnow())


class TestCommunityServices:
    async def test_post_create_publishes_and_transition(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = CommunityPostService(repos.community_posts, publish=publisher)
        post = await service.create(
            organization_id,
            user_id="u1",
            post_type=CommunityPostType.QUESTION,
            title="Q1",
            body="body",
        )
        assert "CommunityPostCreated" in publisher.names()
        answered = await service.transition(post, target=CommunityPostStatus.ANSWERED)
        assert answered.status == "answered"

    async def test_accept_comment_marks_answered(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        post_service = CommunityPostService(repos.community_posts)
        post = await post_service.create(
            organization_id,
            user_id="u1",
            post_type=CommunityPostType.QUESTION,
            title="Q2",
            body="body",
        )
        comment_service = CommunityCommentService(repos.community_comments)
        comment = await comment_service.create(
            organization_id, post=post, user_id="u2", body="answer"
        )
        answered = await post_service.accept_comment(post, comment=comment)
        assert answered.accepted_comment_id == comment.id
        assert answered.status == "answered"

    async def test_comment_notifies_only_when_not_author(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        post_service = CommunityPostService(repos.community_posts)
        post = await post_service.create(
            organization_id,
            user_id="u1",
            post_type=CommunityPostType.DISCUSSION,
            title="D1",
            body="body",
        )
        comment_service = CommunityCommentService(repos.community_comments, notifier=notifier)  # type: ignore[arg-type]
        await comment_service.create(organization_id, post=post, user_id="u1", body="self reply")
        assert notifier.calls == []
        await comment_service.create(organization_id, post=post, user_id="u2", body="other reply")
        assert ("notify_community_reply", {"post_title": "D1"}) in notifier.calls

    async def test_comment_accept_and_reputation(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        post_service = CommunityPostService(repos.community_posts)
        post = await post_service.create(
            organization_id,
            user_id="u1",
            post_type=CommunityPostType.QUESTION,
            title="Q3",
            body="body",
        )
        comment_service = CommunityCommentService(repos.community_comments)
        comment = await comment_service.create(
            organization_id, post=post, user_id="u2", body="answer"
        )
        accepted = await comment_service.accept(comment, upvotes=5)
        assert comment_service.reputation_for(accepted) == 20


class TestKnowledgeServices:
    async def test_article_create_and_publish(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = KnowledgeArticleService(repos.knowledge_articles)
        article = await service.create(
            organization_id,
            slug="k1",
            title="K1",
            content="content",
            category=KnowledgeArticleCategory.TECHNICAL,
        )
        published = await service.transition(article, target=ContentStatus.PUBLISHED, now=utcnow())
        assert published.published_at is not None

    async def test_search_index_upserts(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = SearchIndexService(repos.search_index)
        content_id = uuid.uuid4()
        first = await service.index(
            organization_id,
            content_type=SearchContentType.KNOWLEDGE,
            content_id=content_id,
            title="Old title",
            summary="old",
            keywords=["a"],
            now=utcnow(),
        )
        second = await service.index(
            organization_id,
            content_type=SearchContentType.KNOWLEDGE,
            content_id=content_id,
            title="New title",
            summary="new",
            keywords=["b"],
            now=utcnow(),
        )
        assert first.id == second.id
        assert second.title == "New title"
        assert len(await repos.search_index.list_all(organization_id)) == 1


class TestSearchAndAssistantServices:
    async def test_search_ranks_and_publishes(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        index_service = SearchIndexService(repos.search_index)
        await index_service.index(
            organization_id,
            content_type=SearchContentType.DOCUMENTATION,
            content_id=uuid.uuid4(),
            title="Getting Started with Webhooks",
            summary="How to configure webhooks",
            keywords=["webhook", "setup"],
            now=utcnow(),
        )
        service = SearchService(repos.search_index, publish=publisher)
        results = await service.search(organization_id, query="webhook setup", user_id="u1")
        assert len(results) == 1
        assert "SearchPerformed" in publisher.names()

    async def test_assistant_answers_and_notifies_on_confidence(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        index_service = SearchIndexService(repos.search_index)
        await index_service.index(
            organization_id,
            content_type=SearchContentType.DOCUMENTATION,
            content_id=uuid.uuid4(),
            title="Getting Started with Webhooks",
            summary="How to configure webhooks",
            keywords=["webhook", "setup"],
            now=utcnow(),
        )
        service = AssistantService(repos.search_index, publish=publisher, notifier=notifier)  # type: ignore[arg-type]
        answer = await service.ask(
            organization_id, question="how do I set up webhooks", user_id="u1"
        )
        assert answer.content_id is not None
        assert "AIAssistantUsed" in publisher.names()
        assert any(call[0] == "notify_ai_recommendation" for call in notifier.calls)

    async def test_assistant_declines_without_notifying(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        service = AssistantService(repos.search_index, notifier=notifier)  # type: ignore[arg-type]
        answer = await service.ask(organization_id, question="anything at all", user_id="u1")
        assert answer.content_id is None
        assert notifier.calls == []


class TestStatisticsAndReportsServices:
    async def test_roll_up_window_is_idempotent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = StatisticsService(repos.statistics)
        window_start = utcnow()
        first = await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=utcnow(),
            portal_visit_count=1,
            documentation_view_count=0,
            sdk_download_count=0,
            search_query_count=0,
            tutorial_completion_count=0,
            plugin_publication_count=0,
            community_activity_count=0,
            ai_assistant_usage_count=0,
        )
        second = await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=utcnow(),
            portal_visit_count=5,
            documentation_view_count=0,
            sdk_download_count=0,
            search_query_count=0,
            tutorial_completion_count=0,
            plugin_publication_count=0,
            community_activity_count=0,
            ai_assistant_usage_count=0,
        )
        assert first.id == second.id
        assert second.portal_visit_count == 5
        assert len(await service.list_range(organization_id, since=hours_ago(1))) == 1

    async def test_report_generate(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = ReportService(repos.reports)
        report = await service.generate(
            organization_id,
            kind=ReportKind.PORTAL_USAGE,
            title="Usage report",
            period_start=hours_ago(1),
            period_end=utcnow(),
            row_count=10,
            now=utcnow(),
        )
        assert report.status == "completed"
        assert report.row_count == 10


class TestAuditService:
    async def test_record_and_list_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        from app.models.enums import PortalAuditAction

        service = AuditService(repos.audit)
        await service.record(
            organization_id=organization_id,
            action=PortalAuditAction.ADMINISTRATIVE,
            entity_type="x",
            entity_id=uuid.uuid4(),
            summary="did a thing",
            occurred_at=utcnow(),
        )
        entries = await service.list_recent(organization_id)
        assert len(entries) == 1
        assert entries[0].summary == "did a thing"
