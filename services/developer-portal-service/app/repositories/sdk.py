"""Repository for portal-initiated SDK downloads."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sdk import SdkDownload

MAX_PAGE_SIZE = 500


class SdkDownloadRepository(BaseRepository[SdkDownload]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, SdkDownload, tenant_scope=tenant_scope)

    async def list_for_user(
        self, organization_id: UUID, *, user_id: str, limit: int = 100
    ) -> Sequence[SdkDownload]:
        stmt = (
            self._base_select()
            .where(SdkDownload.organization_id == organization_id, SdkDownload.user_id == user_id)
            .order_by(SdkDownload.downloaded_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def count_since(self, organization_id: UUID, *, since: datetime) -> int:
        stmt = self._base_select().where(
            SdkDownload.organization_id == organization_id, SdkDownload.downloaded_at >= since
        )
        return len((await self._session.execute(stmt)).scalars().all())

    async def list_since(
        self, organization_id: UUID, *, since: datetime, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[SdkDownload]:
        stmt = (
            self._base_select()
            .where(
                SdkDownload.organization_id == organization_id, SdkDownload.downloaded_at >= since
            )
            .order_by(SdkDownload.downloaded_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(SdkDownload.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()

    async def exists_for_version(
        self, organization_id: UUID, *, language: str, version_label: str
    ) -> bool:
        stmt = self._base_select().where(
            SdkDownload.organization_id == organization_id,
            SdkDownload.language == language,
            SdkDownload.version_label == version_label,
        )
        return (await self._session.execute(stmt)).scalars().first() is not None


__all__ = ["MAX_PAGE_SIZE", "SdkDownloadRepository"]
