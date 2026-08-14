"""Repositories for platform settings, system configuration, and
feature flags."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import FeatureFlagScope
from app.models.settings import FeatureFlag, PlatformSetting, SystemConfiguration

MAX_PAGE_SIZE = 500


class PlatformSettingRepository(BaseRepository[PlatformSetting]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PlatformSetting, tenant_scope=tenant_scope)

    async def find_by_key(self, organization_id: UUID, *, key: str) -> PlatformSetting | None:
        stmt = self._base_select().where(
            PlatformSetting.organization_id == organization_id, PlatformSetting.key == key
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_all(self, organization_id: UUID) -> Sequence[PlatformSetting]:
        stmt = self._base_select().where(PlatformSetting.organization_id == organization_id)
        return (await self._session.execute(stmt)).scalars().all()


class SystemConfigurationRepository(BaseRepository[SystemConfiguration]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SystemConfiguration, tenant_scope=tenant_scope)

    async def find_by_key(self, organization_id: UUID, *, key: str) -> SystemConfiguration | None:
        stmt = self._base_select().where(
            SystemConfiguration.organization_id == organization_id, SystemConfiguration.key == key
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_all(self, organization_id: UUID) -> Sequence[SystemConfiguration]:
        stmt = self._base_select().where(SystemConfiguration.organization_id == organization_id)
        return (await self._session.execute(stmt)).scalars().all()


class FeatureFlagRepository(BaseRepository[FeatureFlag]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, FeatureFlag, tenant_scope=tenant_scope)

    async def find_by_name(self, organization_id: UUID, *, name: str) -> FeatureFlag | None:
        stmt = self._base_select().where(
            FeatureFlag.organization_id == organization_id, FeatureFlag.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_recent(
        self, organization_id: UUID, *, scope: FeatureFlagScope | None = None, limit: int = 100
    ) -> Sequence[FeatureFlag]:
        stmt = self._base_select().where(FeatureFlag.organization_id == organization_id)
        if scope is not None:
            stmt = stmt.where(FeatureFlag.scope == scope)
        stmt = stmt.order_by(FeatureFlag.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "FeatureFlagRepository",
    "PlatformSettingRepository",
    "SystemConfigurationRepository",
]
