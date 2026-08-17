"""Import ``domain_events`` so every event registers with the shared
registry at process startup."""

from __future__ import annotations

from app.events import domain_events

__all__ = ["domain_events"]
