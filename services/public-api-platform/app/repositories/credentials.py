"""Repositories for API keys, personal access tokens, OAuth clients,
and OAuth tokens."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credentials import ApiKey, OAuthClient, OAuthToken, PersonalAccessToken
from app.models.enums import CredentialStatus, OAuthTokenStatus

MAX_PAGE_SIZE = 500


class ApiKeyRepository(BaseRepository[ApiKey]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ApiKey, tenant_scope=tenant_scope)

    async def list_active(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[ApiKey]:
        stmt = (
            self._base_select()
            .where(
                ApiKey.organization_id == organization_id, ApiKey.status == CredentialStatus.ACTIVE
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_application(self, application_id: UUID) -> Sequence[ApiKey]:
        stmt = self._base_select().where(ApiKey.application_id == application_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(ApiKey.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class PersonalAccessTokenRepository(BaseRepository[PersonalAccessToken]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PersonalAccessToken, tenant_scope=tenant_scope)

    async def list_active(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[PersonalAccessToken]:
        stmt = (
            self._base_select()
            .where(
                PersonalAccessToken.organization_id == organization_id,
                PersonalAccessToken.status == CredentialStatus.ACTIVE,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(PersonalAccessToken.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class OAuthClientRepository(BaseRepository[OAuthClient]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, OAuthClient, tenant_scope=tenant_scope)

    async def find_by_client_id(
        self, organization_id: UUID, *, client_id: str
    ) -> OAuthClient | None:
        stmt = self._base_select().where(
            OAuthClient.organization_id == organization_id, OAuthClient.client_id == client_id
        )
        return (await self._session.execute(stmt)).scalars().first()


class OAuthTokenRepository(BaseRepository[OAuthToken]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, OAuthToken, tenant_scope=tenant_scope)

    async def list_active(
        self, organization_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[OAuthToken]:
        stmt = (
            self._base_select()
            .where(
                OAuthToken.organization_id == organization_id,
                OAuthToken.status == OAuthTokenStatus.ACTIVE,
            )
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(OAuthToken.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "ApiKeyRepository",
    "OAuthClientRepository",
    "OAuthTokenRepository",
    "PersonalAccessTokenRepository",
]
