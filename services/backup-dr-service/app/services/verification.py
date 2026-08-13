"""Backup verification: persisting the outcome of a checksum or sample
restore check.

Wires ``app.verification.engine``'s pure checksum comparison onto the
repository that persists the verdict -- kept apart from the job it
verifies, per :class:`~app.models.backup.BackupVerification`'s own
docstring.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.backup import BackupVerification
from app.models.enums import VerificationKind
from app.repositories.backup import BackupVerificationRepository
from app.verification.engine import verify_checksum


class VerificationService:
    """Runs and persists backup verification checks."""

    def __init__(self, repo: BackupVerificationRepository) -> None:
        self._repo = repo

    async def verify_checksum_for_job(
        self,
        organization_id: UUID,
        *,
        job_id: UUID,
        archive_id: UUID | None,
        expected_checksum: str | None,
        actual_checksum: str,
        now: datetime,
    ) -> BackupVerification:
        verdict = verify_checksum(expected=expected_checksum, actual=actual_checksum)
        return await self._repo.create(
            BackupVerification(
                organization_id=organization_id,
                job_id=job_id,
                archive_id=archive_id,
                verification_kind=VerificationKind.CHECKSUM,
                status=verdict.status,
                verified_at=now,
                checksum_expected=expected_checksum,
                checksum_actual=actual_checksum,
                error_message=None if verdict.status.value != "failed" else verdict.detail,
            )
        )


__all__ = ["VerificationService"]
