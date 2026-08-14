"""Repositories for workload placement, the cluster event timeline,
rolled-up statistics, generated reports, and the immutable audit trail."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReportStatus, WorkloadPlacementStatus
from app.models.reporting import (
    ClusterAudit,
    ClusterEvent,
    ClusterReport,
    ClusterStatistic,
    ClusterWorkload,
)

MAX_PAGE_SIZE = 500


class ClusterWorkloadRepository(BaseRepository[ClusterWorkload]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ClusterWorkload, tenant_scope=tenant_scope)

    async def list_for_cluster(self, cluster_id: UUID) -> Sequence[ClusterWorkload]:
        stmt = self._base_select().where(ClusterWorkload.cluster_id == cluster_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_pending(self, organization_id: UUID) -> Sequence[ClusterWorkload]:
        stmt = self._base_select().where(
            ClusterWorkload.organization_id == organization_id,
            ClusterWorkload.placement_status == WorkloadPlacementStatus.PENDING,
        )
        return (await self._session.execute(stmt)).scalars().all()


class ClusterEventRepository(BaseRepository[ClusterEvent]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ClusterEvent, tenant_scope=tenant_scope)

    async def list_recent(self, cluster_id: UUID, *, limit: int = 100) -> Sequence[ClusterEvent]:
        stmt = (
            self._base_select()
            .where(ClusterEvent.cluster_id == cluster_id)
            .order_by(ClusterEvent.occurred_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class ClusterStatisticRepository(BaseRepository[ClusterStatistic]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ClusterStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, *, window_start: datetime, window_end: datetime
    ) -> ClusterStatistic | None:
        stmt = self._base_select().where(
            ClusterStatistic.organization_id == organization_id,
            ClusterStatistic.window_start == window_start,
            ClusterStatistic.window_end == window_end,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_range(
        self, organization_id: UUID, *, start: datetime, end: datetime
    ) -> Sequence[ClusterStatistic]:
        stmt = (
            self._base_select()
            .where(
                ClusterStatistic.organization_id == organization_id,
                ClusterStatistic.window_start >= start,
                ClusterStatistic.window_end <= end,
            )
            .order_by(ClusterStatistic.window_start)
        )
        return (await self._session.execute(stmt)).scalars().all()


class ClusterReportRepository(BaseRepository[ClusterReport]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ClusterReport, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, report_id: UUID) -> ClusterReport:
        stmt = self._base_select().where(
            ClusterReport.id == report_id, ClusterReport.organization_id == organization_id
        )
        found: ClusterReport | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"Report {report_id!s} was not found in this organization.")
        return found

    async def list_recent(
        self, organization_id: UUID, *, status: ReportStatus | None = None, limit: int = 50
    ) -> Sequence[ClusterReport]:
        stmt = self._base_select().where(ClusterReport.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(ClusterReport.status == status)
        stmt = stmt.order_by(ClusterReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


class ClusterAuditRepository(BaseRepository[ClusterAudit]):
    """Append-only repository for :class:`ClusterAudit`.

    Intentionally exposes no ``update`` beyond the base soft-delete
    machinery -- an audit trail that can be edited by the same path that
    writes it is not a trail.
    """

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ClusterAudit, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, since: datetime, limit: int = 200
    ) -> Sequence[ClusterAudit]:
        stmt = (
            self._base_select()
            .where(
                ClusterAudit.organization_id == organization_id, ClusterAudit.occurred_at >= since
            )
            .order_by(ClusterAudit.occurred_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "ClusterAuditRepository",
    "ClusterEventRepository",
    "ClusterReportRepository",
    "ClusterStatisticRepository",
    "ClusterWorkloadRepository",
]
