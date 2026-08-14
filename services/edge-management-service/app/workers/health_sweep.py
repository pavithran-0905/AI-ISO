"""The health sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Recomputes every device's overall health from its latest per-component
readings, and marks a device whose ``last_seen_at`` has gone stale
offline -- a device that stopped phoning home is not still whatever it
last reported.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.devices.engine import is_stale
from app.services.bundle import build_repositories
from app.services.devices import EdgeDeviceService
from app.services.health import HealthService
from app.services.notifications import EdgeNotifier
from app.types import EventPublisher

logger = get_logger("app.workers.health_sweep")


class HealthSweepWorker:
    """Recomputes overall health for every device and detects
    offline/stale ones."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        notifier: EdgeNotifier,
        degraded_threshold: int,
        unhealthy_threshold: int,
        stale_threshold_minutes: int,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._notifier = notifier
        self._degraded_threshold = degraded_threshold
        self._unhealthy_threshold = unhealthy_threshold
        self._stale_threshold_minutes = stale_threshold_minutes

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Recompute health for every device, returning how many were
        checked."""
        now = datetime.now(UTC)
        checked = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            device_service = EdgeDeviceService(repos.devices, publish=self._publish_event)
            health_service = HealthService(repos.health, repos.devices)

            for organization_id in await repos.devices.list_organization_ids():
                for device in await repos.devices.list_recent(organization_id, limit=5000):
                    if is_stale(
                        device.last_seen_at,
                        now=now,
                        threshold_minutes=self._stale_threshold_minutes,
                    ):
                        was_online = device.is_online
                        await device_service.mark_offline(device, now=now)
                        if was_online:
                            await self._notifier.notify_device_offline(
                                device_id=str(device.id), device_name=device.name
                            )
                    else:
                        await health_service.refresh_overall_status(
                            device,
                            degraded_threshold=self._degraded_threshold,
                            unhealthy_threshold=self._unhealthy_threshold,
                        )
                    checked += 1
            await session.commit()

        logger.info("health sweep completed", extra={"extra_fields": {"checked": checked}})
        return checked


__all__ = ["HealthSweepWorker"]
