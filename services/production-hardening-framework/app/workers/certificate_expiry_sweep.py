"""The certificate expiry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Notifies Certificate Expiring **only on the transition** into the
warning window -- edge-triggered via the persisted ``is_expiring``
flag, the same "publish once, on the crossing, not on every tick past
it" discipline ``services/installation-deployment-service``'s own
``CertificateExpirySweepWorker`` established (Prompt 075), so a
long-neglected certificate does not flood the notification channel on
every tick between the warning window opening and the certificate
finally being rotated.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.certificates.engine import is_expiring_soon
from app.services.bundle import build_repositories
from app.services.notifications import HardeningNotifier

logger = get_logger("app.workers.certificate_expiry_sweep")


class CertificateExpirySweepWorker:
    """Notifies of certificates newly entering their own expiry
    warning window."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: HardeningNotifier,
        warning_days: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._warning_days = warning_days

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Notify for every certificate newly entering its own warning
        window, returning how many were notified."""
        now = datetime.now(UTC)
        notified = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.certificate_inventory.list_organization_ids():
                for certificate in await repos.certificate_inventory.list_valid(organization_id):
                    if certificate.is_expiring:
                        continue
                    if not is_expiring_soon(
                        expires_at=certificate.expires_at, now=now, warning_days=self._warning_days
                    ):
                        continue

                    certificate.is_expiring = True
                    await repos.certificate_inventory.update(certificate)
                    days_remaining = (certificate.expires_at - now).total_seconds() / 86400
                    await self._notifier.notify_certificate_expiring(
                        subject=certificate.subject, days_remaining=days_remaining
                    )
                    notified += 1
            await session.commit()

        logger.info(
            "certificate expiry sweep completed", extra={"extra_fields": {"notified": notified}}
        )
        return notified


__all__ = ["CertificateExpirySweepWorker"]
