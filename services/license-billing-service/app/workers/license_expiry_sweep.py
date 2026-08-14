"""The license expiry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Expires any issued/active license whose ``expires_at`` has passed and
notifies for it, so a customer never keeps using a license past what
they were actually entitled to.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.licenses.engine import is_expired
from app.models.enums import LicenseStatus
from app.services.bundle import build_repositories
from app.services.licenses import LicenseService
from app.services.notifications import BillingNotifier
from app.types import EventPublisher

logger = get_logger("app.workers.license_expiry_sweep")

_LIVE_STATUSES = frozenset({LicenseStatus.ISSUED, LicenseStatus.ACTIVE})


class LicenseExpirySweepWorker:
    """Expires licenses past their expiry and notifies for it."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        notifier: BillingNotifier,
        reminder_days_before: int,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._notifier = notifier
        self._reminder_days_before = reminder_days_before

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's licenses, returning how many were
        checked."""
        now = datetime.now(UTC)
        expiring_threshold = now + timedelta(days=self._reminder_days_before)
        checked = 0
        expired = 0
        expiring_soon = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = LicenseService(
                repos.licenses, repos.license_activations, publish=self._publish_event
            )

            for organization_id in await repos.licenses.list_organization_ids():
                for license_row in await repos.licenses.list_recent(organization_id, limit=5000):
                    if license_row.status not in _LIVE_STATUSES:
                        checked += 1
                        continue
                    if is_expired(license_row.expires_at, now=now):
                        await service.transition(
                            license_row, target=LicenseStatus.EXPIRED, actor_id=None, now=now
                        )
                        await self._notifier.notify_license_expired(
                            license_id=str(license_row.id), customer_id=str(license_row.customer_id)
                        )
                        expired += 1
                    elif (
                        license_row.expires_at is not None
                        and license_row.expires_at <= expiring_threshold
                    ):
                        expiring_soon += 1
                    checked += 1
            await session.commit()

        logger.info(
            "license expiry sweep completed",
            extra={
                "extra_fields": {
                    "checked": checked,
                    "expired": expired,
                    "expiring_soon": expiring_soon,
                }
            },
        )
        return checked


__all__ = ["LicenseExpirySweepWorker"]
