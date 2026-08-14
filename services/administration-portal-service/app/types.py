"""Shared type aliases for this service.

``EventPublisher`` is a protocol rather than a concrete manager so a
service can be constructed with a recording publisher in a test, and so
nothing in the domain layer imports the messaging framework.
"""

from __future__ import annotations

from typing import Protocol

from shared_core.events.base import BaseEvent


class EventPublisher(Protocol):
    """Publishes one domain event."""

    async def __call__(self, event: BaseEvent) -> None: ...


__all__ = ["EventPublisher"]
