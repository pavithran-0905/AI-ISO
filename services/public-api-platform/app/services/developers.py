"""Developer account registration, email verification, and lifecycle
transitions.

Publishes ``DeveloperRegistered`` on every new account, and notifies
Developer Approved directly on the ``-> ACTIVE`` transition (there is
no domain event that transition would otherwise fan out from).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.developers.engine import (
    TransitionResult,
    is_eligible_for_activation,
    validate_transition,
)
from app.events.domain_events import DeveloperRegisteredEvent
from app.models.developers import DeveloperAccount
from app.models.enums import DeveloperAccountStatus, DeveloperAuditAction
from app.repositories.developers import DeveloperAccountRepository
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


class ActivationNotEligibleError(Exception):
    """Raised when a developer account is moved to ``ACTIVE`` before its
    own email has been verified."""


class DeveloperAccountService:
    def __init__(
        self,
        repo: DeveloperAccountRepository,
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
        email: str,
        display_name: str = "",
        developer_organization_id: UUID | None = None,
        now: datetime,
    ) -> DeveloperAccount:
        account = await self._repo.create(
            DeveloperAccount(
                organization_id=organization_id,
                email=email,
                display_name=display_name,
                developer_organization_id=developer_organization_id,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id=organization_id,
                action=DeveloperAuditAction.DEVELOPER_REGISTRATION,
                entity_type="developer_account",
                entity_id=account.id,
                occurred_at=now,
                summary=f"Developer account {email!r} registered.",
            )
        await self._publish(
            DeveloperRegisteredEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"developer_account_id": str(account.id), "email": email},
            )
        )
        return account

    async def verify_email(self, account: DeveloperAccount, *, now: datetime) -> DeveloperAccount:
        account.email_verified_at = now
        return await self._repo.update(account)

    async def transition(
        self,
        account: DeveloperAccount,
        *,
        target: DeveloperAccountStatus,
        now: datetime,
        actor_id: str | None = None,
    ) -> DeveloperAccount:
        """Move *account* to *target*, raising
        :class:`TransitionRefusedError` if the transition is not
        allowed or :class:`ActivationNotEligibleError` if moving to
        ``ACTIVE`` before the account's own email is verified."""
        result = validate_transition(account.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        if target == DeveloperAccountStatus.ACTIVE and not is_eligible_for_activation(
            account.email_verified_at
        ):
            raise ActivationNotEligibleError(
                f"Developer account {account.email!r} has not verified its own email."
            )

        account.status = target
        if target == DeveloperAccountStatus.ACTIVE:
            account.approved_at = now
        elif target == DeveloperAccountStatus.SUSPENDED:
            account.suspended_at = now
        await self._repo.update(account)

        if self._audit is not None:
            await self._audit.record(
                organization_id=account.organization_id,
                action=DeveloperAuditAction.ADMINISTRATIVE,
                entity_type="developer_account",
                entity_id=account.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Developer account {account.email!r} moved to {target.value}.",
            )
        if target == DeveloperAccountStatus.ACTIVE and self._notifier is not None:
            await self._notifier.notify_developer_approved(email=account.email)
        return account


__all__ = ["ActivationNotEligibleError", "DeveloperAccountService", "TransitionRefusedError"]
