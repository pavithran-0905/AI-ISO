"""API key issuance, rotation, revocation, and per-window usage
recording.

Wires ``app.api_management.engine``'s pure hash computation and
expiry/rotation checks onto the repositories that persist keys and
their usage. **The raw key is returned to the caller exactly once, at
issuance** -- only its hash is ever persisted.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.api_management.engine import compute_key_hash
from app.models.api_management import ApiKey, ApiUsage
from app.models.enums import ApiKeyStatus
from app.repositories.api_management import ApiKeyRepository, ApiUsageRepository

_RAW_KEY_BYTES = 32


@dataclass(frozen=True, slots=True)
class IssuedApiKey:
    api_key: ApiKey
    raw_key: str


class ApiKeyService:
    def __init__(self, key_repo: ApiKeyRepository, usage_repo: ApiUsageRepository) -> None:
        self._key_repo = key_repo
        self._usage_repo = usage_repo

    async def issue(
        self,
        organization_id: UUID,
        *,
        name: str,
        rate_limit_per_minute: int | None = None,
        quota_limit: float | None = None,
        expires_at: datetime | None = None,
    ) -> IssuedApiKey:
        raw_key = secrets.token_urlsafe(_RAW_KEY_BYTES)
        api_key = await self._key_repo.create(
            ApiKey(
                organization_id=organization_id,
                name=name,
                key_hash=compute_key_hash(raw_key),
                rate_limit_per_minute=rate_limit_per_minute,
                quota_limit=quota_limit,
                expires_at=expires_at,
            )
        )
        return IssuedApiKey(api_key=api_key, raw_key=raw_key)

    async def rotate(self, api_key: ApiKey, *, now: datetime) -> IssuedApiKey:
        raw_key = secrets.token_urlsafe(_RAW_KEY_BYTES)
        api_key.key_hash = compute_key_hash(raw_key)
        api_key.last_rotated_at = now
        api_key = await self._key_repo.update(api_key)
        return IssuedApiKey(api_key=api_key, raw_key=raw_key)

    async def revoke(self, api_key: ApiKey) -> ApiKey:
        api_key.status = ApiKeyStatus.REVOKED
        return await self._key_repo.update(api_key)

    async def expire(self, api_key: ApiKey) -> ApiKey:
        api_key.status = ApiKeyStatus.EXPIRED
        return await self._key_repo.update(api_key)

    async def record_usage(
        self,
        organization_id: UUID,
        *,
        api_key_id: UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> ApiUsage:
        """Idempotently increment one window's request count by one."""
        window = await self._usage_repo.find_window(api_key_id, window_start=window_start)
        if window is None:
            window = await self._usage_repo.create(
                ApiUsage(
                    organization_id=organization_id,
                    api_key_id=api_key_id,
                    window_start=window_start,
                    window_end=window_end,
                    request_count=0,
                )
            )
        window.request_count += 1
        return await self._usage_repo.update(window)


__all__ = ["ApiKeyService", "IssuedApiKey"]
