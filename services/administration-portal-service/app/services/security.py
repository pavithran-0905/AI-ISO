"""Security policy settings and security event recording.

Wires ``app.security.engine``'s pure password/IP/session checks onto
the repositories that persist security policy settings and detected
events, notifying ``notify_security_event`` and publishing
``SecurityPolicyUpdated`` on a policy change.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import SecurityPolicyUpdatedEvent
from app.models.enums import SecurityEventKind, SecurityEventSeverity
from app.models.security import SecurityEvent, SecuritySetting
from app.repositories.security import SecurityEventRepository, SecuritySettingRepository
from app.services.notifications import AdminNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "administration-portal-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class SecuritySettingService:
    def __init__(
        self, repo: SecuritySettingRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def upsert(
        self, organization_id: UUID, *, key: str, value: dict[str, object]
    ) -> SecuritySetting:
        existing = await self._repo.find_by_key(organization_id, key=key)
        if existing is not None:
            existing.value = value
            setting = await self._repo.update(existing)
        else:
            setting = await self._repo.create(
                SecuritySetting(organization_id=organization_id, key=key, value=value)
            )
        await self._publish(
            SecurityPolicyUpdatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"key": key},
            )
        )
        return setting


class SecurityEventService:
    def __init__(
        self, repo: SecurityEventRepository, *, notifier: AdminNotifier | None = None
    ) -> None:
        self._repo = repo
        self._notifier = notifier

    async def record(
        self,
        organization_id: UUID,
        *,
        kind: SecurityEventKind,
        severity: SecurityEventSeverity,
        now: datetime,
        actor_id: str | None = None,
        ip_address: str | None = None,
        detail: str | None = None,
    ) -> SecurityEvent:
        event = await self._repo.create(
            SecurityEvent(
                organization_id=organization_id,
                kind=kind,
                severity=severity,
                detected_at=now,
                actor_id=actor_id,
                ip_address=ip_address,
                detail=detail,
            )
        )
        if self._notifier is not None:
            await self._notifier.notify_security_event(
                security_event_id=str(event.id), kind=kind.value, severity=severity.value
            )
        return event


__all__ = ["SecurityEventService", "SecuritySettingService"]
