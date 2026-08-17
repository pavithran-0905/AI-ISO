"""LTS lifecycle tracking and end-of-life scheduling.

``LtsVersionService.create()`` is where a release version is first
designated as a new LTS line -- publishing ``LTSReleased`` and
notifying LTS Release right there, since that is the one moment this
fact becomes true. ``EolScheduleService.create()`` only records a
schedule; ``EOLAnnounced`` and EOL Warning are the
``EolScheduleSweepWorker``'s own job, fired on the edge-triggered
transition into the warning window, not at scheduling time.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import LTSReleasedEvent
from app.models.lifecycle import EolSchedule, LtsVersion
from app.repositories.lifecycle import EolScheduleRepository, LtsVersionRepository
from app.services.notifications import ReleaseNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "release-distribution-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class LtsVersionService:
    def __init__(
        self,
        repo: LtsVersionRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: ReleaseNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def create(
        self,
        organization_id: UUID,
        *,
        release_version_id: UUID,
        support_ends_at: datetime,
        version_label: str = "",
    ) -> LtsVersion:
        lts_version = await self._repo.create(
            LtsVersion(
                organization_id=organization_id,
                release_version_id=release_version_id,
                support_ends_at=support_ends_at,
            )
        )
        await self._publish(
            LTSReleasedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "lts_version_id": str(lts_version.id),
                    "release_version_id": str(release_version_id),
                },
            )
        )
        if self._notifier is not None:
            await self._notifier.notify_lts_release(
                version_label=version_label, support_ends_at=support_ends_at.isoformat()
            )
        return lts_version


class EolScheduleService:
    def __init__(self, repo: EolScheduleRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        release_version_id: UUID,
        eol_date: datetime,
        migration_recommendation: str = "",
    ) -> EolSchedule:
        return await self._repo.create(
            EolSchedule(
                organization_id=organization_id,
                release_version_id=release_version_id,
                eol_date=eol_date,
                migration_recommendation=migration_recommendation,
            )
        )


__all__ = ["EolScheduleService", "LtsVersionService"]
