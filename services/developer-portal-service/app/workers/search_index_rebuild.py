"""The search index rebuild worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Re-indexes every published documentation page, tutorial, sample
project, and knowledge article, plus every approved plugin submission,
into ``search_index`` -- the maintenance job behind docs/074's own
"Search Caching" performance requirement and the thing that keeps
``POST /portal/search`` and the AI documentation assistant answering
against current content rather than whatever was true the last time
something was published.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import (
    KnowledgeArticleCategory,
    PluginSubmissionStatus,
    SampleProjectCategory,
    SearchContentType,
    TutorialDifficulty,
)
from app.services.bundle import build_repositories
from app.services.knowledge import SearchIndexService

logger = get_logger("app.workers.search_index_rebuild")

_MAX_ROWS_PER_ORG = 5_000


class SearchIndexRebuildWorker:
    """Rebuilds every organization's search index from its own current
    published content."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Re-index every organization's own published content,
        returning how many entries were indexed."""
        now = datetime.now(UTC)
        indexed = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            index_service = SearchIndexService(repos.search_index)

            known_organization_ids: set[UUID] = set()
            known_organization_ids.update(await repos.documentation_pages.list_organization_ids())
            known_organization_ids.update(await repos.tutorials.list_organization_ids())
            known_organization_ids.update(await repos.sample_projects.list_organization_ids())
            known_organization_ids.update(await repos.knowledge_articles.list_organization_ids())
            known_organization_ids.update(await repos.plugin_submissions.list_organization_ids())

            for organization_id in known_organization_ids:
                for page in await repos.documentation_pages.list_published(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                ):
                    await index_service.index(
                        organization_id,
                        content_type=SearchContentType.DOCUMENTATION,
                        content_id=page.id,
                        title=page.title,
                        summary=page.content[:500],
                        keywords=[page.category],
                        now=now,
                    )
                    indexed += 1

                for tutorial in await repos.tutorials.list_published(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                ):
                    await index_service.index(
                        organization_id,
                        content_type=SearchContentType.TUTORIAL,
                        content_id=tutorial.id,
                        title=tutorial.title,
                        summary=tutorial.description[:500],
                        keywords=[TutorialDifficulty(tutorial.difficulty).value],
                        now=now,
                    )
                    indexed += 1

                for sample in await repos.sample_projects.list_published(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                ):
                    await index_service.index(
                        organization_id,
                        content_type=SearchContentType.SAMPLE,
                        content_id=sample.id,
                        title=sample.title,
                        summary=sample.description[:500],
                        keywords=[SampleProjectCategory(sample.category).value],
                        now=now,
                    )
                    indexed += 1

                for article in await repos.knowledge_articles.list_published(
                    organization_id, limit=_MAX_ROWS_PER_ORG
                ):
                    await index_service.index(
                        organization_id,
                        content_type=SearchContentType.KNOWLEDGE,
                        content_id=article.id,
                        title=article.title,
                        summary=article.content[:500],
                        keywords=[KnowledgeArticleCategory(article.category).value],
                        now=now,
                    )
                    indexed += 1

                for submission in await repos.plugin_submissions.list_recent(
                    organization_id, status=PluginSubmissionStatus.APPROVED, limit=_MAX_ROWS_PER_ORG
                ):
                    await index_service.index(
                        organization_id,
                        content_type=SearchContentType.PLUGIN,
                        content_id=submission.id,
                        title=submission.plugin_name,
                        summary="",
                        keywords=[submission.version_label],
                        now=now,
                    )
                    indexed += 1

            await session.commit()

        logger.info("search index rebuild completed", extra={"extra_fields": {"indexed": indexed}})
        return indexed


__all__ = ["SearchIndexRebuildWorker"]
