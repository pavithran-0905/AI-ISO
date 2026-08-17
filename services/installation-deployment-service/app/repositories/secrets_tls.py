"""Repositories for TLS certificates and generated secrets."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SecretStatus
from app.models.secrets_tls import GeneratedSecret, TlsCertificate

MAX_PAGE_SIZE = 500


class TlsCertificateRepository(BaseRepository[TlsCertificate]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, TlsCertificate, tenant_scope=tenant_scope)

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[TlsCertificate]:
        stmt = (
            self._base_select()
            .where(TlsCertificate.organization_id == organization_id)
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_expiring_before(
        self, organization_id: UUID, *, before: datetime, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[TlsCertificate]:
        stmt = (
            self._base_select()
            .where(
                TlsCertificate.organization_id == organization_id,
                TlsCertificate.not_after < before,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(TlsCertificate.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class GeneratedSecretRepository(BaseRepository[GeneratedSecret]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, GeneratedSecret, tenant_scope=tenant_scope)

    async def find_active_by_name(
        self, organization_id: UUID, *, secret_name: str
    ) -> GeneratedSecret | None:
        """The current ``ACTIVE`` row for *secret_name*, ignoring any
        earlier rows a rotation has already retired to ``ROTATED``."""
        stmt = self._base_select().where(
            GeneratedSecret.organization_id == organization_id,
            GeneratedSecret.secret_name == secret_name,
            GeneratedSecret.status == SecretStatus.ACTIVE,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_name(
        self, organization_id: UUID, *, secret_name: str
    ) -> Sequence[GeneratedSecret]:
        stmt = (
            self._base_select()
            .where(
                GeneratedSecret.organization_id == organization_id,
                GeneratedSecret.secret_name == secret_name,
            )
            .order_by(GeneratedSecret.created_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_all(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[GeneratedSecret]:
        stmt = (
            self._base_select()
            .where(GeneratedSecret.organization_id == organization_id)
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = ["MAX_PAGE_SIZE", "GeneratedSecretRepository", "TlsCertificateRepository"]
