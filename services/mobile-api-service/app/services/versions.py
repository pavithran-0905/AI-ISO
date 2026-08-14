"""App version policy publication.

There is no ``POST`` route for this -- publishing a new version policy
is an administrative operation performed through internal tooling (or,
in tests, direct service calls), matching how every other AI-IOS
service treats its own worker-consumed policy tables (compare
``services/administration-portal-service``'s diagnostics: written by
services and workers, read-only over HTTP).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import AppUpdatedEvent
from app.models.configuration import MobileAppVersion
from app.models.enums import MobilePlatform, ReleaseChannel
from app.repositories.configuration import MobileAppVersionRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "mobile-api-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class AppVersionService:
    def __init__(
        self, repo: MobileAppVersionRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def publish_version(
        self,
        organization_id: UUID,
        *,
        platform: MobilePlatform,
        version: str,
        minimum_version: str,
        recommended_version: str,
        is_forced_upgrade: bool = False,
        release_channel: ReleaseChannel = ReleaseChannel.STABLE,
        release_notes: str = "",
        now: datetime,
    ) -> MobileAppVersion:
        app_version = await self._repo.create(
            MobileAppVersion(
                organization_id=organization_id,
                platform=platform,
                version_label=version,
                release_channel=release_channel,
                minimum_version_label=minimum_version,
                recommended_version_label=recommended_version,
                is_forced_upgrade=is_forced_upgrade,
                release_notes=release_notes,
                released_at=now,
            )
        )
        await self._publish(
            AppUpdatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "platform": platform.value,
                    "version": version,
                    "is_forced_upgrade": is_forced_upgrade,
                },
            )
        )
        return app_version


__all__ = ["AppVersionService"]
