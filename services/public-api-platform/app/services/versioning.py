"""API version lifecycle.

Publishes ``APIVersionReleased`` on ``RELEASED``, carrying the owning
product's own name so :class:`~app.services.notifications.NotifyingPublisher`
can fan out to the API Version Released notification without a second
lookup.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import APIVersionReleasedEvent
from app.models.documents import ApiVersion
from app.models.enums import ApiVersionStatus, DeveloperAuditAction
from app.models.products import ApiProduct
from app.repositories.documents import ApiVersionRepository
from app.services.audit import AuditService
from app.types import EventPublisher
from app.versioning.engine import TransitionResult, validate_transition

_SOURCE_SERVICE = "public-api-platform"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class ApiVersionService:
    def __init__(
        self,
        repo: ApiVersionRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit

    async def create_draft(
        self, organization_id: UUID, *, api_product_id: UUID, version: str
    ) -> ApiVersion:
        return await self._repo.create(
            ApiVersion(
                organization_id=organization_id,
                api_product_id=api_product_id,
                version_label=version,
            )
        )

    async def transition(
        self,
        version: ApiVersion,
        *,
        target: ApiVersionStatus,
        product: ApiProduct,
        now: datetime,
        actor_id: str | None = None,
    ) -> ApiVersion:
        """Move *version* to *target*, raising
        :class:`TransitionRefusedError` if the transition is not
        allowed."""
        result = validate_transition(version.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        version.status = target
        if target == ApiVersionStatus.RELEASED:
            version.released_at = now
        await self._repo.update(version)

        if self._audit is not None:
            await self._audit.record(
                organization_id=version.organization_id,
                action=DeveloperAuditAction.VERSION_RELEASE,
                entity_type="api_version",
                entity_id=version.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"API version {version.version_label!r} moved to {target.value}.",
            )
        if target == ApiVersionStatus.RELEASED:
            await self._publish(
                APIVersionReleasedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=version.organization_id,
                    payload={
                        "api_version_id": str(version.id),
                        "api_product_id": str(version.api_product_id),
                        "product_name": product.name,
                        "version": version.version_label,
                    },
                )
            )
        return version


__all__ = ["ApiVersionService", "TransitionRefusedError"]
