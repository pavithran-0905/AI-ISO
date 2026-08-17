"""Repository for health-gate verification results."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CheckResultStatus
from app.models.verification import VerificationResult

MAX_PAGE_SIZE = 500


class VerificationResultRepository(BaseRepository[VerificationResult]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, VerificationResult, tenant_scope=tenant_scope)

    async def list_for_job(self, upgrade_job_id: UUID) -> Sequence[VerificationResult]:
        stmt = self._base_select().where(VerificationResult.upgrade_job_id == upgrade_job_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_failed_for_job(self, upgrade_job_id: UUID) -> Sequence[VerificationResult]:
        stmt = self._base_select().where(
            VerificationResult.upgrade_job_id == upgrade_job_id,
            VerificationResult.status == CheckResultStatus.FAILED,
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[VerificationResult]:
        stmt = (
            self._base_select()
            .where(VerificationResult.organization_id == organization_id)
            .order_by(VerificationResult.verified_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "VerificationResultRepository"]
