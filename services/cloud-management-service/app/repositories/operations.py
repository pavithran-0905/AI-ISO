"""Repositories for the operational/governance tables: cost, budgets,
policies, compliance, drift, IaC, and the service catalog."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    CatalogItemStatus,
    CloudComplianceFramework,
    CloudPolicyStatus,
    CloudPolicyType,
    DriftStatus,
    IaCDeploymentStatus,
)
from app.models.operations import (
    CloudBudget,
    CloudCatalogItem,
    CloudCompliance,
    CloudCost,
    CloudDrift,
    CloudIaC,
    CloudPolicy,
)

MAX_PAGE_SIZE = 500


class CloudCostRepository(BaseRepository[CloudCost]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudCost, tenant_scope=tenant_scope)

    async def list_for_account(
        self, account_id: UUID, *, since: datetime, limit: int = 500
    ) -> Sequence[CloudCost]:
        stmt = (
            self._base_select()
            .where(CloudCost.account_id == account_id, CloudCost.period_start >= since)
            .order_by(CloudCost.period_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def total_for_account(self, account_id: UUID, *, since: datetime) -> float:
        stmt = select(CloudCost.amount).where(
            CloudCost.account_id == account_id, CloudCost.period_start >= since
        )
        amounts = (await self._session.execute(stmt)).scalars().all()
        return sum(amounts)


class CloudBudgetRepository(BaseRepository[CloudBudget]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudBudget, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[CloudBudget]:
        stmt = (
            self._base_select()
            .where(CloudBudget.organization_id == organization_id)
            .order_by(CloudBudget.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(CloudBudget.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class CloudPolicyRepository(BaseRepository[CloudPolicy]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudPolicy, tenant_scope=tenant_scope)

    async def list_active(
        self, organization_id: UUID, *, policy_type: CloudPolicyType | None = None
    ) -> Sequence[CloudPolicy]:
        stmt = self._base_select().where(
            CloudPolicy.organization_id == organization_id,
            CloudPolicy.status == CloudPolicyStatus.ACTIVE,
        )
        if policy_type is not None:
            stmt = stmt.where(CloudPolicy.policy_type == policy_type)
        return (await self._session.execute(stmt)).scalars().all()


class CloudComplianceRepository(BaseRepository[CloudCompliance]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudCompliance, tenant_scope=tenant_scope)

    async def latest_for_framework(
        self, account_id: UUID, *, framework: CloudComplianceFramework
    ) -> CloudCompliance | None:
        stmt = (
            self._base_select()
            .where(CloudCompliance.account_id == account_id, CloudCompliance.framework == framework)
            .order_by(CloudCompliance.assessed_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_account(self, account_id: UUID) -> Sequence[CloudCompliance]:
        stmt = self._base_select().where(CloudCompliance.account_id == account_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        framework: CloudComplianceFramework | None = None,
        limit: int = 100,
    ) -> Sequence[CloudCompliance]:
        stmt = self._base_select().where(CloudCompliance.organization_id == organization_id)
        if framework is not None:
            stmt = stmt.where(CloudCompliance.framework == framework)
        stmt = stmt.order_by(CloudCompliance.assessed_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(CloudCompliance.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class CloudDriftRepository(BaseRepository[CloudDrift]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudDrift, tenant_scope=tenant_scope)

    async def list_for_resource(self, resource_id: UUID) -> Sequence[CloudDrift]:
        stmt = self._base_select().where(CloudDrift.resource_id == resource_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_detected(self, organization_id: UUID) -> Sequence[CloudDrift]:
        stmt = self._base_select().where(
            CloudDrift.organization_id == organization_id, CloudDrift.status == DriftStatus.DETECTED
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(CloudDrift.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class CloudIaCRepository(BaseRepository[CloudIaC]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudIaC, tenant_scope=tenant_scope)

    async def list_for_resource(self, resource_id: UUID) -> Sequence[CloudIaC]:
        stmt = self._base_select().where(CloudIaC.resource_id == resource_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: IaCDeploymentStatus
    ) -> Sequence[CloudIaC]:
        stmt = self._base_select().where(
            CloudIaC.organization_id == organization_id, CloudIaC.status == status
        )
        return (await self._session.execute(stmt)).scalars().all()


class CloudCatalogRepository(BaseRepository[CloudCatalogItem]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CloudCatalogItem, tenant_scope=tenant_scope)

    async def list_approved(self, organization_id: UUID) -> Sequence[CloudCatalogItem]:
        stmt = self._base_select().where(
            CloudCatalogItem.organization_id == organization_id,
            CloudCatalogItem.status == CatalogItemStatus.APPROVED,
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[CloudCatalogItem]:
        stmt = (
            self._base_select()
            .where(CloudCatalogItem.organization_id == organization_id)
            .order_by(CloudCatalogItem.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "CloudBudgetRepository",
    "CloudCatalogRepository",
    "CloudComplianceRepository",
    "CloudCostRepository",
    "CloudDriftRepository",
    "CloudIaCRepository",
    "CloudPolicyRepository",
]
