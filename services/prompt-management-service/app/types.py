"""Shared type aliases for this service.

``EventPublisher`` lives here rather than in whichever module happened
to need it first, since several do (prompt lifecycle, governance,
optimization, A/B evaluation). Mirrors ``ai-assistant-service``'s own
``app/types.py`` (Prompt 046) shape.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from shared_core.events.base import DomainEvent

EventPublisher = Callable[[DomainEvent], Awaitable[None]]
"""Publishes one domain event. Satisfied by
``shared_core.events.manager.EventManager.publish``.
"""

__all__ = ["EventPublisher"]
