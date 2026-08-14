"""The domain events this service publishes (docs/071 "EVENTS",
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
class SdkReleasedEvent(DomainEvent):
    """An SDK version was published.

    Expected payload: ``sdk_release_id``, ``language``, ``version``.
    """

    event_name: ClassVar[str] = "SDKReleased"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class CliReleasedEvent(DomainEvent):
    """A CLI version was published.

    Expected payload: ``cli_version_id``, ``version``.
    """

    event_name: ClassVar[str] = "CLIReleased"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SdkDownloadedEvent(DomainEvent):
    """An SDK package was downloaded.

    Expected payload: ``sdk_version_id``, ``language``.
    """

    event_name: ClassVar[str] = "SDKDownloaded"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class CliDownloadedEvent(DomainEvent):
    """A CLI package was downloaded.

    Expected payload: ``cli_version_id``.
    """

    event_name: ClassVar[str] = "CLIDownloaded"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class PluginInstalledEvent(DomainEvent):
    """A CLI plugin was installed.

    Expected payload: ``cli_plugin_id``, ``name``.
    """

    event_name: ClassVar[str] = "PluginInstalled"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class PluginUpdatedEvent(DomainEvent):
    """A CLI plugin's status changed.

    Expected payload: ``cli_plugin_id``, ``status``.
    """

    event_name: ClassVar[str] = "PluginUpdated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class AuthenticationSucceededEvent(DomainEvent):
    """A CLI session authenticated successfully.

    Expected payload: ``cli_session_id``, ``auth_method``.
    """

    event_name: ClassVar[str] = "AuthenticationSucceeded"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ProfileCreatedEvent(DomainEvent):
    """A CLI profile was created.

    Expected payload: ``cli_profile_id``, ``profile_name``.
    """

    event_name: ClassVar[str] = "ProfileCreated"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "AuthenticationSucceededEvent",
    "CliDownloadedEvent",
    "CliReleasedEvent",
    "PluginInstalledEvent",
    "PluginUpdatedEvent",
    "ProfileCreatedEvent",
    "SdkDownloadedEvent",
    "SdkReleasedEvent",
]
