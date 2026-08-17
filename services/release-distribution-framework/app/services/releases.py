"""Release version lifecycle orchestration.

Publishes ``ReleaseCreated`` on creation and one event per lifecycle
step (``ReleaseValidated``, ``ReleaseSigned``, ``ReleasePublished``,
``ReleaseArchived``) as a release version advances -- see
``app.release.engine`` for the transition table this drives.

``publish()`` walks a release all the way from its current status to
``PUBLISHED`` in one call, since docs/080 names no separate
``POST /releases/validate``/``POST /releases/sign`` routes of their
own; each intermediate step still publishes its own event exactly as
if it had been called individually.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import (
    ReleaseArchivedEvent,
    ReleaseCreatedEvent,
    ReleasePublishedEvent,
    ReleaseSignedEvent,
    ReleaseValidatedEvent,
)
from app.models.enums import ReleaseChannelType, ReleaseStatus
from app.models.releases import ReleaseVersion
from app.release.engine import TransitionResult, next_status_toward, validate_transition
from app.repositories.releases import ReleaseVersionRepository
from app.services.notifications import ReleaseNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "release-distribution-framework"

_EVENT_BY_STATUS = {
    ReleaseStatus.VALIDATED: ReleaseValidatedEvent,
    ReleaseStatus.SIGNED: ReleaseSignedEvent,
    ReleaseStatus.PUBLISHED: ReleasePublishedEvent,
    ReleaseStatus.ARCHIVED: ReleaseArchivedEvent,
}


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class ReleaseVersionService:
    def __init__(
        self,
        repo: ReleaseVersionRepository,
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
        version_label: str,
        release_channel_id: UUID,
        channel_type: ReleaseChannelType,
        is_security_release: bool = False,
    ) -> ReleaseVersion:
        version = await self._repo.create(
            ReleaseVersion(
                organization_id=organization_id,
                version_label=version_label,
                release_channel_id=release_channel_id,
                is_security_release=is_security_release,
            )
        )
        await self._publish(
            ReleaseCreatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"release_version_id": str(version.id), "version_label": version_label},
            )
        )
        if self._notifier is not None:
            await self._notifier.notify_new_release(
                version_label=version_label, channel_type=str(channel_type)
            )
        return version

    async def validate(self, version: ReleaseVersion) -> ReleaseVersion:
        return await self._advance(version, ReleaseStatus.VALIDATED)

    async def sign(self, version: ReleaseVersion) -> ReleaseVersion:
        return await self._advance(version, ReleaseStatus.SIGNED)

    async def publish(
        self, version: ReleaseVersion, *, channel_type: ReleaseChannelType, now: datetime
    ) -> ReleaseVersion:
        version.released_at = now
        version = await self._advance(version, ReleaseStatus.PUBLISHED)
        if self._notifier is not None:
            if channel_type == ReleaseChannelType.LTS:
                await self._notifier.notify_patch_available(version_label=version.version_label)
            if version.is_security_release and channel_type in (
                ReleaseChannelType.STABLE,
                ReleaseChannelType.LTS,
            ):
                await self._notifier.notify_critical_update(version_label=version.version_label)
        return version

    async def archive(self, version: ReleaseVersion) -> ReleaseVersion:
        return await self._advance(version, ReleaseStatus.ARCHIVED)

    async def _advance(
        self, version: ReleaseVersion, target_status: ReleaseStatus
    ) -> ReleaseVersion:
        target_status = ReleaseStatus(target_status)
        while ReleaseStatus(version.status) != target_status:
            next_status = next_status_toward(version.status, target_status)
            if next_status is None:
                result = validate_transition(version.status, target_status)
                raise TransitionRefusedError(result)
            result = validate_transition(version.status, next_status)
            if not result.is_allowed:
                raise TransitionRefusedError(result)
            version.status = next_status
            version = await self._repo.update(version)
            await self._publish_transition_event(version, next_status)
        return version

    async def _publish_transition_event(
        self, version: ReleaseVersion, status: ReleaseStatus
    ) -> None:
        event_class = _EVENT_BY_STATUS.get(status)
        if event_class is None:
            return
        payload: dict[str, object] = {
            "release_version_id": str(version.id),
            "version_label": version.version_label,
        }
        if status == ReleaseStatus.PUBLISHED:
            payload["is_security_release"] = version.is_security_release
        await self._publish(
            event_class(
                source_service=_SOURCE_SERVICE,
                organization_id=version.organization_id,
                payload=payload,
            )
        )


__all__ = ["ReleaseVersionService", "TransitionRefusedError"]
