from app.events.domain_events import (
    AIModelDeployedEvent,
    DeviceOfflineEvent,
    DeviceOnlineEvent,
    EdgeDeviceRegisteredEvent,
    EdgeSiteRegisteredEvent,
    OTACompletedEvent,
    OTAStartedEvent,
    SynchronizationCompletedEvent,
    SynchronizationFailedEvent,
)

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
