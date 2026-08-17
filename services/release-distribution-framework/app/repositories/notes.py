"""Repository for release notes."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notes import ReleaseNote

MAX_PAGE_SIZE = 500


class ReleaseNoteRepository(BaseRepository[ReleaseNote]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ReleaseNote, tenant_scope=tenant_scope)

    async def list_for_version(self, release_version_id: UUID) -> Sequence[ReleaseNote]:
        stmt = self._base_select().where(ReleaseNote.release_version_id == release_version_id)
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["ReleaseNoteRepository"]
