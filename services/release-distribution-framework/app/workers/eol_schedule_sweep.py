"""The end-of-life schedule sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Publishes ``EOLAnnounced`` and notifies EOL Warning **only on the
transition** into a release's own end-of-life warning window --
edge-triggered via the persisted ``deprecation_notice_sent`` flag, the
same shape ``LtsSupportExpirySweepWorker`` uses for its own, distinct
warning window.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.eol.engine import is_eol_approaching
from app.events.domain_events import EOLAnnouncedEvent
from app.services.bundle import build_repositories
from app.services.notifications import ReleaseNotifier
from app.types import EventPublisher

logger = get_logger("app.workers.eol_schedule_sweep")

_SOURCE_SERVICE = "release-distribution-framework"


class EolScheduleSweepWorker:
    """Notifies of releases newly entering their own end-of-life
    warning window."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish: EventPublisher,
        notifier: ReleaseNotifier,
        warning_days: int,
    ) -> None:
        self._session_factory = session_factory
        self._publish = publish
        self._notifier = notifier
        self._warning_days = warning_days

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Notify for every release newly entering its own EOL warning
        window, returning how many were notified."""
        now = datetime.now(UTC)
        notified = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.eol_schedule.list_organization_ids():
                for schedule in await repos.eol_schedule.list_all(organization_id):
                    if schedule.deprecation_notice_sent:
                        continue
                    if not is_eol_approaching(
                        eol_date=schedule.eol_date, now=now, warning_days=self._warning_days
                    ):
                        continue

                    version = await repos.release_versions.require_by_id(
                        schedule.release_version_id
                    )
                    schedule.deprecation_notice_sent = True
                    await repos.eol_schedule.update(schedule)

                    await self._publish(
                        EOLAnnouncedEvent(
                            source_service=_SOURCE_SERVICE,
                            organization_id=organization_id,
                            payload={
                                "eol_schedule_id": str(schedule.id),
                                "release_version_id": str(schedule.release_version_id),
                            },
                        )
                    )
                    await self._notifier.notify_eol_warning(
                        version_label=version.version_label, eol_date=schedule.eol_date.isoformat()
                    )
                    notified += 1
            await session.commit()

        logger.info("eol schedule sweep completed", extra={"extra_fields": {"notified": notified}})
        return notified


__all__ = ["EolScheduleSweepWorker"]
