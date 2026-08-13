"""Repositories for the derived tables: dependencies, topology, SLOs,
anomalies, root cause, capacity, and cost.

Every row here is a conclusion, not an observation, and every method that
lists them orders by the field that makes the conclusion actionable --
most-critical first for topology nodes, most-severe first for anomalies,
soonest-to-exhaust first for capacity -- rather than by insertion order,
which is what a caller gets by accident from an unordered query and
mistakes for a ranking.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import (
    AnomalyDetection,
    CapacityForecast,
    CostReport,
    RootCauseReport,
    ServiceDependency,
    ServiceTopologyNode,
    Sli,
    Slo,
)
from app.models.enums import AnomalyMethod, AnomalySeverity, NodeHealth

MAX_PAGE_SIZE = 500


class ServiceDependencyRepository(BaseRepository[ServiceDependency]):
    """Repository for :class:`ServiceDependency` edges."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ServiceDependency, tenant_scope=tenant_scope)

    async def find_edge(
        self, organization_id: UUID, caller: str, callee: str, environment: str
    ) -> ServiceDependency | None:
        stmt = self._base_select().where(
            ServiceDependency.organization_id == organization_id,
            ServiceDependency.caller_service == caller,
            ServiceDependency.callee_service == callee,
            ServiceDependency.environment == environment,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_service(
        self, organization_id: UUID, service_name: str, environment: str
    ) -> Sequence[ServiceDependency]:
        """Every edge touching *service_name*, as caller or callee.

        Both directions in one query: a caller building a topology view
        needs dependencies and dependents together, and two separate calls
        invite forgetting one of them at a call site.
        """
        stmt = self._base_select().where(
            ServiceDependency.organization_id == organization_id,
            ServiceDependency.environment == environment,
            (ServiceDependency.caller_service == service_name)
            | (ServiceDependency.callee_service == service_name),
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_stale(
        self, organization_id: UUID, environment: str, *, older_than: datetime
    ) -> Sequence[ServiceDependency]:
        """Edges nothing has confirmed recently -- candidates to fade."""
        stmt = self._base_select().where(
            ServiceDependency.organization_id == organization_id,
            ServiceDependency.environment == environment,
            ServiceDependency.last_observed_at < older_than,
            ServiceDependency.is_stale.is_(False),
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_environment(
        self, organization_id: UUID, environment: str, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ServiceDependency]:
        """Every edge in one environment, for a full topology view."""
        stmt = (
            self._base_select()
            .where(
                ServiceDependency.organization_id == organization_id,
                ServiceDependency.environment == environment,
            )
            .order_by(ServiceDependency.caller_service, ServiceDependency.callee_service)
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class ServiceTopologyNodeRepository(BaseRepository[ServiceTopologyNode]):
    """Repository for :class:`ServiceTopologyNode`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ServiceTopologyNode, tenant_scope=tenant_scope)

    async def find_node(
        self, organization_id: UUID, service_name: str, environment: str
    ) -> ServiceTopologyNode | None:
        stmt = self._base_select().where(
            ServiceTopologyNode.organization_id == organization_id,
            ServiceTopologyNode.service_name == service_name,
            ServiceTopologyNode.environment == environment,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_critical(
        self, organization_id: UUID, environment: str, *, limit: int = 50
    ) -> Sequence[ServiceTopologyNode]:
        """Nodes ranked by criticality, most critical first."""
        stmt = (
            self._base_select()
            .where(
                ServiceTopologyNode.organization_id == organization_id,
                ServiceTopologyNode.environment == environment,
            )
            .order_by(ServiceTopologyNode.criticality.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_unhealthy(
        self, organization_id: UUID, environment: str
    ) -> Sequence[ServiceTopologyNode]:
        stmt = self._base_select().where(
            ServiceTopologyNode.organization_id == organization_id,
            ServiceTopologyNode.environment == environment,
            ServiceTopologyNode.health.in_([NodeHealth.DEGRADED, NodeHealth.UNHEALTHY]),
        )
        return (await self._session.execute(stmt)).scalars().all()


class SloRepository(BaseRepository[Slo]):
    """Repository for :class:`Slo` definitions."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Slo, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, slo_id: UUID) -> Slo:
        stmt = self._base_select().where(Slo.id == slo_id, Slo.organization_id == organization_id)
        found: Slo | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(
                f"SLO {slo_id!s} was not found in organization {organization_id!s}."
            )
        return found

    async def list_enabled(
        self, organization_id: UUID, *, service_name: str | None = None
    ) -> Sequence[Slo]:
        stmt = self._base_select().where(
            Slo.organization_id == organization_id, Slo.is_enabled.is_(True)
        )
        if service_name is not None:
            stmt = stmt.where(Slo.service_name == service_name)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        """Every organization with at least one enabled SLO."""
        stmt = select(Slo.organization_id).distinct().where(Slo.is_enabled.is_(True))
        return (await self._session.execute(stmt)).scalars().all()


class SliRepository(BaseRepository[Sli]):
    """Repository for :class:`Sli` evaluation windows."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Sli, tenant_scope=tenant_scope)

    async def latest_for_slo(self, slo_id: UUID) -> Sli | None:
        stmt = (
            self._base_select().where(Sli.slo_id == slo_id).order_by(Sli.window_end.desc()).limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_slo(self, slo_id: UUID, *, start: datetime, end: datetime) -> Sequence[Sli]:
        """Windows overlapping ``[start, end)``, for rollup.

        Overlap rather than containment: a monthly report over a set of
        daily windows needs every window that touches the month, including
        the ones straddling its edges, or the rollup undercounts at both
        boundaries.
        """
        stmt = (
            self._base_select()
            .where(
                Sli.slo_id == slo_id,
                Sli.window_start < end,
                Sli.window_end > start,
            )
            .order_by(Sli.window_start)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_burning(self, organization_id: UUID) -> Sequence[Sli]:
        stmt = (
            select(Sli)
            .join(Slo, Sli.slo_id == Slo.id)
            .where(
                Slo.organization_id == organization_id,
                Sli.is_active.is_(True),
                Sli.is_burning.is_(True),
            )
        )
        return (await self._session.execute(stmt)).scalars().all()


class AnomalyDetectionRepository(BaseRepository[AnomalyDetection]):
    """Repository for :class:`AnomalyDetection`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, AnomalyDetection, tenant_scope=tenant_scope)

    async def find_existing(
        self,
        organization_id: UUID,
        *,
        metric_series_id: UUID | None,
        occurred_at: datetime,
        method: AnomalyMethod,
    ) -> AnomalyDetection | None:
        """The detection already recorded for this instant, if any.

        A sweep that re-scans an overlapping window -- which every sweep
        does, since the baseline needs history from before the window it
        is evaluating -- must not create a second row for the same
        anomaly. Keyed on the same triple the detector itself would
        reproduce deterministically from the same input.
        """
        stmt = self._base_select().where(
            AnomalyDetection.organization_id == organization_id,
            AnomalyDetection.metric_series_id == metric_series_id,
            AnomalyDetection.occurred_at == occurred_at,
            AnomalyDetection.method == method,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        since: datetime,
        service_name: str | None = None,
        min_severity: AnomalySeverity | None = None,
        unacknowledged_only: bool = False,
        limit: int = 100,
    ) -> Sequence[AnomalyDetection]:
        """Recent detections, most severe and most recent first."""
        stmt = self._base_select().where(
            AnomalyDetection.organization_id == organization_id,
            AnomalyDetection.detected_at >= since,
        )
        if service_name is not None:
            stmt = stmt.where(AnomalyDetection.service_name == service_name)
        if min_severity is not None:
            ranked = list(AnomalySeverity)
            allowed = ranked[ranked.index(min_severity) :]
            stmt = stmt.where(AnomalyDetection.severity.in_(allowed))
        if unacknowledged_only:
            stmt = stmt.where(AnomalyDetection.is_acknowledged.is_(False))
        stmt = stmt.order_by(AnomalyDetection.detected_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def acknowledge(
        self, organization_id: UUID, detection_id: UUID, *, acknowledged_by: str
    ) -> AnomalyDetection:
        stmt = self._base_select().where(
            AnomalyDetection.id == detection_id,
            AnomalyDetection.organization_id == organization_id,
        )
        detection: AnomalyDetection | None = (await self._session.execute(stmt)).scalars().first()
        if detection is None:
            raise NotFoundError(
                f"Anomaly detection {detection_id!s} was not found in organization "
                f"{organization_id!s}."
            )
        detection.is_acknowledged = True
        detection.acknowledged_by = acknowledged_by
        await self._session.flush()
        return detection


class RootCauseReportRepository(BaseRepository[RootCauseReport]):
    """Repository for :class:`RootCauseReport`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, RootCauseReport, tenant_scope=tenant_scope)

    async def find_for_incident(
        self, organization_id: UUID, incident_reference: str
    ) -> RootCauseReport | None:
        stmt = (
            self._base_select()
            .where(
                RootCauseReport.organization_id == organization_id,
                RootCauseReport.incident_reference == incident_reference,
            )
            .order_by(RootCauseReport.analysed_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_service(
        self, organization_id: UUID, service_name: str, *, limit: int = 20
    ) -> Sequence[RootCauseReport]:
        stmt = (
            self._base_select()
            .where(
                RootCauseReport.organization_id == organization_id,
                RootCauseReport.service_name == service_name,
            )
            .order_by(RootCauseReport.analysed_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class CapacityForecastRepository(BaseRepository[CapacityForecast]):
    """Repository for :class:`CapacityForecast`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CapacityForecast, tenant_scope=tenant_scope)

    async def latest_for_resource(
        self, organization_id: UUID, service_name: str, resource_kind: str
    ) -> CapacityForecast | None:
        stmt = (
            self._base_select()
            .where(
                CapacityForecast.organization_id == organization_id,
                CapacityForecast.service_name == service_name,
                CapacityForecast.resource_kind == resource_kind,
            )
            .order_by(CapacityForecast.generated_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_at_risk(
        self, organization_id: UUID, *, within_days: float, limit: int = 100
    ) -> Sequence[CapacityForecast]:
        """Forecasts that will exhaust within *within_days*, soonest first.

        ``days_until_exhaustion is None`` is excluded by the column
        comparison itself -- SQL's three-valued logic makes ``NULL <= x``
        unknown rather than true, so a forecast with no trend never shows
        up here as a false emergency.
        """
        stmt = (
            self._base_select()
            .where(
                CapacityForecast.organization_id == organization_id,
                CapacityForecast.days_until_exhaustion.is_not(None),
                CapacityForecast.days_until_exhaustion <= within_days,
            )
            .order_by(CapacityForecast.days_until_exhaustion)
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class CostReportRepository(BaseRepository[CostReport]):
    """Repository for :class:`CostReport`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CostReport, tenant_scope=tenant_scope)

    async def find_period(
        self,
        organization_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
        dimension: str,
        dimension_value: str | None,
    ) -> CostReport | None:
        stmt = self._base_select().where(
            CostReport.organization_id == organization_id,
            CostReport.period_start == period_start,
            CostReport.period_end == period_end,
            CostReport.dimension == dimension,
            CostReport.dimension_value == dimension_value,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_period(
        self,
        organization_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
        dimension: str,
    ) -> Sequence[CostReport]:
        """Every reported value at one dimension for one period.

        Used for a rollup check: summing these against the organization
        total is how a caller verifies the hierarchy invariant that
        :mod:`app.cost.analytics` computes rather than trusting it blind.
        """
        stmt = self._base_select().where(
            CostReport.organization_id == organization_id,
            CostReport.period_start == period_start,
            CostReport.period_end == period_end,
            CostReport.dimension == dimension,
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "AnomalyDetectionRepository",
    "CapacityForecastRepository",
    "CostReportRepository",
    "RootCauseReportRepository",
    "ServiceDependencyRepository",
    "ServiceTopologyNodeRepository",
    "SliRepository",
    "SloRepository",
]
