"""Repository for configuration wizard profiles."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuration import ConfigurationProfile
from app.models.enums import ConfigurationSection

MAX_PAGE_SIZE = 500


class ConfigurationProfileRepository(BaseRepository[ConfigurationProfile]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ConfigurationProfile, tenant_scope=tenant_scope)

    async def find_by_name(
        self, organization_id: UUID, *, name: str
    ) -> ConfigurationProfile | None:
        stmt = self._base_select().where(
            ConfigurationProfile.organization_id == organization_id,
            ConfigurationProfile.name == name,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def find_by_section(
        self, organization_id: UUID, *, section: ConfigurationSection
    ) -> ConfigurationProfile | None:
        stmt = self._base_select().where(
            ConfigurationProfile.organization_id == organization_id,
            ConfigurationProfile.section == section,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ConfigurationProfile]:
        stmt = (
            self._base_select()
            .where(ConfigurationProfile.organization_id == organization_id)
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "ConfigurationProfileRepository"]
