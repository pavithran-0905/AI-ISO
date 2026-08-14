"""Repositories for the per-device operational tables: configuration,
synchronization, updates, firmware catalog, applications, AI models,
protocols, and component health."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EdgeDeviceType, SyncStatus, UpdateStatus
from app.models.operations import (
    EdgeAiModel,
    EdgeApplication,
    EdgeConfiguration,
    EdgeFirmware,
    EdgeHealth,
    EdgeProtocol,
    EdgeSynchronization,
    EdgeUpdate,
)

MAX_PAGE_SIZE = 500


class EdgeConfigurationRepository(BaseRepository[EdgeConfiguration]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeConfiguration, tenant_scope=tenant_scope)

    async def active_for_key(self, device_id: UUID, *, config_key: str) -> EdgeConfiguration | None:
        stmt = self._base_select().where(
            EdgeConfiguration.device_id == device_id,
            EdgeConfiguration.config_key == config_key,
            EdgeConfiguration.is_current.is_(True),
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_device(self, device_id: UUID) -> Sequence[EdgeConfiguration]:
        stmt = self._base_select().where(EdgeConfiguration.device_id == device_id)
        return (await self._session.execute(stmt)).scalars().all()


class EdgeSynchronizationRepository(BaseRepository[EdgeSynchronization]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeSynchronization, tenant_scope=tenant_scope)

    async def latest_completed_for_device(self, device_id: UUID) -> EdgeSynchronization | None:
        stmt = (
            self._base_select()
            .where(
                EdgeSynchronization.device_id == device_id,
                EdgeSynchronization.status == SyncStatus.COMPLETED,
            )
            .order_by(EdgeSynchronization.completed_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_device(self, device_id: UUID) -> Sequence[EdgeSynchronization]:
        stmt = self._base_select().where(EdgeSynchronization.device_id == device_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_failed(self, organization_id: UUID) -> Sequence[EdgeSynchronization]:
        stmt = self._base_select().where(
            EdgeSynchronization.organization_id == organization_id,
            EdgeSynchronization.status == SyncStatus.FAILED,
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_stuck(
        self, organization_id: UUID, *, before: datetime
    ) -> Sequence[EdgeSynchronization]:
        """Every synchronization still ``IN_PROGRESS`` that started
        before *before* -- a device that dropped mid-sync and never
        reported back."""
        stmt = self._base_select().where(
            EdgeSynchronization.organization_id == organization_id,
            EdgeSynchronization.status == SyncStatus.IN_PROGRESS,
            EdgeSynchronization.started_at < before,
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(EdgeSynchronization.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class EdgeUpdateRepository(BaseRepository[EdgeUpdate]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeUpdate, tenant_scope=tenant_scope)

    async def list_for_device(self, device_id: UUID) -> Sequence[EdgeUpdate]:
        stmt = (
            self._base_select()
            .where(EdgeUpdate.device_id == device_id)
            .order_by(EdgeUpdate.created_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_in_progress(
        self, organization_id: UUID, *, started_before: datetime | None = None
    ) -> Sequence[EdgeUpdate]:
        stmt = self._base_select().where(
            EdgeUpdate.organization_id == organization_id,
            EdgeUpdate.status.in_(
                [
                    UpdateStatus.PLANNED,
                    UpdateStatus.DOWNLOADING,
                    UpdateStatus.STAGING,
                    UpdateStatus.APPLYING,
                    UpdateStatus.VERIFYING,
                ]
            ),
        )
        if started_before is not None:
            stmt = stmt.where(EdgeUpdate.started_at < started_before)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(EdgeUpdate.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class EdgeFirmwareRepository(BaseRepository[EdgeFirmware]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeFirmware, tenant_scope=tenant_scope)

    async def find_by_type_and_version(
        self, device_type: EdgeDeviceType, version_label: str
    ) -> EdgeFirmware | None:
        stmt = self._base_select().where(
            EdgeFirmware.device_type == device_type, EdgeFirmware.version_label == version_label
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_type(self, device_type: EdgeDeviceType) -> Sequence[EdgeFirmware]:
        stmt = (
            self._base_select()
            .where(EdgeFirmware.device_type == device_type)
            .order_by(EdgeFirmware.skew_rank)
        )
        return (await self._session.execute(stmt)).scalars().all()


class EdgeApplicationRepository(BaseRepository[EdgeApplication]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeApplication, tenant_scope=tenant_scope)

    async def list_for_device(self, device_id: UUID) -> Sequence[EdgeApplication]:
        stmt = self._base_select().where(EdgeApplication.device_id == device_id)
        return (await self._session.execute(stmt)).scalars().all()


class EdgeAiModelRepository(BaseRepository[EdgeAiModel]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeAiModel, tenant_scope=tenant_scope)

    async def list_for_device(self, device_id: UUID) -> Sequence[EdgeAiModel]:
        stmt = self._base_select().where(EdgeAiModel.device_id == device_id)
        return (await self._session.execute(stmt)).scalars().all()


class EdgeProtocolRepository(BaseRepository[EdgeProtocol]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeProtocol, tenant_scope=tenant_scope)

    async def list_for_device(self, device_id: UUID) -> Sequence[EdgeProtocol]:
        stmt = self._base_select().where(EdgeProtocol.device_id == device_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(EdgeProtocol.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class EdgeHealthRepository(BaseRepository[EdgeHealth]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EdgeHealth, tenant_scope=tenant_scope)

    async def list_for_device(self, device_id: UUID) -> Sequence[EdgeHealth]:
        stmt = self._base_select().where(EdgeHealth.device_id == device_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def latest_per_component(self, device_id: UUID) -> Sequence[EdgeHealth]:
        """The most recent reading per component for one device.

        Reads every row for the device ordered newest-first and keeps
        only the first occurrence of each component -- the row count per
        device is small enough that a window-function query would add
        complexity this doesn't need.
        """
        stmt = (
            self._base_select()
            .where(EdgeHealth.device_id == device_id)
            .order_by(EdgeHealth.checked_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        seen: set[str] = set()
        latest: list[EdgeHealth] = []
        for row in rows:
            if row.component not in seen:
                seen.add(row.component)
                latest.append(row)
        return latest


__all__ = [
    "MAX_PAGE_SIZE",
    "EdgeAiModelRepository",
    "EdgeApplicationRepository",
    "EdgeConfigurationRepository",
    "EdgeFirmwareRepository",
    "EdgeHealthRepository",
    "EdgeProtocolRepository",
    "EdgeSynchronizationRepository",
    "EdgeUpdateRepository",
]
