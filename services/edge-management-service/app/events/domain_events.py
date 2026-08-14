"""The domain events this service publishes (docs/067 "EVENTS",
integrating Prompt 020).

All nine spec-named events. **Every event is registered with the shared
registry at import time.** ``EventManager.publish`` validates against
:data:`shared_core.events.registry.default_registry` and refuses
anything unregistered as ``AIIOS-EVENT-0002``.

**Fields live in ``payload``**, per :class:`~shared_core.events.base.BaseEvent`
-- not as typed attributes on each subclass, matching the convention
every other AI-IOS service follows.
"""

from __future__ import annotations

from typing import ClassVar

from shared_core.events import default_registry
from shared_core.events.base import DomainEvent


@default_registry.register
class EdgeSiteRegisteredEvent(DomainEvent):
    """A new edge site was registered.

    Expected payload: ``site_id``, ``name``, ``business_unit``.
    """

    event_name: ClassVar[str] = "EdgeSiteRegistered"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class EdgeDeviceRegisteredEvent(DomainEvent):
    """A new edge device was registered.

    Expected payload: ``device_id``, ``site_id``, ``device_type``.
    """

    event_name: ClassVar[str] = "EdgeDeviceRegistered"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SynchronizationCompletedEvent(DomainEvent):
    """A device synchronization finished successfully.

    Expected payload: ``device_id``, ``sync_id``, ``sync_kind``,
    ``duration_ms``.
    """

    event_name: ClassVar[str] = "SynchronizationCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SynchronizationFailedEvent(DomainEvent):
    """A device synchronization failed.

    Expected payload: ``device_id``, ``sync_id``, ``error_message``.
    """

    event_name: ClassVar[str] = "SynchronizationFailed"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class OTAStartedEvent(DomainEvent):
    """An over-the-air update began applying to a device.

    Expected payload: ``device_id``, ``update_id``, ``from_version``,
    ``to_version``.
    """

    event_name: ClassVar[str] = "OTAStarted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class OTACompletedEvent(DomainEvent):
    """An over-the-air update finished, successfully or not.

    Expected payload: ``device_id``, ``update_id``, ``status``.
    """

    event_name: ClassVar[str] = "OTACompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class DeviceOfflineEvent(DomainEvent):
    """A device that was online stopped reporting in.

    Expected payload: ``device_id``, ``last_seen_at``.
    """

    event_name: ClassVar[str] = "DeviceOffline"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class DeviceOnlineEvent(DomainEvent):
    """A device that was offline resumed reporting in.

    Expected payload: ``device_id``, ``last_seen_at``.
    """

    event_name: ClassVar[str] = "DeviceOnline"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class AIModelDeployedEvent(DomainEvent):
    """An AI model was deployed (or promoted) to a device.

    Expected payload: ``device_id``, ``model_id``, ``name``, ``version``,
    ``status``.
    """

    event_name: ClassVar[str] = "AIModelDeployed"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "AIModelDeployedEvent",
    "DeviceOfflineEvent",
    "DeviceOnlineEvent",
    "EdgeDeviceRegisteredEvent",
    "EdgeSiteRegisteredEvent",
    "OTACompletedEvent",
    "OTAStartedEvent",
    "SynchronizationCompletedEvent",
    "SynchronizationFailedEvent",
]
