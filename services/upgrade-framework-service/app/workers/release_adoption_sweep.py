"""The release adoption sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Notifies Upgrade Available when a release channel's own latest known
version is newer than its current one. **Edge-triggered via the
version's own ``released_at`` timestamp**, not a separate "already
notified" table -- docs/076's own DATABASE TABLES section has no such
table, so, mirroring
``services/installation-deployment-service``'s own upgrade
availability sweep (Prompt 075), this worker only notifies while the
newer version's ``released_at`` still falls within its own lookback
window (twice its own sweep interval), rather than on every tick for
as long as the channel stays on the older version.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.compatibility.engine import parse_semantic_version
from app.services.bundle import build_repositories
from app.services.notifications import UpgradeNotifier

logger = get_logger("app.workers.release_adoption_sweep")


class ReleaseAdoptionSweepWorker:
    """Notifies of a newly available release version, per channel."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: UpgradeNotifier,
        lookback_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._lookback_seconds = lookback_seconds

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Notify for every channel with a newly available release,
        returning how many were notified."""
        now = datetime.now(UTC)
        lookback_cutoff = now - timedelta(seconds=self._lookback_seconds)
        notified = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.versions.list_organization_ids():
                for channel in await repos.channels.list_all(organization_id):
                    current = await repos.versions.find_current(
                        organization_id, release_channel_id=channel.id
                    )
                    latest_rows = await repos.versions.list_latest(
                        organization_id, release_channel_id=channel.id, limit=1
                    )
                    if not latest_rows:
                        continue
                    latest = latest_rows[0]

                    if latest.released_at < lookback_cutoff:
                        continue
                    if current is not None and parse_semantic_version(
                        latest.version_label
                    ) <= parse_semantic_version(current.version_label):
                        continue

                    await self._notifier.notify_upgrade_available(version=latest.version_label)
                    notified += 1

        logger.info(
            "release adoption sweep completed", extra={"extra_fields": {"notified": notified}}
        )
        return notified


__all__ = ["ReleaseAdoptionSweepWorker"]
