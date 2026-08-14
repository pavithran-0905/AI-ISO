"""SDK release lifecycle.

Wires ``app.sdk.engine``'s pure transition table onto the repository
that persists a release's ``status``, publishing ``SDKReleased`` on
``PUBLISHED`` -- with ``breaking_changes`` carried in the event payload
so :class:`~app.services.notifications.NotifyingPublisher` can fan out
to the Breaking API Changes notification without a second event.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import SdkReleasedEvent
from app.models.enums import AuditAction, ReleaseStatus, SdkLanguage
from app.models.sdk import SdkRelease
from app.repositories.sdk import SdkReleaseRepository
from app.sdk.engine import TransitionResult, validate_transition
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "sdk-cli-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class SdkReleaseService:
    def __init__(
        self,
        repo: SdkReleaseRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit

    async def create_draft(
        self,
        organization_id: UUID,
        *,
        sdk_version_id: UUID,
        release_notes: str,
        breaking_changes: bool = False,
    ) -> SdkRelease:
        return await self._repo.create(
            SdkRelease(
                organization_id=organization_id,
                sdk_version_id=sdk_version_id,
                release_notes=release_notes,
                breaking_changes=breaking_changes,
            )
        )

    async def transition(
        self,
        release: SdkRelease,
        *,
        target: ReleaseStatus,
        language: SdkLanguage,
        version: str,
        actor_id: str | None,
        now: datetime,
    ) -> SdkRelease:
        """Move *release* to *target*, raising
        :class:`TransitionRefusedError` if the transition is not
        allowed."""
        result = validate_transition(release.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        release.status = target
        if target == ReleaseStatus.PUBLISHED:
            release.published_at = now
        await self._repo.update(release)

        if self._audit is not None:
            await self._audit.record(
                organization_id=release.organization_id,
                action=AuditAction.SDK_RELEASED,
                entity_type="sdk_release",
                entity_id=release.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"SDK release {release.id!s} moved to {target.value}.",
            )

        if target == ReleaseStatus.PUBLISHED:
            await self._publish(
                SdkReleasedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=release.organization_id,
                    payload={
                        "sdk_release_id": str(release.id),
                        "language": language.value,
                        "version": version,
                        "breaking_changes": release.breaking_changes,
                    },
                )
            )
        return release


__all__ = ["SdkReleaseService", "TransitionRefusedError"]
