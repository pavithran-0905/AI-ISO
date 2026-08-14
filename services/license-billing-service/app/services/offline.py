"""Offline license file issuance and validation.

Wires ``app.offline.engine``'s pure hash computation and validation
onto the repository that persists offline license tracking rows.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.licenses import OfflineLicense
from app.offline.engine import OfflineLicenseValidation, compute_file_hash, validate_offline_license
from app.repositories.licenses import OfflineLicenseRepository


class OfflineLicenseService:
    def __init__(self, repo: OfflineLicenseRepository) -> None:
        self._repo = repo

    async def issue(
        self,
        organization_id: UUID,
        *,
        license_id: UUID,
        file_content: bytes,
        expires_at: datetime,
        now: datetime,
    ) -> OfflineLicense:
        return await self._repo.create(
            OfflineLicense(
                organization_id=organization_id,
                license_id=license_id,
                license_file_hash=compute_file_hash(file_content),
                issued_at=now,
                expires_at=expires_at,
            )
        )

    async def validate(
        self, offline_license: OfflineLicense, *, file_content: bytes, now: datetime
    ) -> OfflineLicenseValidation:
        return validate_offline_license(
            file_content,
            expected_hash=offline_license.license_file_hash,
            is_revoked=offline_license.is_revoked,
            expires_at=offline_license.expires_at,
            now=now,
        )

    async def revoke(self, offline_license: OfflineLicense) -> OfflineLicense:
        offline_license.is_revoked = True
        return await self._repo.update(offline_license)


__all__ = ["OfflineLicenseService"]
