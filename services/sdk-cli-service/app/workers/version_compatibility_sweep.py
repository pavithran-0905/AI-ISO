"""The version compatibility sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

For every SDK/CLI version carrying a planned ``deprecated_at`` date,
notifies once that date enters its own configured warning window, and
disables the version (``is_enabled = False``) once the date actually
arrives -- a version nobody explicitly disabled does not silently keep
being offered past its own announced deprecation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.bundle import build_repositories
from app.services.notifications import SdkCliNotifier

logger = get_logger("app.workers.version_compatibility_sweep")


class VersionCompatibilitySweepWorker:
    """Notifies for versions entering their deprecation warning window,
    and disables versions past their planned deprecation date."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: SdkCliNotifier,
        sdk_warning_days_before: int,
        cli_warning_days_before: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._sdk_warning_days_before = sdk_warning_days_before
        self._cli_warning_days_before = cli_warning_days_before

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's SDK and CLI versions, returning
        how many were checked."""
        now = datetime.now(UTC)
        checked = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            sdk_organization_ids = await repos.sdk_versions.list_organization_ids()
            for organization_id in sdk_organization_ids:
                for sdk_version in await repos.sdk_versions.list_with_planned_deprecation(
                    organization_id
                ):
                    if sdk_version.deprecated_at is None:
                        continue  # narrows the type; the query itself already guarantees this
                    if now >= sdk_version.deprecated_at:
                        sdk_version.is_enabled = False
                        await repos.sdk_versions.update(sdk_version)
                    elif now >= sdk_version.deprecated_at - timedelta(
                        days=self._sdk_warning_days_before
                    ):
                        await self._notifier.notify_deprecation_notice(
                            kind="SDK",
                            version=sdk_version.version_label,
                            deprecated_at=sdk_version.deprecated_at.isoformat(),
                        )
                    checked += 1

            cli_organization_ids = await repos.cli_versions.list_organization_ids()
            for organization_id in cli_organization_ids:
                for cli_version in await repos.cli_versions.list_with_planned_deprecation(
                    organization_id
                ):
                    if cli_version.deprecated_at is None:
                        continue  # narrows the type; the query itself already guarantees this
                    if now >= cli_version.deprecated_at:
                        cli_version.is_enabled = False
                        await repos.cli_versions.update(cli_version)
                    elif now >= cli_version.deprecated_at - timedelta(
                        days=self._cli_warning_days_before
                    ):
                        await self._notifier.notify_deprecation_notice(
                            kind="CLI",
                            version=cli_version.version_label,
                            deprecated_at=cli_version.deprecated_at.isoformat(),
                        )
                    checked += 1

            await session.commit()

        logger.info(
            "version compatibility sweep completed", extra={"extra_fields": {"checked": checked}}
        )
        return checked


__all__ = ["VersionCompatibilitySweepWorker"]
