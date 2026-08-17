"""Repositories for API versions and their documentation artifacts."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import ApiChangelogEntry, ApiVersion, GraphQlSchema, OpenApiDocument

MAX_PAGE_SIZE = 500


class ApiVersionRepository(BaseRepository[ApiVersion]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ApiVersion, tenant_scope=tenant_scope)

    async def list_for_product(self, api_product_id: UUID) -> Sequence[ApiVersion]:
        stmt = self._base_select().where(ApiVersion.api_product_id == api_product_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_with_planned_deprecation(self, organization_id: UUID) -> Sequence[ApiVersion]:
        stmt = self._base_select().where(
            ApiVersion.organization_id == organization_id, ApiVersion.deprecated_at.is_not(None)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_with_planned_sunset(self, organization_id: UUID) -> Sequence[ApiVersion]:
        stmt = self._base_select().where(
            ApiVersion.organization_id == organization_id, ApiVersion.sunset_at.is_not(None)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(ApiVersion.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class OpenApiDocumentRepository(BaseRepository[OpenApiDocument]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, OpenApiDocument, tenant_scope=tenant_scope)

    async def find_published_for_product(
        self, organization_id: UUID, *, api_product_id: UUID
    ) -> OpenApiDocument | None:
        stmt = (
            self._base_select()
            .where(
                OpenApiDocument.organization_id == organization_id,
                OpenApiDocument.api_product_id == api_product_id,
                OpenApiDocument.is_published.is_(True),
            )
            .order_by(OpenApiDocument.published_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()


class GraphQlSchemaRepository(BaseRepository[GraphQlSchema]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, GraphQlSchema, tenant_scope=tenant_scope)

    async def find_published_for_product(
        self, organization_id: UUID, *, api_product_id: UUID
    ) -> GraphQlSchema | None:
        stmt = (
            self._base_select()
            .where(
                GraphQlSchema.organization_id == organization_id,
                GraphQlSchema.api_product_id == api_product_id,
                GraphQlSchema.is_published.is_(True),
            )
            .order_by(GraphQlSchema.published_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()


class ApiChangelogEntryRepository(BaseRepository[ApiChangelogEntry]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ApiChangelogEntry, tenant_scope=tenant_scope)

    async def list_for_product(
        self, organization_id: UUID, *, api_product_id: UUID, limit: int = 100
    ) -> Sequence[ApiChangelogEntry]:
        stmt = (
            self._base_select()
            .where(
                ApiChangelogEntry.organization_id == organization_id,
                ApiChangelogEntry.api_product_id == api_product_id,
            )
            .order_by(ApiChangelogEntry.published_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "ApiChangelogEntryRepository",
    "ApiVersionRepository",
    "GraphQlSchemaRepository",
    "OpenApiDocumentRepository",
]
