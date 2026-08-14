"""Push token registration and push notification delivery.

Delivery itself is exclusively the
:class:`~app.workers.push_delivery_retry_sweep.PushDeliveryRetrySweepWorker`'s
job -- ``attempt_delivery`` is called from there, never from a route,
matching the same "enqueue synchronously, process in the background"
split as synchronization.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import PushDeliveredEvent, PushFailedEvent
from app.models.enums import NotificationDeliveryStatus, PushPlatform, PushTokenStatus
from app.models.notifications import MobileNotification, MobilePushToken
from app.push.engine import is_retry_eligible, validate_transition
from app.repositories.notifications import MobileNotificationRepository, MobilePushTokenRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "mobile-api-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class PushService:
    def __init__(
        self,
        tokens_repo: MobilePushTokenRepository,
        notifications_repo: MobileNotificationRepository,
        *,
        publish: EventPublisher = _noop_publisher,
    ) -> None:
        self._tokens = tokens_repo
        self._notifications = notifications_repo
        self._publish = publish

    async def register_token(
        self,
        organization_id: UUID,
        *,
        device_id: UUID,
        platform: PushPlatform,
        token_value: str,
        now: datetime,
    ) -> MobilePushToken:
        existing = await self._tokens.find_for_device(
            organization_id, device_id=device_id, platform=platform
        )
        if existing is not None:
            existing.token_value = token_value
            existing.status = PushTokenStatus.ACTIVE
            existing.registered_at = now
            return await self._tokens.update(existing)
        return await self._tokens.create(
            MobilePushToken(
                organization_id=organization_id,
                device_id=device_id,
                platform=platform,
                token_value=token_value,
                registered_at=now,
            )
        )

    async def enqueue(
        self,
        organization_id: UUID,
        *,
        device_id: UUID,
        title: str,
        body: str,
        category: str = "general",
    ) -> MobileNotification:
        return await self._notifications.create(
            MobileNotification(
                organization_id=organization_id,
                device_id=device_id,
                title=title,
                body=body,
                category=category,
            )
        )

    async def attempt_delivery(
        self,
        notification: MobileNotification,
        device_identifier: str,
        *,
        token_usable: bool,
        max_retry_count: int,
        now: datetime,
    ) -> MobileNotification:
        """Attempt one delivery of *notification*.

        A successful attempt transitions ``PENDING -> DELIVERED``. A
        failed attempt with retries remaining only increments
        ``retry_count``, leaving the notification ``PENDING`` for the
        next sweep; a failed attempt with no retries left transitions
        ``PENDING -> FAILED``.
        """
        if token_usable:
            transition = validate_transition(
                notification.status, NotificationDeliveryStatus.DELIVERED
            )
            if transition.is_allowed:
                notification.status = NotificationDeliveryStatus.DELIVERED
                notification.delivered_at = now
                notification = await self._notifications.update(notification)
                await self._publish(
                    PushDeliveredEvent(
                        source_service=_SOURCE_SERVICE,
                        organization_id=notification.organization_id,
                        payload={
                            "notification_id": str(notification.id),
                            "device_id": str(notification.device_id),
                        },
                    )
                )
            return notification

        notification.retry_count += 1
        if is_retry_eligible(retry_count=notification.retry_count, max_retry_count=max_retry_count):
            return await self._notifications.update(notification)

        transition = validate_transition(notification.status, NotificationDeliveryStatus.FAILED)
        if transition.is_allowed:
            notification.status = NotificationDeliveryStatus.FAILED
            notification = await self._notifications.update(notification)
            await self._publish(
                PushFailedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=notification.organization_id,
                    payload={
                        "notification_id": str(notification.id),
                        "device_id": str(notification.device_id),
                        "device_identifier": device_identifier,
                    },
                )
            )
        return notification

    async def mark_read(
        self, notification: MobileNotification, *, now: datetime
    ) -> MobileNotification:
        notification.status = NotificationDeliveryStatus.READ
        notification.read_at = now
        return await self._notifications.update(notification)


__all__ = ["PushService"]
