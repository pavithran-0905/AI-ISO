"""Repositories for CLI versions, plugins, profiles, sessions, usage,
and updates."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cli import CliPlugin, CliProfile, CliSession, CliUpdate, CliUsage, CliVersion
from app.models.enums import PluginStatus

MAX_PAGE_SIZE = 500


class CliVersionRepository(BaseRepository[CliVersion]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CliVersion, tenant_scope=tenant_scope)

    async def list_recent(self, organization_id: UUID, *, limit: int = 100) -> Sequence[CliVersion]:
        stmt = (
            self._base_select()
            .where(CliVersion.organization_id == organization_id)
            .order_by(CliVersion.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_with_planned_deprecation(self, organization_id: UUID) -> Sequence[CliVersion]:
        """Every still-enabled version that has a planned
        ``deprecated_at`` date set -- the ones the deprecation sweep
        needs to watch."""
        stmt = self._base_select().where(
            CliVersion.organization_id == organization_id,
            CliVersion.is_enabled.is_(True),
            CliVersion.deprecated_at.is_not(None),
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def latest_enabled(self, organization_id: UUID) -> CliVersion | None:
        stmt = (
            self._base_select()
            .where(CliVersion.organization_id == organization_id, CliVersion.is_enabled.is_(True))
            .order_by(CliVersion.created_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(CliVersion.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class CliPluginRepository(BaseRepository[CliPlugin]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CliPlugin, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, plugin_id: UUID) -> CliPlugin:
        stmt = self._base_select().where(
            CliPlugin.id == plugin_id, CliPlugin.organization_id == organization_id
        )
        found: CliPlugin | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"CLI plugin {plugin_id!s} was not found in this organization.")
        return found

    async def find_by_name(self, organization_id: UUID, *, name: str) -> CliPlugin | None:
        stmt = self._base_select().where(
            CliPlugin.organization_id == organization_id, CliPlugin.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_recent(
        self, organization_id: UUID, *, status: PluginStatus | None = None, limit: int = 100
    ) -> Sequence[CliPlugin]:
        stmt = self._base_select().where(CliPlugin.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(CliPlugin.status == status)
        stmt = stmt.order_by(CliPlugin.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: PluginStatus
    ) -> Sequence[CliPlugin]:
        stmt = self._base_select().where(
            CliPlugin.organization_id == organization_id, CliPlugin.status == status
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(CliPlugin.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class CliProfileRepository(BaseRepository[CliProfile]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CliProfile, tenant_scope=tenant_scope)

    async def list_all(self, organization_id: UUID) -> Sequence[CliProfile]:
        stmt = self._base_select().where(CliProfile.organization_id == organization_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_default_ids(self, organization_id: UUID) -> Sequence[UUID]:
        stmt = self._base_select().where(
            CliProfile.organization_id == organization_id, CliProfile.is_default.is_(True)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [row.id for row in rows]


class CliSessionRepository(BaseRepository[CliSession]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CliSession, tenant_scope=tenant_scope)

    async def list_for_profile(self, profile_id: UUID) -> Sequence[CliSession]:
        stmt = self._base_select().where(CliSession.profile_id == profile_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_enabled(self, organization_id: UUID) -> Sequence[CliSession]:
        stmt = self._base_select().where(
            CliSession.organization_id == organization_id, CliSession.is_enabled.is_(True)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(self, organization_id: UUID, *, limit: int = 100) -> Sequence[CliSession]:
        stmt = (
            self._base_select()
            .where(CliSession.organization_id == organization_id)
            .order_by(CliSession.started_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(CliSession.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class CliUsageRepository(BaseRepository[CliUsage]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CliUsage, tenant_scope=tenant_scope)

    async def count_since(self, organization_id: UUID, *, since: datetime) -> int:
        stmt = self._base_select().where(
            CliUsage.organization_id == organization_id, CliUsage.executed_at >= since
        )
        return len((await self._session.execute(stmt)).scalars().all())

    async def list_recent(self, organization_id: UUID, *, limit: int = 100) -> Sequence[CliUsage]:
        stmt = (
            self._base_select()
            .where(CliUsage.organization_id == organization_id)
            .order_by(CliUsage.executed_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(CliUsage.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class CliUpdateRepository(BaseRepository[CliUpdate]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CliUpdate, tenant_scope=tenant_scope)

    async def list_recent(self, organization_id: UUID, *, limit: int = 100) -> Sequence[CliUpdate]:
        stmt = (
            self._base_select()
            .where(CliUpdate.organization_id == organization_id)
            .order_by(CliUpdate.checked_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(CliUpdate.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "CliPluginRepository",
    "CliProfileRepository",
    "CliSessionRepository",
    "CliUpdateRepository",
    "CliUsageRepository",
    "CliVersionRepository",
]
