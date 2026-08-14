"""Repositories for push tokens and push notifications."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationDeliveryStatus, PushPlatform
from app.models.notifications import MobileNotification, MobilePushToken

MAX_PAGE_SIZE = 500


class MobilePushTokenRepository(BaseRepository[MobilePushToken]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MobilePushToken, tenant_scope=tenant_scope)

    async def find_for_device(
        self, organization_id: UUID, *, device_id: UUID, platform: PushPlatform
    ) -> MobilePushToken | None:
        stmt = self._base_select().where(
            MobilePushToken.organization_id == organization_id,
            MobilePushToken.device_id == device_id,
            MobilePushToken.platform == platform,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_active_for_device(
        self, organization_id: UUID, *, device_id: UUID
    ) -> Sequence[MobilePushToken]:
        stmt = self._base_select().where(
            MobilePushToken.organization_id == organization_id,
            MobilePushToken.device_id == device_id,
        )
        return (await self._session.execute(stmt)).scalars().all()


class MobileNotificationRepository(BaseRepository[MobileNotification]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MobileNotification, tenant_scope=tenant_scope)

    async def list_for_device(
        self, organization_id: UUID, *, device_id: UUID, limit: int = 100
    ) -> Sequence[MobileNotification]:
        stmt = (
            self._base_select()
            .where(
                MobileNotification.organization_id == organization_id,
                MobileNotification.device_id == device_id,
            )
            .order_by(MobileNotification.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_pending(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[MobileNotification]:
        stmt = (
            self._base_select()
            .where(
                MobileNotification.organization_id == organization_id,
                MobileNotification.status == NotificationDeliveryStatus.PENDING,
            )
            .order_by(MobileNotification.created_at.asc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(MobileNotification.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "MobileNotificationRepository", "MobilePushTokenRepository"]
