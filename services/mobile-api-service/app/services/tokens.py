"""Device-bound mobile token issuance and expiry."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

from app.models.devices import MobileToken
from app.models.enums import TokenStatus
from app.repositories.devices import MobileTokenRepository

_TOKEN_BYTES = 32


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("ascii")).hexdigest()


class MobileTokenService:
    def __init__(self, repo: MobileTokenRepository) -> None:
        self._repo = repo

    async def issue(
        self, organization_id: UUID, *, device_id: UUID, now: datetime, max_age_days: int
    ) -> tuple[MobileToken, str]:
        """Issue a fresh device-bound token, returning the persisted
        row and the raw token value (shown once, never stored)."""
        raw_token = secrets.token_urlsafe(_TOKEN_BYTES)
        token = await self._repo.create(
            MobileToken(
                organization_id=organization_id,
                device_id=device_id,
                token_hash=_hash_token(raw_token),
                issued_at=now,
                expires_at=now + timedelta(days=max_age_days),
            )
        )
        return token, raw_token

    async def revoke(self, token: MobileToken, *, now: datetime) -> MobileToken:
        token.status = TokenStatus.REVOKED
        token.revoked_at = now
        return await self._repo.update(token)


__all__ = ["MobileTokenService"]
