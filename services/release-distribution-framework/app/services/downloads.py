"""Download event recording.

Publishes ``ReleaseDownloaded`` on every recorded download -- a
high-frequency event never fanned into a notification (docs/080's own
NOTIFICATIONS list has no "Download" kind), only ever forwarded.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import ReleaseDownloadedEvent
from app.models.downloads import DownloadStatistic
from app.repositories.downloads import DownloadStatisticRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "release-distribution-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class DownloadStatisticService:
    def __init__(
        self, repo: DownloadStatisticRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def record(
        self,
        organization_id: UUID,
        *,
        release_artifact_id: UUID,
        region_code: str = "",
        bytes_transferred: int = 0,
        downloaded_at: datetime,
    ) -> DownloadStatistic:
        download = await self._repo.create(
            DownloadStatistic(
                organization_id=organization_id,
                release_artifact_id=release_artifact_id,
                region_code=region_code,
                bytes_transferred=bytes_transferred,
                downloaded_at=downloaded_at,
            )
        )
        await self._publish(
            ReleaseDownloadedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"release_artifact_id": str(release_artifact_id)},
            )
        )
        return download


__all__ = ["DownloadStatisticService"]
