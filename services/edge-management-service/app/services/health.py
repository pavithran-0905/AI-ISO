"""Device health recording and aggregation.

Wires ``app.health.engine``'s pure component rollup onto the repository
that persists health readings and the device's own denormalized
``health_status``. No dedicated event is published here -- docs/067
names no health-changed event, only the offline/online boundary
``app.services.devices`` already covers.
"""

from __future__ import annotations

from datetime import datetime

from app.health.engine import ComponentReading, HealthAggregation, aggregate_health
from app.models.devices import EdgeDevice
from app.models.enums import ComponentHealthStatus, DeviceComponent
from app.models.operations import EdgeHealth
from app.repositories.devices import EdgeDeviceRepository
from app.repositories.operations import EdgeHealthRepository


class HealthService:
    def __init__(
        self, health_repo: EdgeHealthRepository, device_repo: EdgeDeviceRepository
    ) -> None:
        self._health_repo = health_repo
        self._device_repo = device_repo

    async def record_reading(
        self,
        device: EdgeDevice,
        *,
        component: DeviceComponent,
        status: ComponentHealthStatus,
        reading_value: float | None,
        detail: str | None,
        now: datetime,
    ) -> EdgeHealth:
        return await self._health_repo.create(
            EdgeHealth(
                organization_id=device.organization_id,
                device_id=device.id,
                component=component,
                status=status,
                reading_value=reading_value,
                detail=detail,
                checked_at=now,
            )
        )

    async def refresh_overall_status(
        self, device: EdgeDevice, *, degraded_threshold: int, unhealthy_threshold: int
    ) -> HealthAggregation:
        """Recompute *device*'s overall health from its latest
        per-component readings and persist it."""
        rows = await self._health_repo.latest_per_component(device.id)
        readings = [ComponentReading(component=row.component, status=row.status) for row in rows]
        aggregation = aggregate_health(
            readings, degraded_threshold=degraded_threshold, unhealthy_threshold=unhealthy_threshold
        )
        device.health_status = aggregation.overall
        await self._device_repo.update(device)
        return aggregation


__all__ = ["HealthService"]
