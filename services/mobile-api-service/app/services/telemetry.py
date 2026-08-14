"""Raw telemetry and analytics event recording.

Like app version policy, configuration, and reports, there is no
``POST`` route for either table -- docs/072's REST APIs section lists
exactly thirteen endpoints and neither telemetry nor analytics
ingestion is among them. These services exist for internal recording
(a background collector, or a test/hand-verification seeding data for
``GET /mobile/statistics`` to aggregate).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.models.enums import AnalyticsMetricType, TelemetryMetricType
from app.models.telemetry import MobileAnalyticsEvent, MobileTelemetryEvent
from app.repositories.telemetry import (
    MobileAnalyticsEventRepository,
    MobileTelemetryEventRepository,
)


class TelemetryService:
    def __init__(self, repo: MobileTelemetryEventRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        device_id: UUID,
        metric_type: TelemetryMetricType,
        value: float,
        recorded_at: datetime,
        detail: dict[str, Any] | None = None,
    ) -> MobileTelemetryEvent:
        return await self._repo.create(
            MobileTelemetryEvent(
                organization_id=organization_id,
                device_id=device_id,
                metric_type=metric_type,
                value=value,
                detail=detail or {},
                recorded_at=recorded_at,
            )
        )


class AnalyticsService:
    def __init__(self, repo: MobileAnalyticsEventRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        device_id: UUID,
        user_id: str,
        metric_type: AnalyticsMetricType,
        value: float,
        recorded_at: datetime,
        detail: dict[str, Any] | None = None,
    ) -> MobileAnalyticsEvent:
        return await self._repo.create(
            MobileAnalyticsEvent(
                organization_id=organization_id,
                device_id=device_id,
                user_id=user_id,
                metric_type=metric_type,
                value=value,
                detail=detail or {},
                recorded_at=recorded_at,
            )
        )


__all__ = ["AnalyticsService", "TelemetryService"]
