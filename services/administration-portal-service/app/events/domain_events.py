"""The domain events this service publishes (docs/070 "EVENTS",
integrating Prompt 020).

All ten spec-named events. **Every event is registered with the shared
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
class TenantCreatedEvent(DomainEvent):
    """A new tenant was provisioned.

    Expected payload: ``tenant_id``, ``organization_ref_id``, ``name``.
    """

    event_name: ClassVar[str] = "TenantCreated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class TenantUpdatedEvent(DomainEvent):
    """A tenant's status changed.

    Expected payload: ``tenant_id``, ``status``.
    """

    event_name: ClassVar[str] = "TenantUpdated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class TenantDeletedEvent(DomainEvent):
    """A tenant began deletion.

    Expected payload: ``tenant_id``.
    """

    event_name: ClassVar[str] = "TenantDeleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class FeatureFlagUpdatedEvent(DomainEvent):
    """A feature flag's definition changed.

    Expected payload: ``feature_flag_id``, ``name``.
    """

    event_name: ClassVar[str] = "FeatureFlagUpdated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class MaintenanceStartedEvent(DomainEvent):
    """A maintenance window began.

    Expected payload: ``maintenance_window_id``, ``title``.
    """

    event_name: ClassVar[str] = "MaintenanceStarted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class MaintenanceCompletedEvent(DomainEvent):
    """A maintenance window completed.

    Expected payload: ``maintenance_window_id``.
    """

    event_name: ClassVar[str] = "MaintenanceCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class AdminLoginEvent(DomainEvent):
    """An administrator session started.

    Expected payload: ``admin_user_id``, ``session_id``.
    """

    event_name: ClassVar[str] = "AdminLogin"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ConfigurationChangedEvent(DomainEvent):
    """A system configuration entry changed.

    Expected payload: ``key``, ``environment``.
    """

    event_name: ClassVar[str] = "ConfigurationChanged"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SecurityPolicyUpdatedEvent(DomainEvent):
    """A security policy setting changed.

    Expected payload: ``key``.
    """

    event_name: ClassVar[str] = "SecurityPolicyUpdated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class PlatformHealthChangedEvent(DomainEvent):
    """The platform's overall health status changed.

    Expected payload: ``component``, ``status``.
    """

    event_name: ClassVar[str] = "PlatformHealthChanged"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "AdminLoginEvent",
    "ConfigurationChangedEvent",
    "FeatureFlagUpdatedEvent",
    "MaintenanceCompletedEvent",
    "MaintenanceStartedEvent",
    "PlatformHealthChangedEvent",
    "SecurityPolicyUpdatedEvent",
    "TenantCreatedEvent",
    "TenantDeletedEvent",
    "TenantUpdatedEvent",
]
