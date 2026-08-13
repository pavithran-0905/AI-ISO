"""Repositories for the operational tables: statistics, reports, audit,
saved queries, dashboards, and retention policy.

The audit repository has no ``update`` -- it is append-only by contract,
and exposing one would let a caller edit the very record meant to survive
a caller's mistake.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuditAction, ReportStatus, SignalKind
from app.models.operations import (
    Dashboard,
    ObservabilityAudit,
    ObservabilityReport,
    ObservabilityStatistic,
    RetentionPolicy,
    SavedQuery,
)
from app.retention.engine import RetentionPolicySpec

MAX_PAGE_SIZE = 500


class ObservabilityStatisticRepository(BaseRepository[ObservabilityStatistic]):
    """Repository for :class:`ObservabilityStatistic` rollups."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ObservabilityStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, *, window_start: datetime, window_end: datetime
    ) -> ObservabilityStatistic | None:
        stmt = self._base_select().where(
            ObservabilityStatistic.organization_id == organization_id,
            ObservabilityStatistic.window_start == window_start,
            ObservabilityStatistic.window_end == window_end,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_range(
        self, organization_id: UUID, *, start: datetime, end: datetime
    ) -> Sequence[ObservabilityStatistic]:
        stmt = (
            self._base_select()
            .where(
                ObservabilityStatistic.organization_id == organization_id,
                ObservabilityStatistic.window_start >= start,
                ObservabilityStatistic.window_end <= end,
            )
            .order_by(ObservabilityStatistic.window_start)
        )
        return (await self._session.execute(stmt)).scalars().all()


class ObservabilityReportRepository(BaseRepository[ObservabilityReport]):
    """Repository for :class:`ObservabilityReport`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ObservabilityReport, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, report_id: UUID) -> ObservabilityReport:
        stmt = self._base_select().where(
            ObservabilityReport.id == report_id,
            ObservabilityReport.organization_id == organization_id,
        )
        found: ObservabilityReport | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(
                f"Report {report_id!s} was not found in organization {organization_id!s}."
            )
        return found

    async def list_recent(
        self, organization_id: UUID, *, status: ReportStatus | None = None, limit: int = 50
    ) -> Sequence[ObservabilityReport]:
        stmt = self._base_select().where(ObservabilityReport.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(ObservabilityReport.status == status)
        stmt = stmt.order_by(ObservabilityReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class ObservabilityAuditRepository(BaseRepository[ObservabilityAudit]):
    """Append-only repository for :class:`ObservabilityAudit`.

    Intentionally exposes no ``update`` or ``delete`` beyond the base
    soft-delete machinery: an audit trail that can be edited by the same
    path that writes it is not a trail, it is a log a caller trusts by
    mistake.
    """

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ObservabilityAudit, tenant_scope=tenant_scope)

    async def list_for_entity(
        self, organization_id: UUID, entity_type: str, entity_id: UUID
    ) -> Sequence[ObservabilityAudit]:
        stmt = (
            self._base_select()
            .where(
                ObservabilityAudit.organization_id == organization_id,
                ObservabilityAudit.entity_type == entity_type,
                ObservabilityAudit.entity_id == entity_id,
            )
            .order_by(ObservabilityAudit.occurred_at)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        since: datetime,
        action: AuditAction | None = None,
        actor_id: str | None = None,
        limit: int = 200,
    ) -> Sequence[ObservabilityAudit]:
        stmt = self._base_select().where(
            ObservabilityAudit.organization_id == organization_id,
            ObservabilityAudit.occurred_at >= since,
        )
        if action is not None:
            stmt = stmt.where(ObservabilityAudit.action == action)
        if actor_id is not None:
            stmt = stmt.where(ObservabilityAudit.actor_id == actor_id)
        stmt = stmt.order_by(ObservabilityAudit.occurred_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class SavedQueryRepository(BaseRepository[SavedQuery]):
    """Repository for :class:`SavedQuery`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SavedQuery, tenant_scope=tenant_scope)

    async def find_by_name(self, organization_id: UUID, name: str) -> SavedQuery | None:
        stmt = self._base_select().where(
            SavedQuery.organization_id == organization_id, SavedQuery.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_visible_to(
        self, organization_id: UUID, owner: str, *, signal_kind: SignalKind | None = None
    ) -> Sequence[SavedQuery]:
        """Queries the caller owns, plus every shared one.

        Shared and owned are combined in one query rather than two calls
        the API layer merges, so the ordering and pagination the caller
        sees is consistent regardless of how many of each exist.
        """
        stmt = self._base_select().where(
            SavedQuery.organization_id == organization_id,
            (SavedQuery.owner == owner) | (SavedQuery.is_shared.is_(True)),
        )
        if signal_kind is not None:
            stmt = stmt.where(SavedQuery.signal_kind == signal_kind)
        stmt = stmt.order_by(SavedQuery.name)
        return (await self._session.execute(stmt)).scalars().all()

    async def record_run(
        self, organization_id: UUID, query_id: UUID, *, duration_ms: float, at: datetime
    ) -> SavedQuery:
        """Update run statistics with a running mean, not a stored total.

        A stored total plus a stored count computed at read time would
        divide by whatever the count was *then*; keeping the mean itself
        current avoids a second, separately-updatable field that can drift
        from the count that produced it.
        """
        stmt = self._base_select().where(
            SavedQuery.id == query_id, SavedQuery.organization_id == organization_id
        )
        query: SavedQuery | None = (await self._session.execute(stmt)).scalars().first()
        if query is None:
            raise NotFoundError(
                f"Saved query {query_id!s} was not found in organization {organization_id!s}."
            )
        previous_mean = query.mean_duration_ms or 0.0
        query.mean_duration_ms = ((previous_mean * query.run_count) + duration_ms) / (
            query.run_count + 1
        )
        query.run_count += 1
        query.last_run_at = at
        await self._session.flush()
        return query


class DashboardRepository(BaseRepository[Dashboard]):
    """Repository for :class:`Dashboard`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Dashboard, tenant_scope=tenant_scope)

    async def find_by_slug(self, organization_id: UUID, slug: str) -> Dashboard | None:
        stmt = self._base_select().where(
            Dashboard.organization_id == organization_id, Dashboard.slug == slug
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_visible_to(self, organization_id: UUID, owner: str) -> Sequence[Dashboard]:
        stmt = (
            self._base_select()
            .where(
                Dashboard.organization_id == organization_id,
                (Dashboard.owner == owner) | (Dashboard.is_shared.is_(True)),
            )
            .order_by(Dashboard.is_default.desc(), Dashboard.name)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def record_view(
        self, organization_id: UUID, dashboard_id: UUID, *, at: datetime
    ) -> Dashboard:
        stmt = self._base_select().where(
            Dashboard.id == dashboard_id, Dashboard.organization_id == organization_id
        )
        dashboard: Dashboard | None = (await self._session.execute(stmt)).scalars().first()
        if dashboard is None:
            raise NotFoundError(
                f"Dashboard {dashboard_id!s} was not found in organization {organization_id!s}."
            )
        dashboard.view_count += 1
        dashboard.last_viewed_at = at
        await self._session.flush()
        return dashboard


class RetentionPolicyRepository(BaseRepository[RetentionPolicy]):
    """Repository for :class:`RetentionPolicy`.

    :meth:`as_spec` is the seam to :mod:`app.retention.engine`: the ORM
    row is mutable operational state (``last_applied_at``, a running
    delete count), while :class:`RetentionPolicySpec` is the frozen,
    validated value the pure engine reasons over. Converting explicitly
    here means the engine can never see a policy mid-edit.
    """

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, RetentionPolicy, tenant_scope=tenant_scope)

    async def find_for_scope(
        self, organization_id: UUID, signal_kind: SignalKind, environment: str
    ) -> RetentionPolicy | None:
        stmt = self._base_select().where(
            RetentionPolicy.organization_id == organization_id,
            RetentionPolicy.signal_kind == signal_kind,
            RetentionPolicy.environment == environment,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_enabled(self, organization_id: UUID) -> Sequence[RetentionPolicy]:
        stmt = self._base_select().where(
            RetentionPolicy.organization_id == organization_id,
            RetentionPolicy.is_enabled.is_(True),
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def record_sweep(
        self, organization_id: UUID, policy_id: UUID, *, applied_at: datetime, deleted_count: int
    ) -> RetentionPolicy:
        stmt = self._base_select().where(
            RetentionPolicy.id == policy_id, RetentionPolicy.organization_id == organization_id
        )
        policy: RetentionPolicy | None = (await self._session.execute(stmt)).scalars().first()
        if policy is None:
            raise NotFoundError(
                f"Retention policy {policy_id!s} was not found in organization "
                f"{organization_id!s}."
            )
        policy.last_applied_at = applied_at
        policy.last_deleted_count = deleted_count
        await self._session.flush()
        return policy

    @staticmethod
    def as_spec(policy: RetentionPolicy) -> RetentionPolicySpec:
        """Convert a persisted row into the pure engine's input type."""
        return RetentionPolicySpec(
            signal_kind=policy.signal_kind,
            environment=policy.environment,
            raw_days=policy.raw_days,
            downsampled_days=policy.downsampled_days,
            coarse_days=policy.coarse_days,
            downsample_interval=timedelta(seconds=policy.downsample_interval_seconds),
            is_enabled=policy.is_enabled,
        )


__all__ = [
    "MAX_PAGE_SIZE",
    "DashboardRepository",
    "ObservabilityAuditRepository",
    "ObservabilityReportRepository",
    "ObservabilityStatisticRepository",
    "RetentionPolicyRepository",
    "SavedQueryRepository",
]
