"""Runtime protection event classification."""

from __future__ import annotations

from app.models.enums import FindingSeverity, RuntimeProtectionEventType

_ALWAYS_CRITICAL_EVENT_TYPES = frozenset(
    {RuntimeProtectionEventType.PRIVILEGE_ESCALATION, RuntimeProtectionEventType.THREAT_DETECTION}
)


def is_critical_event(*, event_type: RuntimeProtectionEventType, severity: FindingSeverity) -> bool:
    """Whether a runtime protection event warrants an immediate
    incident response -- either its own recorded severity is
    ``CRITICAL``, or its event type is one this platform always treats
    as critical regardless of the severity it was recorded with
    (privilege escalation and active threat detection)."""
    if FindingSeverity(severity) == FindingSeverity.CRITICAL:
        return True
    return RuntimeProtectionEventType(event_type) in _ALWAYS_CRITICAL_EVENT_TYPES


__all__ = ["is_critical_event"]
