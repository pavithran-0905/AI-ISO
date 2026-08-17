"""Repositories for deployment profiles, targets, inventory, jobs,
history, versions, artifacts, and the current status board."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import (
    DeploymentArtifact,
    DeploymentHistory,
    DeploymentInventory,
    DeploymentJob,
    DeploymentProfile,
    DeploymentStatusRecord,
    DeploymentTarget,
    DeploymentVersion,
)
from app.models.enums import DeploymentJobStatus, DeploymentJobType

MAX_PAGE_SIZE = 500


class DeploymentProfileRepository(BaseRepository[DeploymentProfile]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeploymentProfile, tenant_scope=tenant_scope)

    async def find_by_name(self, organization_id: UUID, *, name: str) -> DeploymentProfile | None:
        stmt = self._base_select().where(
            DeploymentProfile.organization_id == organization_id, DeploymentProfile.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_enabled(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[DeploymentProfile]:
        stmt = (
            self._base_select()
            .where(
                DeploymentProfile.organization_id == organization_id,
                DeploymentProfile.is_enabled.is_(True),
            )
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(DeploymentProfile.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class DeploymentTargetRepository(BaseRepository[DeploymentTarget]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeploymentTarget, tenant_scope=tenant_scope)

    async def list_for_profile(self, deployment_profile_id: UUID) -> Sequence[DeploymentTarget]:
        stmt = self._base_select().where(
            DeploymentTarget.deployment_profile_id == deployment_profile_id
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_organization(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[DeploymentTarget]:
        stmt = (
            self._base_select()
            .where(DeploymentTarget.organization_id == organization_id)
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class DeploymentInventoryRepository(BaseRepository[DeploymentInventory]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeploymentInventory, tenant_scope=tenant_scope)

    async def list_for_target(self, deployment_target_id: UUID) -> Sequence[DeploymentInventory]:
        stmt = self._base_select().where(
            DeploymentInventory.deployment_target_id == deployment_target_id
        )
        return (await self._session.execute(stmt)).scalars().all()


class DeploymentJobRepository(BaseRepository[DeploymentJob]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeploymentJob, tenant_scope=tenant_scope)

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        job_type: DeploymentJobType | None = None,
        status: DeploymentJobStatus | None = None,
        limit: int = 100,
    ) -> Sequence[DeploymentJob]:
        stmt = self._base_select().where(DeploymentJob.organization_id == organization_id)
        if job_type is not None:
            stmt = stmt.where(DeploymentJob.job_type == job_type)
        if status is not None:
            stmt = stmt.where(DeploymentJob.status == status)
        stmt = stmt.order_by(DeploymentJob.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_running(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[DeploymentJob]:
        stmt = (
            self._base_select()
            .where(
                DeploymentJob.organization_id == organization_id,
                DeploymentJob.status == DeploymentJobStatus.RUNNING,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(DeploymentJob.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class DeploymentHistoryRepository(BaseRepository[DeploymentHistory]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeploymentHistory, tenant_scope=tenant_scope)

    async def list_for_job(self, deployment_job_id: UUID) -> Sequence[DeploymentHistory]:
        stmt = (
            self._base_select()
            .where(DeploymentHistory.deployment_job_id == deployment_job_id)
            .order_by(DeploymentHistory.occurred_at.asc())
        )
        return (await self._session.execute(stmt)).scalars().all()


class DeploymentVersionRepository(BaseRepository[DeploymentVersion]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeploymentVersion, tenant_scope=tenant_scope)

    async def find_by_label(
        self, organization_id: UUID, *, version_label: str
    ) -> DeploymentVersion | None:
        stmt = self._base_select().where(
            DeploymentVersion.organization_id == organization_id,
            DeploymentVersion.version_label == version_label,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def find_current(self, organization_id: UUID) -> DeploymentVersion | None:
        stmt = self._base_select().where(
            DeploymentVersion.organization_id == organization_id,
            DeploymentVersion.is_current.is_(True),
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_latest(
        self, organization_id: UUID, *, limit: int = 1
    ) -> Sequence[DeploymentVersion]:
        stmt = (
            self._base_select()
            .where(DeploymentVersion.organization_id == organization_id)
            .order_by(DeploymentVersion.released_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[DeploymentVersion]:
        stmt = (
            self._base_select()
            .where(DeploymentVersion.organization_id == organization_id)
            .order_by(DeploymentVersion.released_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(DeploymentVersion.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class DeploymentArtifactRepository(BaseRepository[DeploymentArtifact]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeploymentArtifact, tenant_scope=tenant_scope)

    async def list_for_version(self, deployment_version_id: UUID) -> Sequence[DeploymentArtifact]:
        stmt = self._base_select().where(
            DeploymentArtifact.deployment_version_id == deployment_version_id
        )
        return (await self._session.execute(stmt)).scalars().all()


class DeploymentStatusRepository(BaseRepository[DeploymentStatusRecord]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DeploymentStatusRecord, tenant_scope=tenant_scope)

    async def find_for_target(
        self, organization_id: UUID, *, deployment_target_id: UUID
    ) -> DeploymentStatusRecord | None:
        stmt = self._base_select().where(
            DeploymentStatusRecord.organization_id == organization_id,
            DeploymentStatusRecord.deployment_target_id == deployment_target_id,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_organization(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[DeploymentStatusRecord]:
        stmt = (
            self._base_select()
            .where(DeploymentStatusRecord.organization_id == organization_id)
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "DeploymentArtifactRepository",
    "DeploymentHistoryRepository",
    "DeploymentInventoryRepository",
    "DeploymentJobRepository",
    "DeploymentProfileRepository",
    "DeploymentStatusRepository",
    "DeploymentTargetRepository",
    "DeploymentVersionRepository",
]
