"""The domain events this service publishes (docs/072 "EVENTS",
integrating Prompt 020).

All nine spec-named events. **Every event is registered with the
shared registry at import time.** ``EventManager.publish`` validates
against :data:`shared_core.events.registry.default_registry` and
refuses anything unregistered as ``AIIOS-EVENT-0002``.

**Fields live in ``payload``**, per :class:`~shared_core.events.base.BaseEvent`
-- not as typed attributes on each subclass, matching the convention
every other AI-IOS service follows.
"""

from __future__ import annotations

from typing import ClassVar

from shared_core.events import default_registry
from shared_core.events.base import DomainEvent


@default_registry.register
class MobileDeviceRegisteredEvent(DomainEvent):
    """A mobile device was registered (directly, or via QR enrollment).

    Expected payload: ``device_id``, ``platform``, ``trust_status``.
    """

    event_name: ClassVar[str] = "MobileDeviceRegistered"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class MobileLoginSucceededEvent(DomainEvent):
    """A mobile session was established.

    Expected payload: ``device_id``, ``user_id``, ``auth_method``,
    ``is_new_device``.
    """

    event_name: ClassVar[str] = "MobileLoginSucceeded"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class MobileLoginFailedEvent(DomainEvent):
    """A mobile login attempt was refused.

    Expected payload: ``device_identifier``, ``reason``.
    """

    event_name: ClassVar[str] = "MobileLoginFailed"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SynchronizationCompletedEvent(DomainEvent):
    """A sync job finished with every queued item applied or resolved.

    Expected payload: ``sync_job_id``, ``device_id``, ``applied_count``.
    """

    event_name: ClassVar[str] = "SynchronizationCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SynchronizationFailedEvent(DomainEvent):
    """A sync job could not complete.

    Expected payload: ``sync_job_id``, ``device_id``, ``reason``.
    """

    event_name: ClassVar[str] = "SynchronizationFailed"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class PushDeliveredEvent(DomainEvent):
    """A push notification was delivered.

    Expected payload: ``notification_id``, ``device_id``.
    """

    event_name: ClassVar[str] = "PushDelivered"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class PushFailedEvent(DomainEvent):
    """A push notification exhausted its own retries without
    delivering.

    Expected payload: ``notification_id``, ``device_id``.
    """

    event_name: ClassVar[str] = "PushFailed"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class AppUpdatedEvent(DomainEvent):
    """A new app version policy was published for a platform.

    Expected payload: ``platform``, ``version``, ``is_forced_upgrade``.
    """

    event_name: ClassVar[str] = "AppUpdated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class OfflineQueueProcessedEvent(DomainEvent):
    """One device's offline action queue finished a processing pass.

    Expected payload: ``device_id``, ``processed_count``.
    """

    event_name: ClassVar[str] = "OfflineQueueProcessed"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "AppUpdatedEvent",
    "MobileDeviceRegisteredEvent",
    "MobileLoginFailedEvent",
    "MobileLoginSucceededEvent",
    "OfflineQueueProcessedEvent",
    "PushDeliveredEvent",
    "PushFailedEvent",
    "SynchronizationCompletedEvent",
    "SynchronizationFailedEvent",
]
