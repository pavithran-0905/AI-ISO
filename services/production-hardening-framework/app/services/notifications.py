"""Notifications (docs/079 "NOTIFICATIONS", integrating Prompt 025).

**One of the seven notification kinds has a domain event behind it**
(Critical Vulnerability, fanned from ``VulnerabilityDetected`` -- but
only when the recorded severity is itself ``CRITICAL``) and is
dispatched by :class:`NotifyingPublisher`, an ``EventPublisher`` that
wraps the real one, forwards every event unchanged, and
opportunistically notifies for the subset that warrant it -- the same
pattern every prior AI-IOS service in this build established.

**Six kinds are called directly** by the code that observes the
underlying fact: Certificate Expiring and Certification Expired (their
own edge-triggered sweep workers, time-based rather than write-based),
Hardening Failed (the hardening run service, on a failed terminal
state), Certification Granted (the production certification service,
on grant), Compliance Failure (the compliance service, on a
non-compliant evaluation), Operational Risk (the operational readiness
service, on a failed check).
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_CRITICAL_VULNERABILITY = "production_hardening_framework.critical_vulnerability"
TOPIC_CERTIFICATE_EXPIRING = "production_hardening_framework.certificate_expiring"
TOPIC_HARDENING_FAILED = "production_hardening_framework.hardening_failed"
TOPIC_CERTIFICATION_GRANTED = "production_hardening_framework.certification_granted"
TOPIC_CERTIFICATION_EXPIRED = "production_hardening_framework.certification_expired"
TOPIC_COMPLIANCE_FAILURE = "production_hardening_framework.compliance_failure"
TOPIC_OPERATIONAL_RISK = "production_hardening_framework.operational_risk"


class HardeningNotifier:
    """Sends the seven notification kinds docs/079 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_critical_vulnerability(self, *, package_name: str, cve_id: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CRITICAL_VULNERABILITY,
            notification_type=NotificationType.CRITICAL,
            body=f"Critical vulnerability detected in {package_name!r} ({cve_id or 'no CVE'}).",
            priority=Priority.CRITICAL,
            variables={"package_name": package_name, "cve_id": cve_id},
        )

    async def notify_certificate_expiring(self, *, subject: str, days_remaining: float) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CERTIFICATE_EXPIRING,
            notification_type=NotificationType.WARNING,
            body=f"Certificate {subject!r} expires in {days_remaining:.0f} day(s).",
            priority=Priority.HIGH,
            variables={"subject": subject, "days_remaining": days_remaining},
        )

    async def notify_hardening_failed(
        self, *, hardening_profile_name: str, error_message: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_HARDENING_FAILED,
            notification_type=NotificationType.ERROR,
            body=f"Hardening run for {hardening_profile_name!r} failed: {error_message}",
            priority=Priority.HIGH,
            variables={
                "hardening_profile_name": hardening_profile_name,
                "error_message": error_message,
            },
        )

    async def notify_certification_granted(self, *, name: str, risk_score: float) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CERTIFICATION_GRANTED,
            notification_type=NotificationType.SUCCESS,
            body=f"Production certification granted for {name!r} (risk score {risk_score:.1f}).",
            priority=Priority.NORMAL,
            variables={"name": name, "risk_score": risk_score},
        )

    async def notify_certification_expired(self, *, name: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CERTIFICATION_EXPIRED,
            notification_type=NotificationType.WARNING,
            body=f"Production certification for {name!r} has expired.",
            priority=Priority.HIGH,
            variables={"name": name},
        )

    async def notify_compliance_failure(self, *, framework: str, control_id: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_COMPLIANCE_FAILURE,
            notification_type=NotificationType.ERROR,
            body=f"Compliance control {control_id!r} failed evaluation against {framework}.",
            priority=Priority.HIGH,
            variables={"framework": framework, "control_id": control_id},
        )

    async def notify_operational_risk(self, *, check_type: str, detail: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_OPERATIONAL_RISK,
            notification_type=NotificationType.WARNING,
            body=f"Operational readiness check {check_type!r} failed: {detail}",
            priority=Priority.HIGH,
            variables={"check_type": check_type, "detail": detail},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination exactly as if this wrapper were
    not there.
    """

    def __init__(self, inner: EventPublisher, notifier: HardeningNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "VulnerabilityDetected" and payload.get("severity") == "critical":
            await self._notifier.notify_critical_vulnerability(
                package_name=str(payload.get("package_name", "")),
                cve_id=str(payload.get("cve_id", "")),
            )


__all__ = ["HardeningNotifier", "NotifyingPublisher"]
