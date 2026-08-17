"""The domain events this service publishes (docs/080 "EVENTS",
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
class ReleaseCreatedEvent(DomainEvent):
    """A new release version was created.

    Expected payload: ``release_version_id``, ``version_label``.
    """

    event_name: ClassVar[str] = "ReleaseCreated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ReleaseValidatedEvent(DomainEvent):
    """A release version passed validation.

    Expected payload: ``release_version_id``.
    """

    event_name: ClassVar[str] = "ReleaseValidated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ReleaseSignedEvent(DomainEvent):
    """A release version's own artifacts were signed.

    Expected payload: ``release_version_id``.
    """

    event_name: ClassVar[str] = "ReleaseSigned"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ReleasePublishedEvent(DomainEvent):
    """A release version was published.

    Expected payload: ``release_version_id``, ``version_label``.
    """

    event_name: ClassVar[str] = "ReleasePublished"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ReleasePromotedEvent(DomainEvent):
    """A release version was promoted from one channel to another.

    Expected payload: ``release_promotion_id``, ``from_channel``, ``to_channel``.
    """

    event_name: ClassVar[str] = "ReleasePromoted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ReleaseDownloadedEvent(DomainEvent):
    """A release artifact was downloaded.

    Expected payload: ``release_artifact_id``.
    """

    event_name: ClassVar[str] = "ReleaseDownloaded"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ReleaseArchivedEvent(DomainEvent):
    """A release version was archived.

    Expected payload: ``release_version_id``.
    """

    event_name: ClassVar[str] = "ReleaseArchived"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class LTSReleasedEvent(DomainEvent):
    """A release version was designated as a new LTS line.

    Expected payload: ``lts_version_id``, ``release_version_id``.
    """

    event_name: ClassVar[str] = "LTSReleased"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class EOLAnnouncedEvent(DomainEvent):
    """A release version's own end-of-life warning window was
    entered.

    Expected payload: ``eol_schedule_id``, ``release_version_id``.
    """

    event_name: ClassVar[str] = "EOLAnnounced"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "EOLAnnouncedEvent",
    "LTSReleasedEvent",
    "ReleaseArchivedEvent",
    "ReleaseCreatedEvent",
    "ReleaseDownloadedEvent",
    "ReleasePromotedEvent",
    "ReleasePublishedEvent",
    "ReleaseSignedEvent",
    "ReleaseValidatedEvent",
]
