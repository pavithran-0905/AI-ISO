"""The domain events this service publishes (docs/074 "EVENTS",
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
class DeveloperLoggedInEvent(DomainEvent):
    """A developer started a new portal session.

    Expected payload: ``user_id``.
    """

    event_name: ClassVar[str] = "DeveloperLoggedIn"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class DocumentationPublishedEvent(DomainEvent):
    """A documentation page was published.

    Expected payload: ``documentation_page_id``, ``slug``.
    """

    event_name: ClassVar[str] = "DocumentationPublished"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class TutorialCompletedEvent(DomainEvent):
    """A developer reported completing a tutorial.

    Expected payload: ``tutorial_id``, ``user_id``.
    """

    event_name: ClassVar[str] = "TutorialCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SDKDownloadedEvent(DomainEvent):
    """An SDK was downloaded through the portal's SDK center.

    Expected payload: ``user_id``, ``language``, ``version``.
    """

    event_name: ClassVar[str] = "SDKDownloaded"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class PluginSubmittedEvent(DomainEvent):
    """A plugin submission was created.

    Expected payload: ``plugin_submission_id``, ``plugin_name``.
    """

    event_name: ClassVar[str] = "PluginSubmitted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class PluginPublishedEvent(DomainEvent):
    """A plugin submission was approved and published.

    Expected payload: ``plugin_submission_id``, ``plugin_name``.
    """

    event_name: ClassVar[str] = "PluginPublished"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class CommunityPostCreatedEvent(DomainEvent):
    """A community post was created.

    Expected payload: ``community_post_id``, ``post_type``.
    """

    event_name: ClassVar[str] = "CommunityPostCreated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SearchPerformedEvent(DomainEvent):
    """A search was performed through the portal.

    Expected payload: ``user_id``, ``query``, ``result_count``.
    """

    event_name: ClassVar[str] = "SearchPerformed"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class AIAssistantUsedEvent(DomainEvent):
    """The AI documentation assistant answered a question.

    Expected payload: ``user_id``, ``confidence``.
    """

    event_name: ClassVar[str] = "AIAssistantUsed"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "AIAssistantUsedEvent",
    "CommunityPostCreatedEvent",
    "DeveloperLoggedInEvent",
    "DocumentationPublishedEvent",
    "PluginPublishedEvent",
    "PluginSubmittedEvent",
    "SDKDownloadedEvent",
    "SearchPerformedEvent",
    "TutorialCompletedEvent",
]
