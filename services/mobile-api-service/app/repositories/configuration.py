"""Repositories for app version policy and remote configuration."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuration import MobileAppVersion, MobileConfiguration
from app.models.enums import MobilePlatform

MAX_PAGE_SIZE = 500


class MobileAppVersionRepository(BaseRepository[MobileAppVersion]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MobileAppVersion, tenant_scope=tenant_scope)

    async def find_latest_for_platform(
        self, organization_id: UUID, *, platform: MobilePlatform
    ) -> MobileAppVersion | None:
        stmt = (
            self._base_select()
            .where(
                MobileAppVersion.organization_id == organization_id,
                MobileAppVersion.platform == platform,
            )
            .order_by(MobileAppVersion.released_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[MobileAppVersion]:
        stmt = (
            self._base_select()
            .where(MobileAppVersion.organization_id == organization_id)
            .order_by(MobileAppVersion.released_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(MobileAppVersion.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class MobileConfigurationRepository(BaseRepository[MobileConfiguration]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MobileConfiguration, tenant_scope=tenant_scope)

    async def list_for_environment(
        self, organization_id: UUID, *, environment: str
    ) -> Sequence[MobileConfiguration]:
        stmt = self._base_select().where(
            MobileConfiguration.organization_id == organization_id,
            MobileConfiguration.environment == environment,
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "MobileAppVersionRepository", "MobileConfigurationRepository"]
