"""The plugin submission staleness sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Auto-rejects every plugin submission that has sat in ``VALIDATING``
past its own configured maximum age -- a validation step that never
completes should not leave a developer's own Publisher Dashboard
showing "in progress" forever.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import PluginReviewDecision
from app.services.bundle import build_repositories
from app.services.notifications import PortalNotifier
from app.services.plugins import PluginSubmissionService

logger = get_logger("app.workers.plugin_submission_staleness_sweep")

_STALENESS_REVIEWER_ID = "system:plugin-submission-staleness-sweep"


class PluginSubmissionStalenessSweepWorker:
    """Auto-rejects plugin submissions stuck too long in validation."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: PortalNotifier,
        max_age_hours: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._max_age_hours = max_age_hours

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's stale plugin submissions,
        returning how many were auto-rejected."""
        now = datetime.now(UTC)
        before = now - timedelta(hours=self._max_age_hours)
        rejected = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = PluginSubmissionService(
                repos.plugin_submissions, repos.plugin_reviews, notifier=self._notifier
            )

            for organization_id in await repos.plugin_submissions.list_organization_ids():
                for submission in await repos.plugin_submissions.list_stale_validating(
                    organization_id, before=before
                ):
                    await service.review(
                        submission,
                        reviewer_id=_STALENESS_REVIEWER_ID,
                        decision=PluginReviewDecision.REJECTED,
                        comments="Validation timed out.",
                        now=now,
                    )
                    rejected += 1
            await session.commit()

        logger.info(
            "plugin submission staleness sweep completed",
            extra={"extra_fields": {"rejected": rejected}},
        )
        return rejected


__all__ = ["PluginSubmissionStalenessSweepWorker"]
