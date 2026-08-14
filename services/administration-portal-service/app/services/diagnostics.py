"""Diagnostic runs and component health checks.

Wires ``app.diagnostics.engine``'s pure latency classification and
status aggregation onto the repositories that persist diagnostic runs
and the latest health-check reading per component, publishing
``PlatformHealthChanged`` on a crossing.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.diagnostics.engine import aggregate_overall_status, classify_latency_status
from app.events.domain_events import PlatformHealthChangedEvent
from app.models.diagnostics import Diagnostic, HealthCheck
from app.models.enums import DiagnosticCategory, HealthCheckStatus
from app.repositories.diagnostics import DiagnosticRepository, HealthCheckRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "administration-portal-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class DiagnosticsService:
    def __init__(
        self,
        diagnostic_repo: DiagnosticRepository,
        health_repo: HealthCheckRepository,
        *,
        publish: EventPublisher = _noop_publisher,
    ) -> None:
        self._diagnostic_repo = diagnostic_repo
        self._health_repo = health_repo
        self._publish = publish

    async def run_diagnostic(
        self,
        organization_id: UUID,
        *,
        category: DiagnosticCategory,
        latency_ms: float | None,
        warning_ms: float,
        critical_ms: float,
        now: datetime,
        detail: str | None = None,
    ) -> Diagnostic:
        status = classify_latency_status(latency_ms, warning_ms=warning_ms, critical_ms=critical_ms)
        return await self._diagnostic_repo.create(
            Diagnostic(
                organization_id=organization_id,
                category=category,
                ran_at=now,
                status=status,
                latency_ms=latency_ms,
                detail=detail,
            )
        )

    async def record_health_check(
        self,
        organization_id: UUID,
        *,
        component: str,
        status: HealthCheckStatus,
        now: datetime,
        detail: str | None = None,
    ) -> HealthCheck:
        """Idempotently update *component*'s latest health reading,
        publishing ``PlatformHealthChanged`` only when it actually
        crossed to a different status."""
        existing = await self._health_repo.find_by_component(organization_id, component=component)
        previous_status = existing.status if existing is not None else None

        if existing is not None:
            existing.status = status
            existing.checked_at = now
            existing.detail = detail
            check = await self._health_repo.update(existing)
        else:
            check = await self._health_repo.create(
                HealthCheck(
                    organization_id=organization_id,
                    component=component,
                    status=status,
                    checked_at=now,
                    detail=detail,
                )
            )

        if previous_status != status:
            await self._publish(
                PlatformHealthChangedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=organization_id,
                    payload={"component": component, "status": status.value},
                )
            )
        return check

    async def overall_status(self, organization_id: UUID) -> HealthCheckStatus:
        checks = await self._health_repo.list_all(organization_id)
        return aggregate_overall_status([check.status for check in checks])


__all__ = ["DiagnosticsService"]
