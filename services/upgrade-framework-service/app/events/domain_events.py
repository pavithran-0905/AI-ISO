"""The domain events this service publishes (docs/076 "EVENTS",
integrating Prompt 020).

All nine spec-named events. **Every event is registered with the
shared registry at import time.** ``EventManager.publish`` validates
against :data:`shared_core.events.registry.default_registry` and
refuses anything unregistered as ``AIIOS-EVENT-0002``.

**Fields live in ``payload``**, per :class:`~shared_core.events.base.BaseEvent`
-- not as typed attributes on each subclass, matching the convention
every other AI-IOS service follows.

**Unlike ``services/installation-deployment-service``'s own single
``UpgradeCompleted`` (status-carrying) event, this service's spec names
``UpgradeCompleted`` and ``UpgradeFailed`` as two distinct events** --
honored here rather than collapsed into one, since the two prompts'
own specs genuinely differ on this point.
"""

from __future__ import annotations

from typing import ClassVar

from shared_core.events import default_registry
from shared_core.events.base import DomainEvent


@default_registry.register
class UpgradeScheduledEvent(DomainEvent):
    """An upgrade job was scheduled but has not yet started.

    Expected payload: ``upgrade_job_id``, ``upgrade_plan_id``.
    """

    event_name: ClassVar[str] = "UpgradeScheduled"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class UpgradeStartedEvent(DomainEvent):
    """An upgrade job began running.

    Expected payload: ``upgrade_job_id``, ``upgrade_plan_id``.
    """

    event_name: ClassVar[str] = "UpgradeStarted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class UpgradeCompletedEvent(DomainEvent):
    """An upgrade job succeeded.

    Expected payload: ``upgrade_job_id``.
    """

    event_name: ClassVar[str] = "UpgradeCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class UpgradeFailedEvent(DomainEvent):
    """An upgrade job failed.

    Expected payload: ``upgrade_job_id``, ``error_message``.
    """

    event_name: ClassVar[str] = "UpgradeFailed"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class RollbackStartedEvent(DomainEvent):
    """A rollback began.

    Expected payload: ``upgrade_job_id``, ``from_version``, ``to_version``.
    """

    event_name: ClassVar[str] = "RollbackStarted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class RollbackCompletedEvent(DomainEvent):
    """A rollback finished, successfully or not.

    Expected payload: ``upgrade_job_id``, ``status``, ``to_version``.
    """

    event_name: ClassVar[str] = "RollbackCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class CompatibilityValidatedEvent(DomainEvent):
    """A compatibility check was validated.

    Expected payload: ``compatibility_type``, ``status``.
    """

    event_name: ClassVar[str] = "CompatibilityValidated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class MigrationCompletedEvent(DomainEvent):
    """A migration step finished, successfully or not.

    Expected payload: ``upgrade_job_id``, ``migration_type``, ``status``.
    """

    event_name: ClassVar[str] = "MigrationCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ReleasePublishedEvent(DomainEvent):
    """A new release version was published to a channel.

    Expected payload: ``release_channel_id``, ``version_label``.
    """

    event_name: ClassVar[str] = "ReleasePublished"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "CompatibilityValidatedEvent",
    "MigrationCompletedEvent",
    "ReleasePublishedEvent",
    "RollbackCompletedEvent",
    "RollbackStartedEvent",
    "UpgradeCompletedEvent",
    "UpgradeFailedEvent",
    "UpgradeScheduledEvent",
    "UpgradeStartedEvent",
]
