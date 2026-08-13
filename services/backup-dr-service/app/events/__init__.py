"""Domain events. Imported at process startup so every event class
registers with the shared registry before anything tries to publish one."""

from app.events.domain_events import (
    BackupCompletedEvent,
    BackupFailedEvent,
    BackupStartedEvent,
    DRTestCompletedEvent,
    FailoverCompletedEvent,
    FailoverStartedEvent,
    RecoveryValidatedEvent,
    RestoreCompletedEvent,
    RestoreStartedEvent,
)

__all__ = [
    "BackupCompletedEvent",
    "BackupFailedEvent",
    "BackupStartedEvent",
    "DRTestCompletedEvent",
    "FailoverCompletedEvent",
    "FailoverStartedEvent",
    "RecoveryValidatedEvent",
    "RestoreCompletedEvent",
    "RestoreStartedEvent",
]
