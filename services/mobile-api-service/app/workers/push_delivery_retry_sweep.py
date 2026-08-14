"""The push delivery retry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

**Delivery is a declared seam.** Actually handing a payload to Firebase
Cloud Messaging or the Apple Push Notification Service is an external
integration this service does not implement (docs/072 "DO NOT
IMPLEMENT" excludes native platform SDKs). What this worker *can*
honestly determine is whether the target device has a currently usable
registered push token: if it does, the notification is considered
handed off (``DELIVERED``); if it does not, delivery fails and retries
per :func:`app.push.engine.is_retry_eligible` until the configured
retry budget is exhausted, at which point it is marked ``FAILED`` and
``PushFailed`` is published.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from shared_core.database.tenant import TenantScope
from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.push.engine import is_push_token_usable
from app.services.bundle import build_repositories
from app.services.push import PushService
from app.types import EventPublisher

logger = get_logger("app.workers.push_delivery_retry_sweep")

_MAX_ITEMS_PER_TICK = 1_000


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class PushDeliveryRetrySweepWorker:
    """Attempts delivery of every organization's pending push
    notifications."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish: EventPublisher = _noop_publisher,
        max_retry_count: int,
    ) -> None:
        self._session_factory = session_factory
        self._publish = publish
        self._max_retry_count = max_retry_count

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Attempt delivery for every organization's pending
        notifications, returning how many were attempted."""
        now = datetime.now(UTC)
        attempted = 0

        async with self._session_factory() as session:
            unscoped_repos = build_repositories(session)
            organization_ids = await unscoped_repos.notifications.list_organization_ids()

            for organization_id in organization_ids:
                attempted += await self._process_organization(session, organization_id, now=now)
            await session.commit()

        logger.info(
            "push delivery retry sweep completed", extra={"extra_fields": {"attempted": attempted}}
        )
        return attempted

    async def _process_organization(
        self, session: AsyncSession, organization_id: UUID, *, now: datetime
    ) -> int:
        repos = build_repositories(
            session, tenant_scope=TenantScope(organization_id=organization_id)
        )
        push_service = PushService(repos.push_tokens, repos.notifications, publish=self._publish)

        pending = await repos.notifications.list_pending(organization_id, limit=_MAX_ITEMS_PER_TICK)
        attempted = 0
        for notification in pending:
            device = await repos.devices.get_by_id(notification.device_id)
            device_identifier = device.device_identifier if device is not None else "unknown"

            tokens = await repos.push_tokens.list_active_for_device(
                organization_id, device_id=notification.device_id
            )
            token_usable = any(is_push_token_usable(token.status) for token in tokens)

            await push_service.attempt_delivery(
                notification,
                device_identifier,
                token_usable=token_usable,
                max_retry_count=self._max_retry_count,
                now=now,
            )
            attempted += 1
        return attempted


__all__ = ["PushDeliveryRetrySweepWorker"]
