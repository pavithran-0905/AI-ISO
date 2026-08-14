"""Platform and tenant announcements."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import AnnouncementScope
from app.models.maintenance import PlatformAnnouncement
from app.repositories.maintenance import PlatformAnnouncementRepository


class AnnouncementService:
    def __init__(self, repo: PlatformAnnouncementRepository) -> None:
        self._repo = repo

    async def publish_announcement(
        self,
        organization_id: UUID,
        *,
        title: str,
        body: str,
        scope: AnnouncementScope,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
    ) -> PlatformAnnouncement:
        return await self._repo.create(
            PlatformAnnouncement(
                organization_id=organization_id,
                title=title,
                body=body,
                scope=scope,
                starts_at=starts_at,
                ends_at=ends_at,
            )
        )

    async def retract(self, announcement: PlatformAnnouncement) -> PlatformAnnouncement:
        announcement.is_enabled = False
        return await self._repo.update(announcement)


__all__ = ["AnnouncementService"]
