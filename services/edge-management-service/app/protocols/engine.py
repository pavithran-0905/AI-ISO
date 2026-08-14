"""Industrial protocol connectivity classification.

**Connectivity is classified from what was actually observed, never
assumed.** A protocol endpoint nothing has checked yet is ``UNKNOWN``,
not ``CONNECTED`` -- this build tracks connectivity state; it holds no
protocol drivers (see this package's README "Scope boundary").
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models.enums import ProtocolHealthStatus


def classify_connectivity(
    last_checked_at: datetime | None, *, had_error: bool, now: datetime, stale_after_minutes: int
) -> ProtocolHealthStatus:
    """Classify a protocol endpoint's connectivity from its last check.

    A check that recorded an error is ``ERROR`` regardless of how
    recently it ran. A check old enough to be stale is ``UNKNOWN`` --
    connectivity this service has not verified recently is not evidence
    either way. Otherwise a recent, error-free check is ``CONNECTED``.
    """
    if had_error:
        return ProtocolHealthStatus.ERROR
    if last_checked_at is None:
        return ProtocolHealthStatus.UNKNOWN
    if now - last_checked_at > timedelta(minutes=stale_after_minutes):
        return ProtocolHealthStatus.UNKNOWN
    return ProtocolHealthStatus.CONNECTED


__all__ = ["classify_connectivity"]
