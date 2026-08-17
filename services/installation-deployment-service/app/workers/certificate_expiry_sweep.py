"""The certificate expiry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Recomputes every certificate's own status against its ``not_after``,
notifying Certificate Expiring **only on the transition** into
``EXPIRING`` -- edge-triggered, not level-triggered, the same
"publish once, on the crossing, not on every tick past it" discipline
``services/public-api-platform``'s own quota-breach notification
established (Prompt 073), so a long-neglected certificate does not
flood the notification channel on every single tick between the
warning window opening and the certificate finally being rotated.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import TlsCertificateStatus
from app.services.bundle import build_repositories
from app.services.notifications import DeploymentNotifier
from app.services.tls import TlsCertificateService

logger = get_logger("app.workers.certificate_expiry_sweep")


class CertificateExpirySweepWorker:
    """Recomputes certificate expiry status and notifies on the
    valid -> expiring transition."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: DeploymentNotifier,
        warning_days: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._warning_days = warning_days

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Recompute every organization's own certificates, returning
        how many newly started expiring."""
        now = datetime.now(UTC)
        newly_expiring = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = TlsCertificateService(repos.tls_certificates)

            for organization_id in await repos.tls_certificates.list_organization_ids():
                for certificate in await repos.tls_certificates.list_all(organization_id):
                    previous_status = TlsCertificateStatus(certificate.status)
                    updated = await service.refresh_status(
                        certificate, now=now, warning_days=self._warning_days
                    )
                    new_status = TlsCertificateStatus(updated.status)
                    if (
                        new_status == TlsCertificateStatus.EXPIRING
                        and previous_status != new_status
                    ):
                        await self._notifier.notify_certificate_expiring(
                            common_name=updated.common_name, not_after=updated.not_after.isoformat()
                        )
                        newly_expiring += 1
            await session.commit()

        logger.info(
            "certificate expiry sweep completed",
            extra={"extra_fields": {"newly_expiring": newly_expiring}},
        )
        return newly_expiring


__all__ = ["CertificateExpirySweepWorker"]
