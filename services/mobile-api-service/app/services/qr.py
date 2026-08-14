"""QR-code onboarding token issuance and redemption.

Tokens are one-time and self-expiring, so they live in Redis (through
:class:`~shared_core.cache.manager.CacheManager` -- "No service shall
communicate directly with Redis," per docs/019) rather than in a
Postgres table: there is no ``mobile_qr_tokens`` table among docs/072's
fourteen, and a value that only needs to exist for its own short TTL
before being redeemed exactly once is precisely what a cache, not the
system of record, is for. Redemption reads then deletes the key, so a
second redemption attempt finds nothing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from shared_core.cache.manager import CacheManager

from app.models.enums import QrPurpose
from app.qr.engine import generate_qr_token

_KEY_PREFIX = "mobile_api:qr:"


class QrService:
    def __init__(self, cache: CacheManager) -> None:
        self._cache = cache

    async def issue(
        self,
        organization_id: UUID,
        *,
        purpose: QrPurpose,
        ttl_minutes: int,
        now: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Mint and store a fresh one-time QR token, returning the raw
        token value to be embedded in the QR code."""
        token = generate_qr_token()
        payload = {
            "organization_id": str(organization_id),
            "purpose": purpose.value,
            "issued_at": now.isoformat(),
            **(metadata or {}),
        }
        await self._cache.set(f"{_KEY_PREFIX}{token}", payload, ttl_seconds=ttl_minutes * 60)
        return token

    async def redeem(self, token: str) -> dict[str, Any] | None:
        """Redeem *token*, returning its payload exactly once, or
        ``None`` if it was never issued, already redeemed, or has
        expired."""
        key = f"{_KEY_PREFIX}{token}"
        payload = await self._cache.get(key)
        if payload is None:
            return None
        await self._cache.delete(key)
        return dict(payload)


__all__ = ["QrService"]
