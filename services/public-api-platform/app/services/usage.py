"""Raw API usage event recording.

There is no ``POST`` route for ``api_usage`` -- docs/073's REST APIs
section lists exactly 15 endpoints and ingestion is not one of them
(that is the API Gateway's job per docs/073's own "DO NOT IMPLEMENT:
API Gateway Proxy Engine" -- this platform manages developers,
applications, and products, not live request traffic). This service
exists for internal recording (or, in tests, direct calls) and is only
ever read over HTTP via ``GET /usage``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.usage import ApiUsageEvent
from app.repositories.usage import ApiUsageEventRepository


class UsageService:
    def __init__(self, repo: ApiUsageEventRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        developer_account_id: UUID,
        application_id: UUID,
        api_product_id: UUID,
        endpoint: str,
        status_code: int,
        latency_ms: float,
        occurred_at: datetime,
    ) -> ApiUsageEvent:
        return await self._repo.create(
            ApiUsageEvent(
                organization_id=organization_id,
                developer_account_id=developer_account_id,
                application_id=application_id,
                api_product_id=api_product_id,
                endpoint=endpoint,
                status_code=status_code,
                latency_ms=latency_ms,
                occurred_at=occurred_at,
            )
        )


__all__ = ["UsageService"]
