"""The domain events this service publishes (docs/066 "EVENTS",
integrating Prompt 020).

All eight the spec names. **Every event is registered with the shared
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
class ClusterRegisteredEvent(DomainEvent):
    """A cluster was registered with this service.

    Expected payload: ``cluster_id``, ``name``, ``cluster_type``,
    ``registration_method``.
    """

    event_name: ClassVar[str] = "ClusterRegistered"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ClusterValidatedEvent(DomainEvent):
    """A cluster's credentials and reachability were validated.

    Expected payload: ``cluster_id``, ``is_valid``, ``detail``.
    """

    event_name: ClassVar[str] = "ClusterValidated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ClusterProvisionedEvent(DomainEvent):
    """A cluster finished provisioning and is ready for configuration.

    Expected payload: ``cluster_id``, ``lifecycle_state``.
    """

    event_name: ClassVar[str] = "ClusterProvisioned"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ClusterUpgradedEvent(DomainEvent):
    """A cluster upgrade finished, successfully or not.

    Expected payload: ``cluster_id``, ``upgrade_id``, ``from_version``,
    ``to_version``, ``status``.
    """

    event_name: ClassVar[str] = "ClusterUpgraded"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ClusterHealthChangedEvent(DomainEvent):
    """A cluster's overall health status changed.

    Expected payload: ``cluster_id``, ``previous_status``, ``new_status``.
    """

    event_name: ClassVar[str] = "ClusterHealthChanged"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class PolicyAppliedEvent(DomainEvent):
    """A policy finished propagating to its target(s).

    Expected payload: ``policy_id``, ``target_cluster_ids``, ``status``.
    """

    event_name: ClassVar[str] = "PolicyApplied"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ComplianceUpdatedEvent(DomainEvent):
    """A cluster's compliance standing against one framework was
    reassessed.

    Expected payload: ``cluster_id``, ``framework``, ``status``, ``score``.
    """

    event_name: ClassVar[str] = "ComplianceUpdated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ClusterRemovedEvent(DomainEvent):
    """A cluster was decommissioned or archived and removed from active
    fleet management.

    Expected payload: ``cluster_id``, ``lifecycle_state``.
    """

    event_name: ClassVar[str] = "ClusterRemoved"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "ClusterHealthChangedEvent",
    "ClusterProvisionedEvent",
    "ClusterRegisteredEvent",
    "ClusterRemovedEvent",
    "ClusterUpgradedEvent",
    "ClusterValidatedEvent",
    "ComplianceUpdatedEvent",
    "PolicyAppliedEvent",
]
