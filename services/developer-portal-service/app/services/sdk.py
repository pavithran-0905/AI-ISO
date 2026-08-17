"""Portal-initiated SDK download recording.

Publishes ``SDKDownloaded`` on every recorded download, and notifies
SDK Released directly the first time this portal ever sees a
particular language/version pair downloaded -- a real deployment would
instead learn about a release the moment ``services/sdk-cli-service``
(Prompt 071) published one, but since this service does not consume
another service's events, the portal's own first sighting of a new
version through its download-recording path is the honest signal
available to it.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import SDKDownloadedEvent
from app.models.sdk import SdkDownload
from app.repositories.sdk import SdkDownloadRepository
from app.services.notifications import PortalNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "developer-portal-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class SdkDownloadService:
    def __init__(
        self,
        repo: SdkDownloadRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: PortalNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def record(
        self, organization_id: UUID, *, user_id: str, language: str, version: str, now: datetime
    ) -> SdkDownload:
        is_first_sighting = not await self._repo.exists_for_version(
            organization_id, language=language, version_label=version
        )
        download = await self._repo.create(
            SdkDownload(
                organization_id=organization_id,
                user_id=user_id,
                language=language,
                version_label=version,
                downloaded_at=now,
            )
        )
        await self._publish(
            SDKDownloadedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"user_id": user_id, "language": language, "version": version},
            )
        )
        if is_first_sighting and self._notifier is not None:
            await self._notifier.notify_sdk_released(language=language, version=version)
        return download


__all__ = ["SdkDownloadService"]
