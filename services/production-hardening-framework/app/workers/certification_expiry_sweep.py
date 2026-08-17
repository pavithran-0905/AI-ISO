"""The certification expiry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Transitions every ``GRANTED`` production certification whose own
``expires_at`` has passed to ``EXPIRED`` and notifies Certification
Expired. **Inherently edge-triggered**: once a certification leaves
``GRANTED`` status it is no longer picked up by this sweep's own
``GRANTED``-only query, so it cannot re-notify on a later tick.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.certification.engine import is_expired
from app.models.enums import CertificationStatus
from app.services.bundle import build_repositories
from app.services.notifications import HardeningNotifier

logger = get_logger("app.workers.certification_expiry_sweep")


class CertificationExpirySweepWorker:
    """Expires production certifications whose own expiration date has
    passed."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, notifier: HardeningNotifier
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Expire every organization's own overdue certifications,
        returning how many were expired."""
        now = datetime.now(UTC)
        expired = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.production_certifications.list_organization_ids():
                for certification in await repos.production_certifications.list_by_status(
                    organization_id, status=CertificationStatus.GRANTED
                ):
                    if not is_expired(expires_at=certification.expires_at, now=now):
                        continue

                    certification.status = CertificationStatus.EXPIRED
                    await repos.production_certifications.update(certification)
                    await self._notifier.notify_certification_expired(name=certification.name)
                    expired += 1
            await session.commit()

        logger.info(
            "certification expiry sweep completed", extra={"extra_fields": {"expired": expired}}
        )
        return expired


__all__ = ["CertificationExpirySweepWorker"]
