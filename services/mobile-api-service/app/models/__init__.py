"""Imports every model so ``Base.metadata`` sees every table."""

from __future__ import annotations

from app.models.configuration import MobileAppVersion, MobileConfiguration
from app.models.devices import MobileDevice, MobileProfile, MobileSession, MobileToken
from app.models.notifications import MobileNotification, MobilePushToken
from app.models.reporting import MobileAudit, MobileReport
from app.models.sync import MobileSyncJob, MobileSyncQueueItem
from app.models.telemetry import MobileAnalyticsEvent, MobileTelemetryEvent

__all__ = [
    "MobileAnalyticsEvent",
    "MobileAppVersion",
    "MobileAudit",
    "MobileConfiguration",
    "MobileDevice",
    "MobileNotification",
    "MobileProfile",
    "MobilePushToken",
    "MobileReport",
    "MobileSession",
    "MobileSyncJob",
    "MobileSyncQueueItem",
    "MobileTelemetryEvent",
    "MobileToken",
]
