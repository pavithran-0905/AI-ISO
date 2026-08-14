"""Repositories for organizations, tenants, and every per-tenant
administrative table."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TenantStatus
from app.models.tenants import (
    Organization,
    Tenant,
    TenantHealth,
    TenantLimit,
    TenantProvisioning,
    TenantSetting,
    TenantUsage,
)

MAX_PAGE_SIZE = 500


class OrganizationRepository(BaseRepository[Organization]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Organization, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, entity_id: UUID) -> Organization:
        stmt = self._base_select().where(
            Organization.id == entity_id, Organization.organization_id == organization_id
        )
        found: Organization | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"Organization {entity_id!s} was not found in this organization.")
        return found

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[Organization]:
        stmt = (
            self._base_select()
            .where(Organization.organization_id == organization_id)
            .order_by(Organization.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class TenantRepository(BaseRepository[Tenant]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Tenant, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, tenant_id: UUID) -> Tenant:
        stmt = self._base_select().where(
            Tenant.id == tenant_id, Tenant.organization_id == organization_id
        )
        found: Tenant | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"Tenant {tenant_id!s} was not found in this organization.")
        return found

    async def list_for_organization_ref(self, organization_ref_id: UUID) -> Sequence[Tenant]:
        stmt = self._base_select().where(Tenant.organization_ref_id == organization_ref_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, status: TenantStatus | None = None, limit: int = 100
    ) -> Sequence[Tenant]:
        stmt = self._base_select().where(Tenant.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(Tenant.status == status)
        stmt = stmt.order_by(Tenant.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: TenantStatus
    ) -> Sequence[Tenant]:
        stmt = self._base_select().where(
            Tenant.organization_id == organization_id, Tenant.status == status
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(Tenant.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class TenantSettingRepository(BaseRepository[TenantSetting]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, TenantSetting, tenant_scope=tenant_scope)

    async def list_for_tenant(self, tenant_id: UUID) -> Sequence[TenantSetting]:
        stmt = self._base_select().where(TenantSetting.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def find_by_key(self, tenant_id: UUID, *, key: str) -> TenantSetting | None:
        stmt = self._base_select().where(
            TenantSetting.tenant_id == tenant_id, TenantSetting.key == key
        )
        return (await self._session.execute(stmt)).scalars().first()


class TenantLimitRepository(BaseRepository[TenantLimit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, TenantLimit, tenant_scope=tenant_scope)

    async def list_for_tenant(self, tenant_id: UUID) -> Sequence[TenantLimit]:
        stmt = self._base_select().where(TenantLimit.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def find_by_metric(self, tenant_id: UUID, *, metric_key: str) -> TenantLimit | None:
        stmt = self._base_select().where(
            TenantLimit.tenant_id == tenant_id, TenantLimit.metric_key == metric_key
        )
        return (await self._session.execute(stmt)).scalars().first()


class TenantUsageRepository(BaseRepository[TenantUsage]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, TenantUsage, tenant_scope=tenant_scope)

    async def list_for_tenant(
        self, tenant_id: UUID, *, metric_key: str | None = None
    ) -> Sequence[TenantUsage]:
        stmt = self._base_select().where(TenantUsage.tenant_id == tenant_id)
        if metric_key is not None:
            stmt = stmt.where(TenantUsage.metric_key == metric_key)
        return (await self._session.execute(stmt)).scalars().all()

    async def latest_for_metric(self, tenant_id: UUID, *, metric_key: str) -> TenantUsage | None:
        stmt = (
            self._base_select()
            .where(TenantUsage.tenant_id == tenant_id, TenantUsage.metric_key == metric_key)
            .order_by(TenantUsage.recorded_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()


class TenantHealthRepository(BaseRepository[TenantHealth]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, TenantHealth, tenant_scope=tenant_scope)

    async def latest_for_tenant(self, tenant_id: UUID) -> TenantHealth | None:
        stmt = (
            self._base_select()
            .where(TenantHealth.tenant_id == tenant_id)
            .order_by(TenantHealth.checked_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_tenant(self, tenant_id: UUID) -> Sequence[TenantHealth]:
        stmt = self._base_select().where(TenantHealth.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()


class TenantProvisioningRepository(BaseRepository[TenantProvisioning]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, TenantProvisioning, tenant_scope=tenant_scope)

    async def list_for_tenant(self, tenant_id: UUID) -> Sequence[TenantProvisioning]:
        stmt = self._base_select().where(TenantProvisioning.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "OrganizationRepository",
    "TenantHealthRepository",
    "TenantLimitRepository",
    "TenantProvisioningRepository",
    "TenantRepository",
    "TenantSettingRepository",
    "TenantUsageRepository",
]
