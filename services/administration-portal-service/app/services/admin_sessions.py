"""Administrator session lifecycle and administrative action logging.

Wires ``app.security.engine``'s pure session-expiry check onto the
repository that persists sessions, publishing ``AdminLogin`` on start.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from app.events.domain_events import AdminLoginEvent
from app.models.admin import AdminAction, AdminSession
from app.repositories.admin import AdminActionRepository, AdminSessionRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "administration-portal-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class AdminSessionService:
    def __init__(
        self, repo: AdminSessionRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def start_session(
        self,
        organization_id: UUID,
        *,
        admin_user_id: str,
        max_age_minutes: int,
        now: datetime,
        ip_address: str | None = None,
    ) -> AdminSession:
        session = await self._repo.create(
            AdminSession(
                organization_id=organization_id,
                admin_user_id=admin_user_id,
                started_at=now,
                expires_at=now + timedelta(minutes=max_age_minutes),
                ip_address=ip_address,
            )
        )
        await self._publish(
            AdminLoginEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"admin_user_id": admin_user_id, "session_id": str(session.id)},
            )
        )
        return session

    async def force_logout(self, session: AdminSession) -> AdminSession:
        session.is_enabled = False
        return await self._repo.update(session)

    def is_usable(self, session: AdminSession, *, now: datetime) -> bool:
        """Whether *session* is still enabled and has not outlived its
        own recorded ``expires_at``."""
        return session.is_enabled and now < session.expires_at


class AdminActionService:
    def __init__(self, repo: AdminActionRepository) -> None:
        self._repo = repo

    async def log(
        self,
        organization_id: UUID,
        *,
        admin_user_id: str,
        action: str,
        target_type: str,
        target_id: UUID | None,
        now: datetime,
        detail: str | None = None,
    ) -> AdminAction:
        return await self._repo.create(
            AdminAction(
                organization_id=organization_id,
                admin_user_id=admin_user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                performed_at=now,
                detail=detail,
            )
        )


__all__ = ["AdminActionService", "AdminSessionService"]
