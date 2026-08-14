"""The CLI update check sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

For every organization's latest enabled CLI version, notifies once per
sweep for every other still-enabled version behind it.
"""

from __future__ import annotations

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.bundle import build_repositories
from app.services.notifications import SdkCliNotifier
from app.versioning.engine import is_update_available

logger = get_logger("app.workers.cli_update_check_sweep")

_MAX_VERSIONS_PER_ORG = 5_000


class CliUpdateCheckSweepWorker:
    """Notifies for every still-enabled CLI version behind the latest
    one."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, notifier: SdkCliNotifier
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's CLI versions, returning how many
        outdated versions were notified for."""
        notified = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.cli_versions.list_organization_ids():
                latest = await repos.cli_versions.latest_enabled(organization_id)
                if latest is None:
                    continue
                for version in await repos.cli_versions.list_recent(
                    organization_id, limit=_MAX_VERSIONS_PER_ORG
                ):
                    if not version.is_enabled or version.id == latest.id:
                        continue
                    if is_update_available(version.version_label, latest.version_label):
                        await self._notifier.notify_cli_update_available(
                            current_version=version.version_label,
                            latest_version=latest.version_label,
                        )
                        notified += 1

        logger.info(
            "CLI update check sweep completed", extra={"extra_fields": {"notified": notified}}
        )
        return notified


__all__ = ["CliUpdateCheckSweepWorker"]
