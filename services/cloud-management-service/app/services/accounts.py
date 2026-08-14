"""Cloud account registration, credential revalidation, and health
classification.

Wires ``app.accounts.engine``'s pure credential validation and health
classification onto the repository that persists accounts, publishing
``CloudAccountRegistered``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.accounts.engine import CredentialValidation, classify_account_health, validate_credential
from app.events.domain_events import CloudAccountRegisteredEvent
from app.models.accounts import CloudAccount
from app.models.enums import AuditAction
from app.repositories.accounts import CloudAccountRepository
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "cloud-management-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class CredentialRefusedError(Exception):
    """Raised when an account's registered credential is not usable."""

    def __init__(self, validation: CredentialValidation) -> None:
        super().__init__(validation.detail)
        self.validation = validation


class CloudAccountService:
    def __init__(
        self,
        repo: CloudAccountRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit

    async def register_account(
        self,
        organization_id: UUID,
        *,
        provider_id: UUID,
        external_account_id: str,
        name: str,
        credential_ref: str,
        credential_expires_at: datetime | None,
        actor_id: str | None,
        now: datetime,
    ) -> CloudAccount:
        """Register an account, refusing an unusable credential.

        Raises:
            CredentialRefusedError: If *credential_ref* is empty or
                already expired.
        """
        validation = validate_credential(credential_ref, expires_at=credential_expires_at, now=now)
        if not validation.is_valid:
            raise CredentialRefusedError(validation)

        account = await self._repo.create(
            CloudAccount(
                organization_id=organization_id,
                provider_id=provider_id,
                external_account_id=external_account_id,
                name=name,
                credential_ref=credential_ref,
                credential_expires_at=credential_expires_at,
                is_valid=True,
                last_validated_at=now,
                health_status=classify_account_health(is_valid=True, is_stale=False),
                registered_at=now,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.ACCOUNT_REGISTERED,
                entity_type="cloud_account",
                entity_id=account.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Registered cloud account {name!r} ({external_account_id}).",
            )
        await self._publish(
            CloudAccountRegisteredEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "account_id": str(account.id),
                    "provider_id": str(provider_id),
                    "name": name,
                },
            )
        )
        return account

    async def revalidate(self, account: CloudAccount, *, now: datetime) -> CloudAccount:
        """Recheck an existing account's credential expiry right now.

        A revalidation that just ran is, by definition, not stale --
        the health sweep worker is what later reclassifies an account
        ``DEGRADED`` purely from elapsed time since this call, without
        re-running the check itself.
        """
        validation = validate_credential(
            account.credential_ref, expires_at=account.credential_expires_at, now=now
        )
        account.is_valid = validation.is_valid
        account.last_validated_at = now
        account.health_status = classify_account_health(
            is_valid=validation.is_valid, is_stale=False
        )
        return await self._repo.update(account)


__all__ = ["CloudAccountService", "CredentialRefusedError"]
