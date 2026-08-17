"""Repositories for plugin submissions and reviewer decisions."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PluginSubmissionStatus
from app.models.plugins import PluginReview, PluginSubmission

MAX_PAGE_SIZE = 500


class PluginSubmissionRepository(BaseRepository[PluginSubmission]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PluginSubmission, tenant_scope=tenant_scope)

    async def list_for_user(
        self, organization_id: UUID, *, user_id: str, limit: int = 100
    ) -> Sequence[PluginSubmission]:
        stmt = (
            self._base_select()
            .where(
                PluginSubmission.organization_id == organization_id,
                PluginSubmission.user_id == user_id,
            )
            .order_by(PluginSubmission.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        status: PluginSubmissionStatus | None = None,
        limit: int = 100,
    ) -> Sequence[PluginSubmission]:
        stmt = self._base_select().where(PluginSubmission.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(PluginSubmission.status == status)
        stmt = stmt.order_by(PluginSubmission.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_stale_validating(
        self, organization_id: UUID, *, before: datetime
    ) -> Sequence[PluginSubmission]:
        stmt = self._base_select().where(
            PluginSubmission.organization_id == organization_id,
            PluginSubmission.status == PluginSubmissionStatus.VALIDATING,
            PluginSubmission.updated_at < before,
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(PluginSubmission.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class PluginReviewRepository(BaseRepository[PluginReview]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PluginReview, tenant_scope=tenant_scope)

    async def list_for_submission(self, plugin_submission_id: UUID) -> Sequence[PluginReview]:
        stmt = (
            self._base_select()
            .where(PluginReview.plugin_submission_id == plugin_submission_id)
            .order_by(PluginReview.reviewed_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "PluginReviewRepository", "PluginSubmissionRepository"]
