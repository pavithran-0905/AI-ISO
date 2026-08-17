"""Release channels and the versions published to them.

Publishes ``ReleasePublished`` on every new version -- the one
fan-notified event in this build (see ``app.services.notifications``).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import ReleasePublishedEvent
from app.models.enums import ReleaseChannelType
from app.models.releases import ReleaseChannel, ReleaseVersion
from app.repositories.releases import ReleaseChannelRepository, ReleaseVersionRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "upgrade-framework-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class ReleaseChannelService:
    def __init__(self, repo: ReleaseChannelRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        name: str,
        channel_type: ReleaseChannelType,
        description: str = "",
    ) -> ReleaseChannel:
        return await self._repo.create(
            ReleaseChannel(
                organization_id=organization_id,
                name=name,
                channel_type=channel_type,
                description=description,
            )
        )


class ReleaseVersionService:
    def __init__(
        self, repo: ReleaseVersionRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def publish(
        self,
        organization_id: UUID,
        *,
        release_channel_id: UUID,
        version_label: str,
        released_at: datetime,
        checksum_sha256: str = "",
        artifact_ref: str = "",
    ) -> ReleaseVersion:
        version = await self._repo.create(
            ReleaseVersion(
                organization_id=organization_id,
                release_channel_id=release_channel_id,
                version_label=version_label,
                released_at=released_at,
                checksum_sha256=checksum_sha256,
                artifact_ref=artifact_ref,
            )
        )
        await self._publish(
            ReleasePublishedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "release_channel_id": str(release_channel_id),
                    "version_label": version_label,
                },
            )
        )
        return version

    async def mark_current(self, version: ReleaseVersion) -> ReleaseVersion:
        current = await self._repo.find_current(
            version.organization_id, release_channel_id=version.release_channel_id
        )
        if current is not None and current.id != version.id:
            current.is_current = False
            await self._repo.update(current)
        version.is_current = True
        return await self._repo.update(version)


__all__ = ["ReleaseChannelService", "ReleaseVersionService"]
