"""Immutability operations on archives: retention locks and legal
holds.

Wires ``app.immutability.engine``'s pure lock-extension and hold logic
onto :class:`~app.models.backup.BackupArchive` rows, and records every
change on the audit trail -- docs/065 names ``LEGAL_HOLD_APPLIED``
explicitly as an audited action.
"""

from __future__ import annotations

from datetime import datetime

from app.immutability.engine import (
    LockOutcome,
    apply_legal_hold,
    apply_retention_lock,
    release_legal_hold,
)
from app.models.backup import BackupArchive
from app.models.enums import AuditAction
from app.repositories.backup import BackupArchiveRepository
from app.services.audit import AuditService


class ImmutabilityService:
    """Applies and releases retention locks and legal holds on archives."""

    def __init__(self, repo: BackupArchiveRepository, *, audit: AuditService | None = None) -> None:
        self._repo = repo
        self._audit = audit

    async def lock(
        self, archive: BackupArchive, *, until: datetime, actor_id: str | None, now: datetime
    ) -> LockOutcome:
        outcome = apply_retention_lock(
            requested_until=until, existing_lock_until=archive.retention_lock_until
        )
        if outcome.accepted:
            archive.retention_lock_until = outcome.new_lock_until
            archive.immutability_state = outcome.new_state
            await self._repo.update(archive)
            if self._audit is not None:
                await self._audit.record(
                    archive.organization_id,
                    action=AuditAction.ADMINISTRATIVE,
                    entity_type="backup_archive",
                    entity_id=archive.id,
                    occurred_at=now,
                    actor_id=actor_id,
                    summary=f"Retention lock extended to {until.isoformat()}.",
                )
        return outcome

    async def apply_legal_hold(
        self, archive: BackupArchive, *, reason: str, actor_id: str | None, now: datetime
    ) -> BackupArchive:
        archive.immutability_state = apply_legal_hold(reason=reason)
        archive.legal_hold = True
        archive.legal_hold_reason = reason
        await self._repo.update(archive)
        if self._audit is not None:
            await self._audit.record(
                archive.organization_id,
                action=AuditAction.LEGAL_HOLD_APPLIED,
                entity_type="backup_archive",
                entity_id=archive.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Legal hold applied: {reason}",
            )
        return archive

    async def release_legal_hold(
        self, archive: BackupArchive, *, actor_id: str | None, now: datetime
    ) -> BackupArchive:
        archive.immutability_state = release_legal_hold(
            retention_lock_until=archive.retention_lock_until, now=now
        )
        archive.legal_hold = False
        await self._repo.update(archive)
        if self._audit is not None:
            await self._audit.record(
                archive.organization_id,
                action=AuditAction.ADMINISTRATIVE,
                entity_type="backup_archive",
                entity_id=archive.id,
                occurred_at=now,
                actor_id=actor_id,
                summary="Legal hold released.",
            )
        return archive


__all__ = ["ImmutabilityService"]
