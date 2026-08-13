"""The domain events this service publishes (docs/065 "EVENTS",
integrating Prompt 020).

All nine the spec names. **Every event is registered with the shared
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
class BackupStartedEvent(DomainEvent):
    """A backup job began executing.

    Expected payload: ``job_id``, ``target_id``, ``target_name``,
    ``backup_type``.
    """

    event_name: ClassVar[str] = "BackupStarted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class BackupCompletedEvent(DomainEvent):
    """A backup job finished writing successfully.

    Expected payload: ``job_id``, ``target_id``, ``size_bytes``,
    ``duration_ms``.
    """

    event_name: ClassVar[str] = "BackupCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class BackupFailedEvent(DomainEvent):
    """A backup job failed.

    Expected payload: ``job_id``, ``target_id``, ``error_message``.
    """

    event_name: ClassVar[str] = "BackupFailed"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class RestoreStartedEvent(DomainEvent):
    """A restore job began executing.

    Expected payload: ``restore_job_id``, ``restore_kind``,
    ``is_preview``.
    """

    event_name: ClassVar[str] = "RestoreStarted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class RestoreCompletedEvent(DomainEvent):
    """A restore job finished.

    Expected payload: ``restore_job_id``, ``status``, ``duration_ms``.
    """

    event_name: ClassVar[str] = "RestoreCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class FailoverStartedEvent(DomainEvent):
    """A failover or failback was initiated.

    Expected payload: ``failover_event_id``, ``failover_kind``,
    ``dr_plan_id``.
    """

    event_name: ClassVar[str] = "FailoverStarted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class FailoverCompletedEvent(DomainEvent):
    """A failover or failback finished, successfully or not.

    Expected payload: ``failover_event_id``, ``status``,
    ``was_rolled_back``.
    """

    event_name: ClassVar[str] = "FailoverCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class RecoveryValidatedEvent(DomainEvent):
    """A restore or failover's outcome was checked against its RPO/RTO
    target.

    Expected payload: ``recovery_report_id``, ``compliance_status``.
    """

    event_name: ClassVar[str] = "RecoveryValidated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class DRTestCompletedEvent(DomainEvent):
    """A disaster recovery drill finished.

    Expected payload: ``dr_test_id``, ``dr_plan_id``, ``status``,
    ``rpo_status``, ``rto_status``.
    """

    event_name: ClassVar[str] = "DRTestCompleted"
    event_version: ClassVar[str] = "v1"


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
