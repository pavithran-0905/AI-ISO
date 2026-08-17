"""Repositories for installation sessions and their log lines."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InstallationSessionStatus
from app.models.installation import InstallationLog, InstallationSession

MAX_PAGE_SIZE = 500


class InstallationSessionRepository(BaseRepository[InstallationSession]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, InstallationSession, tenant_scope=tenant_scope)

    async def list_running(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[InstallationSession]:
        stmt = (
            self._base_select()
            .where(
                InstallationSession.organization_id == organization_id,
                InstallationSession.status == InstallationSessionStatus.RUNNING,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[InstallationSession]:
        stmt = (
            self._base_select()
            .where(InstallationSession.organization_id == organization_id)
            .order_by(InstallationSession.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(InstallationSession.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class InstallationLogRepository(BaseRepository[InstallationLog]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, InstallationLog, tenant_scope=tenant_scope)

    async def list_for_session(self, installation_session_id: UUID) -> Sequence[InstallationLog]:
        stmt = (
            self._base_select()
            .where(InstallationLog.installation_session_id == installation_session_id)
            .order_by(InstallationLog.logged_at.asc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "InstallationLogRepository", "InstallationSessionRepository"]
