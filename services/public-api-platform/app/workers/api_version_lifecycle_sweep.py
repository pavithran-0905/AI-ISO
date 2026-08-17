"""The API version lifecycle sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Moves every released version into ``DEPRECATED`` once its own planned
``deprecated_at`` date arrives (notifying Deprecation Notice), and every
deprecated version into ``SUNSET`` once its own planned ``sunset_at``
date arrives.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import ApiVersionStatus
from app.services.bundle import build_repositories
from app.services.notifications import DeveloperNotifier
from app.versioning.engine import is_deprecation_due, is_sunset_due

logger = get_logger("app.workers.api_version_lifecycle_sweep")


class ApiVersionLifecycleSweepWorker:
    """Advances API versions through deprecation and sunset on their
    own planned dates."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, notifier: DeveloperNotifier
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's API versions, returning how many
        were checked."""
        now = datetime.now(UTC)
        checked = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.api_versions.list_organization_ids():
                for version in await repos.api_versions.list_with_planned_deprecation(
                    organization_id
                ):
                    if version.status == ApiVersionStatus.RELEASED and is_deprecation_due(
                        deprecated_at=version.deprecated_at, now=now
                    ):
                        version.status = ApiVersionStatus.DEPRECATED
                        await repos.api_versions.update(version)
                        product = await repos.api_products.get_by_id(version.api_product_id)
                        product_name = product.name if product is not None else "unknown"
                        await self._notifier.notify_deprecation_notice(
                            product_name=product_name, version=version.version_label
                        )
                    checked += 1

                for version in await repos.api_versions.list_with_planned_sunset(organization_id):
                    if version.status == ApiVersionStatus.DEPRECATED and is_sunset_due(
                        sunset_at=version.sunset_at, now=now
                    ):
                        version.status = ApiVersionStatus.SUNSET
                        await repos.api_versions.update(version)
                    checked += 1

            await session.commit()

        logger.info(
            "api version lifecycle sweep completed", extra={"extra_fields": {"checked": checked}}
        )
        return checked


__all__ = ["ApiVersionLifecycleSweepWorker"]
