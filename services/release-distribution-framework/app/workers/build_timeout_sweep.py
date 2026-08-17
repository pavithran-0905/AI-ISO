"""The release build timeout sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Fails every release build that has been ``RUNNING`` past its own
configured maximum age -- a build that never reports back is not still
"in progress" forever.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import BuildStatus
from app.release_build.engine import is_job_stuck
from app.services.builds import ReleaseBuildService
from app.services.bundle import build_repositories
from app.services.notifications import ReleaseNotifier

logger = get_logger("app.workers.build_timeout_sweep")


class ReleaseBuildTimeoutSweepWorker:
    """Fails release builds stuck too long in ``RUNNING``."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: ReleaseNotifier,
        max_age_hours: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._max_age_hours = max_age_hours

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's running release builds, returning
        how many were failed."""
        now = datetime.now(UTC)
        failed = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = ReleaseBuildService(repos.release_builds, notifier=self._notifier)

            for organization_id in await repos.release_builds.list_organization_ids():
                for build in await repos.release_builds.list_running(organization_id):
                    if is_job_stuck(
                        build.status,
                        started_at=build.started_at,
                        now=now,
                        max_age_hours=self._max_age_hours,
                    ):
                        version = await repos.release_versions.require_by_id(
                            build.release_version_id
                        )
                        await service.complete(
                            build,
                            status=BuildStatus.FAILED,
                            now=now,
                            error_message="Release build timed out.",
                            version_label=version.version_label,
                        )
                        failed += 1
            await session.commit()

        logger.info(
            "release build timeout sweep completed", extra={"extra_fields": {"failed": failed}}
        )
        return failed


__all__ = ["ReleaseBuildTimeoutSweepWorker"]
