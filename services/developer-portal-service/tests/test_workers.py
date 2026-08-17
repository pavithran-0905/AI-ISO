"""Integration tests for every worker's ``tick()``, against real
PostgreSQL, exercised directly rather than through the scheduler."""

from __future__ import annotations

import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import PlaygroundExampleType, PluginSubmissionStatus
from app.models.explorer import PlaygroundSession
from app.models.plugins import PluginSubmission
from app.services.bundle import build_repositories
from app.workers.playground_session_expiry_sweep import PlaygroundSessionExpirySweepWorker
from app.workers.plugin_submission_staleness_sweep import PluginSubmissionStalenessSweepWorker
from app.workers.search_index_rebuild import SearchIndexRebuildWorker
from app.workers.session_expiry_sweep import DeveloperSessionExpirySweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from tests.conftest import RecordingNotifier, hours_ago, utcnow


class TestSessionExpirySweepWorker:
    async def test_expires_only_past_expiry(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> None:
        repos = build_repositories(db_session)
        from app.models.developers import DeveloperSession

        expired_session = await repos.sessions.create(
            DeveloperSession(
                organization_id=organization_id,
                user_id="u1",
                issued_at=hours_ago(20),
                expires_at=hours_ago(1),
            )
        )
        live_session = await repos.sessions.create(
            DeveloperSession(
                organization_id=organization_id,
                user_id="u2",
                issued_at=utcnow(),
                expires_at=hours_ago(-10),
            )
        )
        await db_session.flush()

        worker = DeveloperSessionExpirySweepWorker(db_session_factory)
        checked = await worker.tick()
        assert checked >= 2

        await db_session.refresh(expired_session)
        await db_session.refresh(live_session)
        assert expired_session.status == "expired"
        assert live_session.status == "active"


class TestPlaygroundSessionExpirySweepWorker:
    async def test_expires_only_stale_sessions(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> None:
        repos = build_repositories(db_session)
        stale_session = await repos.playground_sessions.create(
            PlaygroundSession(
                organization_id=organization_id,
                user_id="u1",
                example_type=PlaygroundExampleType.REST,
                started_at=hours_ago(5),
                last_active_at=hours_ago(5),
            )
        )
        fresh_session = await repos.playground_sessions.create(
            PlaygroundSession(
                organization_id=organization_id,
                user_id="u2",
                example_type=PlaygroundExampleType.REST,
                started_at=utcnow(),
                last_active_at=utcnow(),
            )
        )
        await db_session.flush()

        worker = PlaygroundSessionExpirySweepWorker(db_session_factory, max_age_hours=2)
        expired = await worker.tick()
        assert expired >= 1

        await db_session.refresh(stale_session)
        await db_session.refresh(fresh_session)
        assert stale_session.status == "expired"
        assert fresh_session.status == "active"


class TestSearchIndexRebuildWorker:
    async def test_indexes_published_content_across_types(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> None:
        from app.models.enums import ContentStatus, KnowledgeArticleCategory, SampleProjectCategory
        from app.models.knowledge import KnowledgeArticle
        from app.models.learning import Tutorial
        from app.models.samples import SampleProject

        repos = build_repositories(db_session)
        await repos.documentation_pages.create(
            __import__(
                "app.models.documentation", fromlist=["DocumentationPage"]
            ).DocumentationPage(
                organization_id=organization_id,
                slug="doc1",
                title="Doc1",
                content="hello world",
                status=ContentStatus.PUBLISHED,
                published_at=utcnow(),
            )
        )
        await repos.tutorials.create(
            Tutorial(
                organization_id=organization_id,
                slug="tut1",
                title="Tut1",
                status=ContentStatus.PUBLISHED,
                published_at=utcnow(),
            )
        )
        await repos.sample_projects.create(
            SampleProject(
                organization_id=organization_id,
                slug="samp1",
                title="Samp1",
                category=SampleProjectCategory.STARTER,
                status=ContentStatus.PUBLISHED,
                published_at=utcnow(),
            )
        )
        await repos.knowledge_articles.create(
            KnowledgeArticle(
                organization_id=organization_id,
                slug="know1",
                title="Know1",
                content="content",
                category=KnowledgeArticleCategory.TECHNICAL,
                status=ContentStatus.PUBLISHED,
                published_at=utcnow(),
            )
        )
        await repos.plugin_submissions.create(
            PluginSubmission(
                organization_id=organization_id,
                user_id="u1",
                plugin_name="approved-plugin",
                version_label="1.0.0",
                checksum_sha256="a" * 64,
                status=PluginSubmissionStatus.APPROVED,
                submitted_at=utcnow(),
            )
        )
        await db_session.flush()

        worker = SearchIndexRebuildWorker(db_session_factory)
        indexed = await worker.tick()
        assert indexed >= 5

        entries = await repos.search_index.list_all(organization_id)
        content_types = {entry.content_type for entry in entries}
        assert content_types == {"documentation", "tutorial", "sample", "knowledge", "plugin"}

    async def test_org_discovered_purely_from_documentation_is_indexed(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> None:
        """Regression test for the bug where an organization whose only
        activity was publishing documentation (no plugins, no prior
        index entries) was never discovered by the rebuild worker."""
        from app.models.documentation import DocumentationPage
        from app.models.enums import ContentStatus

        repos = build_repositories(db_session)
        await repos.documentation_pages.create(
            DocumentationPage(
                organization_id=organization_id,
                slug="only-doc",
                title="Only Doc",
                content="content",
                status=ContentStatus.PUBLISHED,
                published_at=utcnow(),
            )
        )
        await db_session.flush()

        worker = SearchIndexRebuildWorker(db_session_factory)
        await worker.tick()

        entries = await repos.search_index.list_all(organization_id)
        assert len(entries) == 1
        assert entries[0].content_type == "documentation"


class TestStatisticsRollupWorker:
    async def test_rolls_up_and_is_idempotent(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> None:
        from app.models.developers import DeveloperSession
        from app.models.sdk import SdkDownload

        repos = build_repositories(db_session)
        await repos.sessions.create(
            DeveloperSession(
                organization_id=organization_id,
                user_id="u1",
                issued_at=utcnow(),
                expires_at=hours_ago(-10),
            )
        )
        await repos.sdk_downloads.create(
            SdkDownload(
                organization_id=organization_id,
                user_id="u1",
                language="python",
                version_label="1.0.0",
                # inside the last *completed* hour, not the current
                # in-progress one -- the window is always [start, end)
                # against the top of the current hour.
                downloaded_at=hours_ago(1),
            )
        )
        await db_session.flush()

        worker = StatisticsRollupWorker(db_session_factory, window_hours=3)
        first_rolled = await worker.tick()
        assert first_rolled >= 1
        second_rolled = await worker.tick()
        assert second_rolled >= 1

        stats = await repos.statistics.list_range(organization_id, since=hours_ago(72))
        # idempotent: exactly one row per (organization, window), not one per tick
        assert len(stats) == 1
        assert stats[0].sdk_download_count == 1

    async def test_sdk_download_count_reflects_real_activity(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> None:
        """Regression test for the bug where the worker's own
        ``sdk_download_count`` was always ``0`` regardless of real
        activity, because it misused ``list_for_user`` with an empty
        ``user_id`` and ``limit=0``."""
        from app.models.sdk import SdkDownload

        repos = build_repositories(db_session)
        for index in range(3):
            await repos.sdk_downloads.create(
                SdkDownload(
                    organization_id=organization_id,
                    user_id=f"u{index}",
                    language="python",
                    version_label="1.0.0",
                    downloaded_at=hours_ago(1),
                )
            )
        await db_session.flush()

        worker = StatisticsRollupWorker(db_session_factory, window_hours=3)
        await worker.tick()

        stats = await repos.statistics.list_range(organization_id, since=hours_ago(72))
        assert stats[0].sdk_download_count == 3


class TestPluginSubmissionStalenessSweepWorker:
    async def test_auto_rejects_stale_submissions_and_leaves_fresh_ones(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        notifier: RecordingNotifier,
    ) -> None:
        repos = build_repositories(db_session)
        stale = await repos.plugin_submissions.create(
            PluginSubmission(
                organization_id=organization_id,
                user_id="u1",
                plugin_name="stale-plugin",
                version_label="1.0.0",
                checksum_sha256="a" * 64,
                status=PluginSubmissionStatus.VALIDATING,
                submitted_at=hours_ago(48),
            )
        )
        fresh = await repos.plugin_submissions.create(
            PluginSubmission(
                organization_id=organization_id,
                user_id="u2",
                plugin_name="fresh-plugin",
                version_label="1.0.0",
                checksum_sha256="b" * 64,
                status=PluginSubmissionStatus.VALIDATING,
                submitted_at=utcnow(),
            )
        )
        await db_session.execute(
            update(PluginSubmission)
            .where(PluginSubmission.id == stale.id)
            .values(updated_at=hours_ago(48))
        )
        await db_session.flush()

        worker = PluginSubmissionStalenessSweepWorker(
            db_session_factory, notifier=notifier, max_age_hours=24  # type: ignore[arg-type]
        )
        rejected = await worker.tick()
        assert rejected >= 1

        await db_session.refresh(stale)
        await db_session.refresh(fresh)
        assert stale.status == "rejected"
        assert fresh.status == "validating"

        reviews = await repos.plugin_reviews.list_for_submission(stale.id)
        assert reviews[0].reviewer_id == "system:plugin-submission-staleness-sweep"

    async def test_run_job_entry_point_matches_scheduler_signature(
        self, db_session_factory: async_sessionmaker[AsyncSession], notifier: RecordingNotifier
    ) -> None:
        """``run_job`` -- the entry point the real scheduler calls --
        must work with the single caller-supplied job argument the
        scheduler passes, matching ``shared_core.scheduler``'s own
        ``JobFn`` signature."""
        worker = PluginSubmissionStalenessSweepWorker(
            db_session_factory, notifier=notifier, max_age_hours=24  # type: ignore[arg-type]
        )
        await worker.run_job(object())
