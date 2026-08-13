"""Repositories for the backup-side tables: targets, schedules, jobs,
snapshots, archives, retention policy, and verification."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backup import (
    BackupArchive,
    BackupJob,
    BackupRetention,
    BackupSchedule,
    BackupSnapshot,
    BackupTarget,
    BackupVerification,
)
from app.models.enums import BackupJobStatus, BackupTargetKind

MAX_PAGE_SIZE = 500


class BackupTargetRepository(BaseRepository[BackupTarget]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BackupTarget, tenant_scope=tenant_scope)

    async def find_by_name(self, organization_id: UUID, name: str) -> BackupTarget | None:
        stmt = self._base_select().where(
            BackupTarget.organization_id == organization_id, BackupTarget.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def require_in_org(self, organization_id: UUID, target_id: UUID) -> BackupTarget:
        stmt = self._base_select().where(
            BackupTarget.id == target_id, BackupTarget.organization_id == organization_id
        )
        found: BackupTarget | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"Backup target {target_id!s} was not found in this organization.")
        return found

    async def list_enabled(self, organization_id: UUID) -> Sequence[BackupTarget]:
        stmt = self._base_select().where(
            BackupTarget.organization_id == organization_id, BackupTarget.is_enabled.is_(True)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(BackupTarget.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class BackupScheduleRepository(BaseRepository[BackupSchedule]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BackupSchedule, tenant_scope=tenant_scope)

    async def list_for_target(self, target_id: UUID) -> Sequence[BackupSchedule]:
        stmt = self._base_select().where(BackupSchedule.target_id == target_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_due(self, organization_id: UUID, *, now: datetime) -> Sequence[BackupSchedule]:
        """Enabled schedules whose ``next_run_at`` has arrived."""
        stmt = self._base_select().where(
            BackupSchedule.organization_id == organization_id,
            BackupSchedule.is_enabled.is_(True),
            BackupSchedule.next_run_at.is_not(None),
            BackupSchedule.next_run_at <= now,
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_enabled(self, organization_id: UUID) -> Sequence[BackupSchedule]:
        stmt = self._base_select().where(
            BackupSchedule.organization_id == organization_id, BackupSchedule.is_enabled.is_(True)
        )
        return (await self._session.execute(stmt)).scalars().all()


class BackupJobRepository(BaseRepository[BackupJob]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BackupJob, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, job_id: UUID) -> BackupJob:
        stmt = self._base_select().where(
            BackupJob.id == job_id, BackupJob.organization_id == organization_id
        )
        found: BackupJob | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"Backup job {job_id!s} was not found in this organization.")
        return found

    async def list_recent(
        self,
        organization_id: UUID,
        *,
        target_id: UUID | None = None,
        status: BackupJobStatus | None = None,
        limit: int = 100,
    ) -> Sequence[BackupJob]:
        stmt = self._base_select().where(BackupJob.organization_id == organization_id)
        if target_id is not None:
            stmt = stmt.where(BackupJob.target_id == target_id)
        if status is not None:
            stmt = stmt.where(BackupJob.status == status)
        stmt = stmt.order_by(BackupJob.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_chain_for_target(
        self, target_id: UUID, *, limit: int = 1000
    ) -> Sequence[BackupJob]:
        """Every job for one target, for chain validation.

        Unbounded by the usual page size within reason: chain validation
        needs to see the whole chain a target job might reference, and
        splitting it across pages would let a validation see a partial
        chain and draw a wrong conclusion from it.
        """
        stmt = (
            self._base_select()
            .where(BackupJob.target_id == target_id)
            .order_by(BackupJob.created_at)
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_running(self, organization_id: UUID) -> Sequence[BackupJob]:
        stmt = self._base_select().where(
            BackupJob.organization_id == organization_id,
            BackupJob.status.in_([BackupJobStatus.PENDING, BackupJobStatus.RUNNING]),
        )
        return (await self._session.execute(stmt)).scalars().all()


class BackupSnapshotRepository(BaseRepository[BackupSnapshot]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BackupSnapshot, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, target_id: UUID | None = None, limit: int = 100
    ) -> Sequence[BackupSnapshot]:
        stmt = self._base_select().where(BackupSnapshot.organization_id == organization_id)
        if target_id is not None:
            stmt = stmt.where(BackupSnapshot.target_id == target_id)
        stmt = stmt.order_by(BackupSnapshot.created_at_source.desc()).limit(
            min(limit, MAX_PAGE_SIZE)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_target(self, target_id: UUID) -> Sequence[BackupSnapshot]:
        stmt = self._base_select().where(BackupSnapshot.target_id == target_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(BackupSnapshot.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class BackupArchiveRepository(BaseRepository[BackupArchive]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BackupArchive, tenant_scope=tenant_scope)

    async def list_for_organization(self, organization_id: UUID) -> Sequence[BackupArchive]:
        stmt = self._base_select().where(BackupArchive.organization_id == organization_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_target_kind(
        self, organization_id: UUID, target_kind: BackupTargetKind | None
    ) -> Sequence[BackupArchive]:
        """Archives whose job's target has *target_kind* --
        ``BackupArchive`` itself carries no target reference, so this
        joins through :class:`~app.models.backup.BackupJob` to
        :class:`~app.models.backup.BackupTarget`. ``target_kind=None``
        matches the retention catch-all scope and returns every archive
        for the organization.
        """
        if target_kind is None:
            return await self.list_for_organization(organization_id)
        stmt = (
            self._base_select()
            .join(BackupJob, BackupArchive.job_id == BackupJob.id)
            .join(BackupTarget, BackupJob.target_id == BackupTarget.id)
            .where(
                BackupArchive.organization_id == organization_id,
                BackupTarget.target_kind == target_kind,
            )
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(BackupArchive.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class BackupRetentionRepository(BaseRepository[BackupRetention]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BackupRetention, tenant_scope=tenant_scope)

    async def list_enabled(self, organization_id: UUID) -> Sequence[BackupRetention]:
        stmt = self._base_select().where(
            BackupRetention.organization_id == organization_id, BackupRetention.is_enabled.is_(True)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def find_for_scope(
        self, organization_id: UUID, target_kind: BackupTargetKind | None, environment: str
    ) -> BackupRetention | None:
        stmt = self._base_select().where(
            BackupRetention.organization_id == organization_id,
            BackupRetention.target_kind == target_kind,
            BackupRetention.environment == environment,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = (
            select(BackupRetention.organization_id)
            .distinct()
            .where(BackupRetention.is_enabled.is_(True))
        )
        return (await self._session.execute(stmt)).scalars().all()


class BackupVerificationRepository(BaseRepository[BackupVerification]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BackupVerification, tenant_scope=tenant_scope)

    async def list_recent(
        self, organization_id: UUID, *, job_id: UUID | None = None, limit: int = 100
    ) -> Sequence[BackupVerification]:
        stmt = self._base_select().where(BackupVerification.organization_id == organization_id)
        if job_id is not None:
            stmt = stmt.where(BackupVerification.job_id == job_id)
        stmt = stmt.order_by(BackupVerification.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def latest_for_job(self, job_id: UUID) -> BackupVerification | None:
        """The most recent verification recorded for one job, if any --
        the seam :mod:`app.workers.verification_sweep` uses to decide
        whether a job is overdue for its next check."""
        stmt = (
            self._base_select()
            .where(BackupVerification.job_id == job_id)
            .order_by(BackupVerification.verified_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()


__all__ = [
    "MAX_PAGE_SIZE",
    "BackupArchiveRepository",
    "BackupJobRepository",
    "BackupRetentionRepository",
    "BackupScheduleRepository",
    "BackupSnapshotRepository",
    "BackupTargetRepository",
    "BackupVerificationRepository",
]
