"""Notifications (docs/067 "NOTIFY", integrating Prompt 025).

**Two of the eight notification kinds have a domain event behind them**
(Device Offline, OTA Failed via ``OTACompleted`` with a failed status)
and are dispatched by :class:`NotifyingPublisher`, an ``EventPublisher``
that wraps the real one, forwards every event unchanged, and
opportunistically notifies for the subset that warrant it -- exactly the
pattern ``services/multi-cluster-management-service/app/services/notifications.py``
established.

**The other six do not** (Synchronization Failed as a standalone alert
distinct from its event, Firmware Update Available, Security Issue, Low
Storage, Temperature Alert, Certificate Expiring): none maps to a
lifecycle-boundary domain event this service publishes, since firmware
catalog freshness, storage/temperature thresholds, and credential expiry
are observed continuously by a worker rather than announced as discrete
facts. Those are called directly by the workers that observe them.
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_DEVICE_OFFLINE = "edge_management.device_offline"
TOPIC_SYNCHRONIZATION_FAILED = "edge_management.synchronization_failed"
TOPIC_OTA_FAILED = "edge_management.ota_failed"
TOPIC_FIRMWARE_UPDATE_AVAILABLE = "edge_management.firmware_update_available"
TOPIC_SECURITY_ISSUE = "edge_management.security_issue"
TOPIC_LOW_STORAGE = "edge_management.low_storage"
TOPIC_TEMPERATURE_ALERT = "edge_management.temperature_alert"
TOPIC_CERTIFICATE_EXPIRING = "edge_management.certificate_expiring"


class EdgeNotifier:
    """Sends the eight notification kinds docs/067 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_device_offline(self, *, device_id: str, device_name: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_DEVICE_OFFLINE,
            notification_type=NotificationType.MONITORING,
            body=f"Device {device_name} ({device_id}) has stopped reporting and is offline.",
            priority=Priority.CRITICAL,
            variables={"device_id": device_id, "device_name": device_name},
        )

    async def notify_synchronization_failed(
        self, *, device_id: str, sync_id: str, error_message: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_SYNCHRONIZATION_FAILED,
            notification_type=NotificationType.MONITORING,
            body=f"Synchronization {sync_id} for device {device_id} failed: {error_message}",
            priority=Priority.HIGH,
            variables={"device_id": device_id, "sync_id": sync_id},
        )

    async def notify_ota_failed(self, *, device_id: str, update_id: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_OTA_FAILED,
            notification_type=NotificationType.MONITORING,
            body=f"OTA update {update_id} for device {device_id} failed.",
            priority=Priority.CRITICAL,
            variables={"device_id": device_id, "update_id": update_id},
        )

    async def notify_firmware_update_available(
        self, *, device_id: str, current_version: str, available_version: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_FIRMWARE_UPDATE_AVAILABLE,
            notification_type=NotificationType.INFORMATION,
            body=(f"Device {device_id} is on {current_version}; {available_version} is available."),
            priority=Priority.NORMAL,
            variables={"device_id": device_id, "available_version": available_version},
        )

    async def notify_security_issue(self, *, device_id: str, detail: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_SECURITY_ISSUE,
            notification_type=NotificationType.WARNING,
            body=f"Security issue detected on device {device_id}: {detail}",
            priority=Priority.CRITICAL,
            variables={"device_id": device_id},
        )

    async def notify_low_storage(self, *, device_id: str, free_fraction: float) -> None:
        await self._manager.broadcast(
            topic=TOPIC_LOW_STORAGE,
            notification_type=NotificationType.WARNING,
            body=f"Device {device_id} has only {free_fraction:.0%} storage free.",
            priority=Priority.HIGH,
            variables={"device_id": device_id},
        )

    async def notify_temperature_alert(self, *, device_id: str, reading_celsius: float) -> None:
        await self._manager.broadcast(
            topic=TOPIC_TEMPERATURE_ALERT,
            notification_type=NotificationType.WARNING,
            body=f"Device {device_id} is reporting {reading_celsius:.1f}C.",
            priority=Priority.HIGH,
            variables={"device_id": device_id},
        )

    async def notify_certificate_expiring(self, *, device_id: str, expires_at: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CERTIFICATE_EXPIRING,
            notification_type=NotificationType.WARNING,
            body=f"Device {device_id}'s credential expires at {expires_at}.",
            priority=Priority.HIGH,
            variables={"device_id": device_id, "expires_at": expires_at},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination exactly as if this wrapper were
    not there.
    """

    def __init__(self, inner: EventPublisher, notifier: EdgeNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "DeviceOffline":
            await self._notifier.notify_device_offline(
                device_id=str(payload.get("device_id", "")),
                device_name=str(payload.get("device_id", "")),
            )
        elif event.event_name == "OTACompleted" and str(payload.get("status", "")) == "failed":
            await self._notifier.notify_ota_failed(
                device_id=str(payload.get("device_id", "")),
                update_id=str(payload.get("update_id", "")),
            )


__all__ = ["EdgeNotifier", "NotifyingPublisher"]
