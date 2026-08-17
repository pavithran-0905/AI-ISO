"""Runtime protection event recording."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import FindingSeverity, RuntimeProtectionEventType
from app.models.runtime_protection import RuntimeProtectionEvent
from app.repositories.runtime_protection import RuntimeProtectionEventRepository


class RuntimeProtectionService:
    def __init__(self, repo: RuntimeProtectionEventRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        event_type: RuntimeProtectionEventType,
        severity: FindingSeverity,
        detail: str = "",
        detected_at: datetime,
    ) -> RuntimeProtectionEvent:
        return await self._repo.create(
            RuntimeProtectionEvent(
                organization_id=organization_id,
                event_type=event_type,
                severity=severity,
                detail=detail,
                detected_at=detected_at,
            )
        )


__all__ = ["RuntimeProtectionService"]
