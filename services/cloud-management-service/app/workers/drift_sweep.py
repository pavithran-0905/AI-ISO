"""The drift sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Escalates any drift event that has sat ``DETECTED`` (unresolved,
unacknowledged) past the configured staleness window one severity
level, and re-notifies -- drift nobody has acted on does not become
less urgent just because time passed; it becomes more so.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.events.domain_events import DriftDetectedEvent
from app.models.enums import DriftSeverity
from app.services.bundle import build_repositories
from app.services.notifications import CloudNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "cloud-management-service"

logger = get_logger("app.workers.drift_sweep")

_ESCALATION_ORDER = (
    DriftSeverity.LOW,
    DriftSeverity.MEDIUM,
    DriftSeverity.HIGH,
    DriftSeverity.CRITICAL,
)


def _escalate(severity: DriftSeverity) -> DriftSeverity:
    """The next severity level up from *severity*, capped at
    ``CRITICAL``."""
    index = _ESCALATION_ORDER.index(DriftSeverity(severity))
    return _ESCALATION_ORDER[min(index + 1, len(_ESCALATION_ORDER) - 1)]


class DriftSweepWorker:
    """Escalates stale unresolved drift events."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        notifier: CloudNotifier,
        stale_after_minutes: int = 1_440,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._notifier = notifier
        self._stale_after_minutes = stale_after_minutes

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Escalate every stale unresolved drift event, returning how
        many were escalated."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=self._stale_after_minutes)
        escalated = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.drift.list_organization_ids():
                for drift in await repos.drift.list_detected(organization_id):
                    if drift.detected_at > cutoff:
                        continue
                    drift.severity = _escalate(drift.severity)
                    await repos.drift.update(drift)
                    await self._publish_event(
                        DriftDetectedEvent(
                            source_service=_SOURCE_SERVICE,
                            organization_id=organization_id,
                            payload={
                                "resource_id": str(drift.resource_id),
                                "severity": str(drift.severity),
                            },
                        )
                    )
                    await self._notifier.notify_drift_detected(
                        resource_id=str(drift.resource_id), severity=str(drift.severity)
                    )
                    escalated += 1
            await session.commit()

        logger.info("drift sweep completed", extra={"extra_fields": {"escalated": escalated}})
        return escalated


__all__ = ["DriftSweepWorker"]
