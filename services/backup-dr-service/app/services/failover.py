"""Failover execution: health-gated automatic failover, ungated manual
failover and failback.

Wires ``app.failover.engine``'s pure health aggregation and
authorization onto the repository that persists failover events, and
publishes ``FailoverStarted`` / ``FailoverCompleted``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import FailoverCompletedEvent, FailoverStartedEvent
from app.failover.engine import (
    AuthorizationResult,
    HealthCheckResult,
    assess_health,
    authorize_failover,
)
from app.models.enums import FailoverKind, FailoverStatus
from app.models.recovery import FailoverEvent
from app.repositories.recovery import FailoverEventRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "backup-dr-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class FailoverService:
    """Authorizes and executes failover and failback."""

    def __init__(
        self, repo: FailoverEventRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    def authorize(
        self, kind: FailoverKind, health_checks: list[HealthCheckResult]
    ) -> AuthorizationResult:
        assessment = assess_health(health_checks)
        return authorize_failover(kind, assessment)

    async def initiate(
        self,
        organization_id: UUID,
        *,
        dr_plan_id: UUID | None,
        kind: FailoverKind,
        source_ref: str | None,
        target_ref: str | None,
        initiated_by: str | None,
        health_checks: list[HealthCheckResult],
        now: datetime,
    ) -> FailoverEvent:
        event = await self._repo.create(
            FailoverEvent(
                organization_id=organization_id,
                dr_plan_id=dr_plan_id,
                failover_kind=kind,
                status=FailoverStatus.HEALTH_CHECKING,
                source_ref=source_ref,
                target_ref=target_ref,
                initiated_by=initiated_by,
                initiated_at=now,
                health_check_results=[
                    {"check_name": r.check_name, "is_healthy": r.is_healthy, "detail": r.detail}
                    for r in health_checks
                ],
            )
        )
        await self._publish(
            FailoverStartedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "failover_event_id": str(event.id),
                    "failover_kind": str(kind),
                    "dr_plan_id": str(dr_plan_id) if dr_plan_id else None,
                },
            )
        )
        return event

    async def complete(
        self,
        event: FailoverEvent,
        *,
        succeeded: bool,
        was_rolled_back: bool,
        error_message: str | None,
        now: datetime,
    ) -> FailoverEvent:
        event.status = FailoverStatus.COMPLETED if succeeded else FailoverStatus.FAILED
        event.completed_at = now
        event.duration_ms = (now - event.initiated_at).total_seconds() * 1000.0
        event.was_rolled_back = was_rolled_back
        event.error_message = error_message
        await self._repo.update(event)
        await self._publish(
            FailoverCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=event.organization_id,
                payload={
                    "failover_event_id": str(event.id),
                    "status": str(event.status),
                    "was_rolled_back": was_rolled_back,
                },
            )
        )
        return event


__all__ = ["FailoverService"]
