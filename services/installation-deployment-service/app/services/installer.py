"""Installation sessions and their log lines.

Publishes ``InstallationStarted``/``InstallationCompleted`` on a
session's own lifecycle transitions, and notifies Installation Failed
directly when a session ends in ``FAILED``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import InstallationCompletedEvent, InstallationStartedEvent
from app.installer.engine import TransitionResult, validate_transition
from app.models.enums import InstallationMode, InstallationSessionStatus
from app.models.installation import InstallationLog, InstallationSession
from app.repositories.installation import InstallationLogRepository, InstallationSessionRepository
from app.services.notifications import DeploymentNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "installation-deployment-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class InstallationSessionService:
    def __init__(
        self,
        repo: InstallationSessionRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: DeploymentNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def create(
        self, organization_id: UUID, *, mode: InstallationMode, actor_id: str | None = None
    ) -> InstallationSession:
        return await self._repo.create(
            InstallationSession(organization_id=organization_id, mode=mode, actor_id=actor_id)
        )

    async def start(self, session: InstallationSession, *, now: datetime) -> InstallationSession:
        result = validate_transition(session.status, InstallationSessionStatus.RUNNING)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        session.status = InstallationSessionStatus.RUNNING
        session.started_at = now
        await self._repo.update(session)
        await self._publish(
            InstallationStartedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=session.organization_id,
                payload={"installation_session_id": str(session.id), "mode": str(session.mode)},
            )
        )
        return session

    async def complete(
        self,
        session: InstallationSession,
        *,
        status: InstallationSessionStatus,
        now: datetime,
        reason: str = "",
    ) -> InstallationSession:
        result = validate_transition(session.status, status)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        session.status = status
        session.completed_at = now
        await self._repo.update(session)
        await self._publish(
            InstallationCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=session.organization_id,
                payload={"installation_session_id": str(session.id), "status": status.value},
            )
        )
        if status == InstallationSessionStatus.FAILED and self._notifier is not None:
            await self._notifier.notify_installation_failed(reason=reason or "unspecified failure")
        return session


class InstallationLogService:
    def __init__(self, repo: InstallationLogRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        installation_session_id: UUID,
        level: str,
        message: str,
        now: datetime,
    ) -> InstallationLog:
        return await self._repo.create(
            InstallationLog(
                organization_id=organization_id,
                installation_session_id=installation_session_id,
                level=level,
                message=message,
                logged_at=now,
            )
        )


__all__ = ["InstallationLogService", "InstallationSessionService", "TransitionRefusedError"]
