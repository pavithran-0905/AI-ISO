"""Repositories for licenses, keys, activations, entitlements, and
offline license files."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LicenseStatus
from app.models.licenses import (
    License,
    LicenseActivation,
    LicenseEntitlement,
    LicenseKey,
    OfflineLicense,
)

MAX_PAGE_SIZE = 500


class LicenseRepository(BaseRepository[License]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, License, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, license_id: UUID) -> License:
        stmt = self._base_select().where(
            License.id == license_id, License.organization_id == organization_id
        )
        found: License | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"License {license_id!s} was not found in this organization.")
        return found

    async def list_for_customer(self, customer_id: UUID) -> Sequence[License]:
        stmt = self._base_select().where(License.customer_id == customer_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, status: LicenseStatus | None = None, limit: int = 100
    ) -> Sequence[License]:
        stmt = self._base_select().where(License.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(License.status == status)
        stmt = stmt.order_by(License.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: LicenseStatus
    ) -> Sequence[License]:
        stmt = self._base_select().where(
            License.organization_id == organization_id, License.status == status
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(License.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class LicenseKeyRepository(BaseRepository[LicenseKey]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, LicenseKey, tenant_scope=tenant_scope)

    async def list_for_license(self, license_id: UUID) -> Sequence[LicenseKey]:
        stmt = self._base_select().where(LicenseKey.license_id == license_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def find_by_value(self, organization_id: UUID, *, key_value: str) -> LicenseKey | None:
        stmt = self._base_select().where(
            LicenseKey.organization_id == organization_id, LicenseKey.key_value == key_value
        )
        return (await self._session.execute(stmt)).scalars().first()


class LicenseActivationRepository(BaseRepository[LicenseActivation]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, LicenseActivation, tenant_scope=tenant_scope)

    async def list_for_license(self, license_id: UUID) -> Sequence[LicenseActivation]:
        stmt = self._base_select().where(LicenseActivation.license_id == license_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def count_active(self, license_id: UUID) -> int:
        stmt = self._base_select().where(
            LicenseActivation.license_id == license_id, LicenseActivation.is_enabled.is_(True)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return len(rows)


class LicenseEntitlementRepository(BaseRepository[LicenseEntitlement]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, LicenseEntitlement, tenant_scope=tenant_scope)

    async def list_for_license(self, license_id: UUID) -> Sequence[LicenseEntitlement]:
        stmt = self._base_select().where(LicenseEntitlement.license_id == license_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def find_by_key(self, license_id: UUID, *, feature_key: str) -> LicenseEntitlement | None:
        stmt = self._base_select().where(
            LicenseEntitlement.license_id == license_id,
            LicenseEntitlement.feature_key == feature_key,
        )
        return (await self._session.execute(stmt)).scalars().first()


class OfflineLicenseRepository(BaseRepository[OfflineLicense]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, OfflineLicense, tenant_scope=tenant_scope)

    async def list_for_license(self, license_id: UUID) -> Sequence[OfflineLicense]:
        stmt = self._base_select().where(OfflineLicense.license_id == license_id)
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "LicenseActivationRepository",
    "LicenseEntitlementRepository",
    "LicenseKeyRepository",
    "LicenseRepository",
    "OfflineLicenseRepository",
]
