"""Repositories for release channels and their published versions."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.releases import ReleaseChannel, ReleaseVersion

MAX_PAGE_SIZE = 500


class ReleaseChannelRepository(BaseRepository[ReleaseChannel]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ReleaseChannel, tenant_scope=tenant_scope)

    async def find_by_name(self, organization_id: UUID, *, name: str) -> ReleaseChannel | None:
        stmt = self._base_select().where(
            ReleaseChannel.organization_id == organization_id, ReleaseChannel.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_enabled(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ReleaseChannel]:
        stmt = (
            self._base_select()
            .where(
                ReleaseChannel.organization_id == organization_id,
                ReleaseChannel.is_enabled.is_(True),
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ReleaseChannel]:
        stmt = (
            self._base_select()
            .where(ReleaseChannel.organization_id == organization_id)
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


class ReleaseVersionRepository(BaseRepository[ReleaseVersion]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ReleaseVersion, tenant_scope=tenant_scope)

    async def find_current(
        self, organization_id: UUID, *, release_channel_id: UUID
    ) -> ReleaseVersion | None:
        stmt = self._base_select().where(
            ReleaseVersion.organization_id == organization_id,
            ReleaseVersion.release_channel_id == release_channel_id,
            ReleaseVersion.is_current.is_(True),
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_latest(
        self, organization_id: UUID, *, release_channel_id: UUID, limit: int = 1
    ) -> Sequence[ReleaseVersion]:
        stmt = (
            self._base_select()
            .where(
                ReleaseVersion.organization_id == organization_id,
                ReleaseVersion.release_channel_id == release_channel_id,
            )
            .order_by(ReleaseVersion.released_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_channel(
        self, release_channel_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ReleaseVersion]:
        stmt = (
            self._base_select()
            .where(ReleaseVersion.release_channel_id == release_channel_id)
            .order_by(ReleaseVersion.released_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ReleaseVersion]:
        stmt = (
            self._base_select()
            .where(ReleaseVersion.organization_id == organization_id)
            .order_by(ReleaseVersion.released_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(ReleaseVersion.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "ReleaseChannelRepository", "ReleaseVersionRepository"]
