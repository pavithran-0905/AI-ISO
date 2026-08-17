"""Certificate inventory recording."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.certificates import CertificateInventoryEntry
from app.repositories.certificates import CertificateInventoryRepository


class CertificateInventoryService:
    def __init__(self, repo: CertificateInventoryRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        subject: str,
        expires_at: datetime,
        issuer: str = "",
        is_valid: bool = True,
        is_mutual_tls: bool = False,
    ) -> CertificateInventoryEntry:
        return await self._repo.create(
            CertificateInventoryEntry(
                organization_id=organization_id,
                subject=subject,
                issuer=issuer,
                expires_at=expires_at,
                is_valid=is_valid,
                is_mutual_tls=is_mutual_tls,
            )
        )


__all__ = ["CertificateInventoryService"]
