"""Repositories for devices, sessions, profiles, and device-bound
tokens."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.devices import MobileDevice, MobileProfile, MobileSession, MobileToken
from app.models.enums import DeviceTrustStatus, SessionStatus, TokenStatus

MAX_PAGE_SIZE = 500


class MobileDeviceRepository(BaseRepository[MobileDevice]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MobileDevice, tenant_scope=tenant_scope)

    async def find_by_identifier(
        self, organization_id: UUID, *, device_identifier: str
    ) -> MobileDevice | None:
        stmt = self._base_select().where(
            MobileDevice.organization_id == organization_id,
            MobileDevice.device_identifier == device_identifier,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[MobileDevice]:
        stmt = (
            self._base_select()
            .where(MobileDevice.organization_id == organization_id)
            .order_by(MobileDevice.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_trust_status(
        self, organization_id: UUID, *, trust_status: DeviceTrustStatus
    ) -> Sequence[MobileDevice]:
        stmt = self._base_select().where(
            MobileDevice.organization_id == organization_id,
            MobileDevice.trust_status == trust_status,
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(MobileDevice.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class MobileSessionRepository(BaseRepository[MobileSession]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MobileSession, tenant_scope=tenant_scope)

    async def list_active(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[MobileSession]:
        stmt = (
            self._base_select()
            .where(
                MobileSession.organization_id == organization_id,
                MobileSession.status == SessionStatus.ACTIVE,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def find_active_for_device(
        self, organization_id: UUID, *, device_id: UUID, user_id: str
    ) -> MobileSession | None:
        stmt = self._base_select().where(
            MobileSession.organization_id == organization_id,
            MobileSession.device_id == device_id,
            MobileSession.user_id == user_id,
            MobileSession.status == SessionStatus.ACTIVE,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def has_prior_session(self, organization_id: UUID, *, device_id: UUID) -> bool:
        """Whether *device_id* has ever had any session recorded --
        used to decide whether a login is this device's first (a "new
        device login")."""
        stmt = self._base_select(include_deleted=True).where(
            MobileSession.organization_id == organization_id, MobileSession.device_id == device_id
        )
        return (await self._session.execute(stmt)).scalars().first() is not None

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 100
    ) -> Sequence[MobileSession]:
        stmt = (
            self._base_select()
            .where(MobileSession.organization_id == organization_id)
            .order_by(MobileSession.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(MobileSession.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class MobileProfileRepository(BaseRepository[MobileProfile]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MobileProfile, tenant_scope=tenant_scope)

    async def find_by_user(self, organization_id: UUID, *, user_id: str) -> MobileProfile | None:
        stmt = self._base_select().where(
            MobileProfile.organization_id == organization_id, MobileProfile.user_id == user_id
        )
        return (await self._session.execute(stmt)).scalars().first()


class MobileTokenRepository(BaseRepository[MobileToken]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MobileToken, tenant_scope=tenant_scope)

    async def list_active(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[MobileToken]:
        stmt = (
            self._base_select()
            .where(
                MobileToken.organization_id == organization_id,
                MobileToken.status == TokenStatus.ACTIVE,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(MobileToken.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "MobileDeviceRepository",
    "MobileProfileRepository",
    "MobileSessionRepository",
    "MobileTokenRepository",
]
