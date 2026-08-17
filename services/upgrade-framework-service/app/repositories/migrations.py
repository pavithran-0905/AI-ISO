"""Repositories for migration history, configuration migrations, and
plugin migrations."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UpgradeJobStatus
from app.models.migrations import ConfigurationMigration, MigrationHistory, PluginMigration

MAX_PAGE_SIZE = 500


class MigrationHistoryRepository(BaseRepository[MigrationHistory]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MigrationHistory, tenant_scope=tenant_scope)

    async def list_for_job(self, upgrade_job_id: UUID) -> Sequence[MigrationHistory]:
        stmt = self._base_select().where(MigrationHistory.upgrade_job_id == upgrade_job_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_running(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[MigrationHistory]:
        stmt = (
            self._base_select()
            .where(
                MigrationHistory.organization_id == organization_id,
                MigrationHistory.status == UpgradeJobStatus.RUNNING,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[MigrationHistory]:
        stmt = (
            self._base_select()
            .where(MigrationHistory.organization_id == organization_id)
            .order_by(MigrationHistory.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(MigrationHistory.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class ConfigurationMigrationRepository(BaseRepository[ConfigurationMigration]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ConfigurationMigration, tenant_scope=tenant_scope)

    async def list_for_job(self, upgrade_job_id: UUID) -> Sequence[ConfigurationMigration]:
        stmt = self._base_select().where(ConfigurationMigration.upgrade_job_id == upgrade_job_id)
        return (await self._session.execute(stmt)).scalars().all()


class PluginMigrationRepository(BaseRepository[PluginMigration]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PluginMigration, tenant_scope=tenant_scope)

    async def list_for_job(self, upgrade_job_id: UUID) -> Sequence[PluginMigration]:
        stmt = self._base_select().where(PluginMigration.upgrade_job_id == upgrade_job_id)
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "ConfigurationMigrationRepository",
    "MigrationHistoryRepository",
    "PluginMigrationRepository",
]
