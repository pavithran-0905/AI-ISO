"""The LTS support expiry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Notifies EOL Warning **only on the transition** into an LTS line's own
support-expiry warning window -- edge-triggered via the persisted
``support_expiry_notice_sent`` flag, the same "publish once, on the
crossing, not on every tick past it" discipline
``services/installation-deployment-service``'s own
``CertificateExpirySweepWorker`` established (Prompt 075) and
``services/production-hardening-framework``'s own
``CertificateExpirySweepWorker`` reused (Prompt 079).
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.lts.engine import is_support_expiring_soon
from app.services.bundle import build_repositories
from app.services.notifications import ReleaseNotifier

logger = get_logger("app.workers.lts_support_expiry_sweep")


class LtsSupportExpirySweepWorker:
    """Notifies of LTS lines newly entering their own support-expiry
    warning window."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: ReleaseNotifier,
        warning_days: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._warning_days = warning_days

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Notify for every LTS line newly entering its own warning
        window, returning how many were notified."""
        now = datetime.now(UTC)
        notified = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.lts_versions.list_organization_ids():
                for lts_version in await repos.lts_versions.list_active(organization_id):
                    if lts_version.support_expiry_notice_sent:
                        continue
                    if not is_support_expiring_soon(
                        support_ends_at=lts_version.support_ends_at,
                        now=now,
                        warning_days=self._warning_days,
                    ):
                        continue

                    version = await repos.release_versions.require_by_id(
                        lts_version.release_version_id
                    )
                    lts_version.support_expiry_notice_sent = True
                    await repos.lts_versions.update(lts_version)
                    await self._notifier.notify_eol_warning(
                        version_label=version.version_label,
                        eol_date=lts_version.support_ends_at.isoformat(),
                    )
                    notified += 1
            await session.commit()

        logger.info(
            "lts support expiry sweep completed", extra={"extra_fields": {"notified": notified}}
        )
        return notified


__all__ = ["LtsSupportExpirySweepWorker"]
