"""The plugin update sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

For every installed plugin, notifies once per sweep if any other
plugin sharing its name and marked ``AVAILABLE`` carries a newer
version.
"""

from __future__ import annotations

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import PluginStatus
from app.services.bundle import build_repositories
from app.services.notifications import SdkCliNotifier
from app.versioning.engine import is_update_available

logger = get_logger("app.workers.plugin_update_sweep")

_MAX_PLUGINS_PER_ORG = 5_000


class PluginUpdateSweepWorker:
    """Notifies for every installed plugin with a newer available
    version."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, notifier: SdkCliNotifier
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's installed plugins, returning how
        many had an update notified."""
        notified = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.cli_plugins.list_organization_ids():
                all_plugins = await repos.cli_plugins.list_recent(
                    organization_id, limit=_MAX_PLUGINS_PER_ORG
                )
                available_by_name: dict[str, list[str]] = {}
                for plugin in all_plugins:
                    if plugin.status == PluginStatus.AVAILABLE:
                        available_by_name.setdefault(plugin.name, []).append(plugin.version_label)

                for plugin in all_plugins:
                    if plugin.status != PluginStatus.INSTALLED:
                        continue
                    newer_versions = [
                        candidate
                        for candidate in available_by_name.get(plugin.name, [])
                        if is_update_available(plugin.version_label, candidate)
                    ]
                    if newer_versions:
                        latest = max(
                            newer_versions, key=lambda v: tuple(int(p) for p in v.split("."))
                        )
                        await self._notifier.notify_plugin_update_available(
                            plugin_name=plugin.name, latest_version=latest
                        )
                        notified += 1

        logger.info("plugin update sweep completed", extra={"extra_fields": {"notified": notified}})
        return notified


__all__ = ["PluginUpdateSweepWorker"]
