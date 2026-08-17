"""The domain events this service publishes (docs/075 "EVENTS",
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
class InstallationStartedEvent(DomainEvent):
    """An installation session began.

    Expected payload: ``installation_session_id``, ``mode``.
    """

    event_name: ClassVar[str] = "InstallationStarted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class InstallationCompletedEvent(DomainEvent):
    """An installation session finished, successfully or not.

    Expected payload: ``installation_session_id``, ``status``.
    """

    event_name: ClassVar[str] = "InstallationCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class DeploymentStartedEvent(DomainEvent):
    """A deployment job began.

    Expected payload: ``deployment_job_id``, ``job_type``.
    """

    event_name: ClassVar[str] = "DeploymentStarted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class DeploymentCompletedEvent(DomainEvent):
    """A deployment job finished, successfully or not.

    Expected payload: ``deployment_job_id``, ``status``.
    """

    event_name: ClassVar[str] = "DeploymentCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class UpgradeStartedEvent(DomainEvent):
    """An upgrade began.

    Expected payload: ``deployment_job_id``, ``from_version``, ``to_version``.
    """

    event_name: ClassVar[str] = "UpgradeStarted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class UpgradeCompletedEvent(DomainEvent):
    """An upgrade finished, successfully or not.

    Expected payload: ``deployment_job_id``, ``status``.
    """

    event_name: ClassVar[str] = "UpgradeCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class RollbackStartedEvent(DomainEvent):
    """A rollback began.

    Expected payload: ``deployment_job_id``, ``from_version``, ``to_version``.
    """

    event_name: ClassVar[str] = "RollbackStarted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class RollbackCompletedEvent(DomainEvent):
    """A rollback finished, successfully or not.

    Expected payload: ``deployment_job_id``, ``status``, ``to_version``.
    """

    event_name: ClassVar[str] = "RollbackCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ValidationCompletedEvent(DomainEvent):
    """A preflight or post-install validation run finished.

    Expected payload: ``check_type``, ``status``.
    """

    event_name: ClassVar[str] = "ValidationCompleted"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "DeploymentCompletedEvent",
    "DeploymentStartedEvent",
    "InstallationCompletedEvent",
    "InstallationStartedEvent",
    "RollbackCompletedEvent",
    "RollbackStartedEvent",
    "UpgradeCompletedEvent",
    "UpgradeStartedEvent",
    "ValidationCompletedEvent",
]
