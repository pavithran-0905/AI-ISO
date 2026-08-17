"""Release promotion orchestration.

``promote()`` is the single-hop path ``POST /releases/promote`` uses:
create a promotion record and immediately complete (or reject) it
based on ``app.promotion.engine.is_valid_promotion``, since docs/080
names no separate approval-workflow route of its own. ``create()``
remains available on its own for internal/test use -- a promotion
left ``PENDING`` is exactly what ``PromotionApprovalTimeoutSweepWorker``
looks for.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import ReleasePromotedEvent
from app.models.enums import PromotionStatus, ReleaseChannelType
from app.models.promotions import ReleasePromotion
from app.promotion.engine import is_valid_promotion
from app.repositories.promotions import ReleasePromotionRepository
from app.services.notifications import ReleaseNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "release-distribution-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class ReleasePromotionService:
    def __init__(
        self,
        repo: ReleasePromotionRepository,
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
        from_channel_type: ReleaseChannelType,
        to_channel_type: ReleaseChannelType,
    ) -> ReleasePromotion:
        return await self._repo.create(
            ReleasePromotion(
                organization_id=organization_id,
                release_version_id=release_version_id,
                from_channel_type=from_channel_type,
                to_channel_type=to_channel_type,
            )
        )

    async def promote(
        self,
        organization_id: UUID,
        *,
        release_version_id: UUID,
        version_label: str,
        from_channel_type: ReleaseChannelType,
        to_channel_type: ReleaseChannelType,
        approved_by: str,
        now: datetime,
    ) -> ReleasePromotion:
        """Create and immediately execute (or reject) a promotion."""
        promotion = await self.create(
            organization_id,
            release_version_id=release_version_id,
            from_channel_type=from_channel_type,
            to_channel_type=to_channel_type,
        )
        if not is_valid_promotion(from_channel=from_channel_type, to_channel=to_channel_type):
            promotion.status = PromotionStatus.REJECTED
            return await self._repo.update(promotion)

        promotion.status = PromotionStatus.COMPLETED
        promotion.approved_by = approved_by
        promotion.promoted_at = now
        promotion = await self._repo.update(promotion)
        await self._publish(
            ReleasePromotedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "release_promotion_id": str(promotion.id),
                    "from_channel": str(from_channel_type),
                    "to_channel": str(to_channel_type),
                },
            )
        )
        if self._notifier is not None:
            await self._notifier.notify_promotion_complete(
                version_label=version_label, to_channel=str(to_channel_type)
            )
        return promotion

    async def reject(self, promotion: ReleasePromotion) -> ReleasePromotion:
        promotion.status = PromotionStatus.REJECTED
        return await self._repo.update(promotion)


__all__ = ["ReleasePromotionService"]
