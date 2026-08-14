"""The app version compliance sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

For every approved device with a known ``app_version_label``, compares
it against its own platform's latest published version policy and
notifies Forced Upgrade (below the minimum) or App Update Available
(below the recommended, but not below the minimum) -- never both for
the same device on the same tick, since a forced upgrade already
implies an update is available.
"""

from __future__ import annotations

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import DeviceTrustStatus
from app.services.bundle import build_repositories
from app.services.notifications import MobileNotifier
from app.versions.engine import is_below_minimum, is_update_recommended

logger = get_logger("app.workers.app_version_compliance_sweep")


class AppVersionComplianceSweepWorker:
    """Notifies devices running an app version behind their platform's
    own policy."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, notifier: MobileNotifier
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's approved devices, returning how
        many were checked."""
        checked = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            organization_ids = await repos.devices.list_organization_ids()

            for organization_id in organization_ids:
                devices = await repos.devices.list_by_trust_status(
                    organization_id, trust_status=DeviceTrustStatus.APPROVED
                )
                policy_cache: dict[str, object] = {}
                for device in devices:
                    if device.app_version_label is None:
                        continue
                    platform_key = str(device.platform)
                    if platform_key not in policy_cache:
                        policy_cache[platform_key] = (
                            await repos.app_versions.find_latest_for_platform(
                                organization_id, platform=device.platform
                            )
                        )
                    policy = policy_cache[platform_key]
                    if policy is None:
                        continue

                    try:
                        below_minimum = is_below_minimum(
                            device.app_version_label, policy.minimum_version_label  # type: ignore[attr-defined]
                        )
                        update_recommended = is_update_recommended(
                            device.app_version_label, policy.recommended_version_label  # type: ignore[attr-defined]
                        )
                    except ValueError:
                        checked += 1
                        continue  # an unparseable device-reported version is skipped, not fatal

                    if below_minimum:
                        await self._notifier.notify_forced_upgrade(
                            platform=platform_key,
                            minimum_version=policy.minimum_version_label,  # type: ignore[attr-defined]
                        )
                    elif update_recommended:
                        await self._notifier.notify_app_update_available(
                            platform=platform_key,
                            recommended_version=policy.recommended_version_label,  # type: ignore[attr-defined]
                        )
                    checked += 1

        logger.info(
            "app version compliance sweep completed", extra={"extra_fields": {"checked": checked}}
        )
        return checked


__all__ = ["AppVersionComplianceSweepWorker"]
