"""Resource utilization sampling.

Notifies Infrastructure Bottleneck directly, synchronously, the
moment a recorded sample itself is at bottleneck level -- the same
caller-reported-outcome, notify-on-write shape
``services/testing-quality-framework``'s own ``SecurityService`` uses
(Prompt 077), since this process cannot itself probe live resource
utilization beyond what a caller reports."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import ResourceType
from app.models.utilization import ResourceUtilization
from app.repositories.utilization import ResourceUtilizationRepository
from app.services.notifications import BenchmarkNotifier
from app.utilization.engine import is_bottleneck


class ResourceUtilizationService:
    def __init__(
        self, repo: ResourceUtilizationRepository, *, notifier: BenchmarkNotifier | None = None
    ) -> None:
        self._repo = repo
        self._notifier = notifier

    async def record(
        self,
        organization_id: UUID,
        *,
        resource_type: ResourceType,
        utilization_percent: float,
        recorded_at: datetime,
    ) -> ResourceUtilization:
        sample = await self._repo.create(
            ResourceUtilization(
                organization_id=organization_id,
                resource_type=resource_type,
                utilization_percent=utilization_percent,
                recorded_at=recorded_at,
            )
        )
        if self._notifier is not None and is_bottleneck(utilization_percent):
            await self._notifier.notify_infrastructure_bottleneck(
                resource_type=str(resource_type), utilization_percent=utilization_percent
            )
        return sample


__all__ = ["ResourceUtilizationService"]
