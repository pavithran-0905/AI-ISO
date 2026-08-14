"""The domain events this service publishes (docs/068 "EVENTS",
integrating Prompt 020).

All eight spec-named events. **Every event is registered with the
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
class CloudAccountRegisteredEvent(DomainEvent):
    """A new cloud account was registered.

    Expected payload: ``account_id``, ``provider_id``, ``name``.
    """

    event_name: ClassVar[str] = "CloudAccountRegistered"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class CloudResourceDiscoveredEvent(DomainEvent):
    """A resource was discovered in an account.

    Expected payload: ``resource_id``, ``account_id``, ``resource_type``.
    """

    event_name: ClassVar[str] = "CloudResourceDiscovered"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class CloudResourceProvisionedEvent(DomainEvent):
    """A resource finished provisioning and reached ``ACTIVE``.

    Expected payload: ``resource_id``, ``account_id``, ``lifecycle_state``.
    """

    event_name: ClassVar[str] = "CloudResourceProvisioned"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class CloudResourceUpdatedEvent(DomainEvent):
    """A resource's lifecycle state or attributes changed.

    Expected payload: ``resource_id``, ``lifecycle_state``.
    """

    event_name: ClassVar[str] = "CloudResourceUpdated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class CloudResourceDeletedEvent(DomainEvent):
    """A resource was deleted.

    Expected payload: ``resource_id``, ``account_id``.
    """

    event_name: ClassVar[str] = "CloudResourceDeleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class BudgetThresholdExceededEvent(DomainEvent):
    """A budget crossed its warning or critical threshold.

    Expected payload: ``budget_id``, ``status``, ``current_spend``,
    ``amount``.
    """

    event_name: ClassVar[str] = "BudgetThresholdExceeded"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class DriftDetectedEvent(DomainEvent):
    """Drift was detected on a resource.

    Expected payload: ``resource_id``, ``severity``.
    """

    event_name: ClassVar[str] = "DriftDetected"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class OptimizationCompletedEvent(DomainEvent):
    """A FinOps optimization pass finished for an account.

    Expected payload: ``account_id``, ``idle_resource_count``,
    ``recommendation_count``.
    """

    event_name: ClassVar[str] = "OptimizationCompleted"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "BudgetThresholdExceededEvent",
    "CloudAccountRegisteredEvent",
    "CloudResourceDeletedEvent",
    "CloudResourceDiscoveredEvent",
    "CloudResourceProvisionedEvent",
    "CloudResourceUpdatedEvent",
    "DriftDetectedEvent",
    "OptimizationCompletedEvent",
]
