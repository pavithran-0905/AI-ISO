"""Developer application registration and lifecycle transitions.

Publishes ``ApplicationCreated`` on every new application, and notifies
Application Approved directly on the ``-> ACTIVE`` transition.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.applications.engine import TransitionResult, validate_transition
from app.events.domain_events import ApplicationCreatedEvent
from app.models.applications import DeveloperApplication
from app.models.enums import ApplicationStatus, DeveloperAuditAction
from app.repositories.applications import DeveloperApplicationRepository
from app.services.audit import AuditService
from app.services.notifications import DeveloperNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "public-api-platform"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class ApplicationService:
    def __init__(
        self,
        repo: DeveloperApplicationRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
        notifier: DeveloperNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit
        self._notifier = notifier

    async def register(
        self,
        organization_id: UUID,
        *,
        developer_account_id: UUID,
        name: str,
        description: str = "",
        redirect_uris: list[str] | None = None,
        allowed_origins: list[str] | None = None,
        scopes: list[str] | None = None,
        now: datetime,
        actor_id: str | None = None,
    ) -> DeveloperApplication:
        application = await self._repo.create(
            DeveloperApplication(
                organization_id=organization_id,
                developer_account_id=developer_account_id,
                name=name,
                description=description,
                redirect_uris=redirect_uris or [],
                allowed_origins=allowed_origins or [],
                scopes=scopes or [],
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id=organization_id,
                action=DeveloperAuditAction.APPLICATION_CHANGE,
                entity_type="developer_application",
                entity_id=application.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Application {name!r} registered.",
            )
        await self._publish(
            ApplicationCreatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "application_id": str(application.id),
                    "developer_account_id": str(developer_account_id),
                    "name": name,
                },
            )
        )
        return application

    async def transition(
        self,
        application: DeveloperApplication,
        *,
        target: ApplicationStatus,
        now: datetime,
        actor_id: str | None = None,
    ) -> DeveloperApplication:
        """Move *application* to *target*, raising
        :class:`TransitionRefusedError` if the transition is not
        allowed."""
        result = validate_transition(application.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        application.status = target
        if target == ApplicationStatus.ACTIVE:
            application.approved_at = now
        elif target == ApplicationStatus.REVOKED:
            application.revoked_at = now
        await self._repo.update(application)

        if self._audit is not None:
            await self._audit.record(
                organization_id=application.organization_id,
                action=DeveloperAuditAction.APPLICATION_CHANGE,
                entity_type="developer_application",
                entity_id=application.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Application {application.name!r} moved to {target.value}.",
            )
        if target == ApplicationStatus.ACTIVE and self._notifier is not None:
            await self._notifier.notify_application_approved(application_name=application.name)
        return application


__all__ = ["ApplicationService", "TransitionRefusedError"]
