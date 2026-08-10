"""Prompt management domain events (docs/061 "EVENTS").

``PromptCreated``, ``PromptUpdated``, ``PromptPublished``,
``PromptDeprecated``, ``PromptExecuted``, ``PromptEvaluated``,
``PromptOptimized``, ``PromptApprovalRequested``,
``PromptSecurityViolation``. Each is a
:class:`shared_core.events.base.DomainEvent` registered with
:data:`shared_core.events.registry.default_registry` at import time --
the same idiom every prior AI-IOS service established (Prompt 020).
"""

from __future__ import annotations

from typing import ClassVar

from shared_core.events import default_registry
from shared_core.events.base import DomainEvent


@default_registry.register
class PromptCreatedEvent(DomainEvent):
    """A new prompt identity was registered."""

    event_name: ClassVar[str] = "PromptCreated"


@default_registry.register
class PromptUpdatedEvent(DomainEvent):
    """A prompt's own identity fields or a new draft revision changed."""

    event_name: ClassVar[str] = "PromptUpdated"


@default_registry.register
class PromptPublishedEvent(DomainEvent):
    """A revision became the live one.

    The event other services care about most: it means the text
    returned for this prompt's slug has changed for everyone.
    """

    event_name: ClassVar[str] = "PromptPublished"


@default_registry.register
class PromptDeprecatedEvent(DomainEvent):
    """A prompt was deprecated or archived."""

    event_name: ClassVar[str] = "PromptDeprecated"


@default_registry.register
class PromptExecutedEvent(DomainEvent):
    """A prompt was used in production and its execution recorded."""

    event_name: ClassVar[str] = "PromptExecuted"


@default_registry.register
class PromptEvaluatedEvent(DomainEvent):
    """An evaluation was scored against a revision."""

    event_name: ClassVar[str] = "PromptEvaluated"


@default_registry.register
class PromptOptimizedEvent(DomainEvent):
    """An optimization suggestion was accepted into a new draft."""

    event_name: ClassVar[str] = "PromptOptimized"


@default_registry.register
class PromptApprovalRequestedEvent(DomainEvent):
    """A revision entered the approval gate."""

    event_name: ClassVar[str] = "PromptApprovalRequested"


@default_registry.register
class PromptSecurityViolationEvent(DomainEvent):
    """A security scan blocked or flagged a revision.

    Carries the finding kinds and severities only -- never the matched
    text, which would put a detected secret onto the event bus and into
    every subscriber's own logs.
    """

    event_name: ClassVar[str] = "PromptSecurityViolation"


__all__ = [
    "PromptApprovalRequestedEvent",
    "PromptCreatedEvent",
    "PromptDeprecatedEvent",
    "PromptEvaluatedEvent",
    "PromptExecutedEvent",
    "PromptOptimizedEvent",
    "PromptPublishedEvent",
    "PromptSecurityViolationEvent",
    "PromptUpdatedEvent",
]
