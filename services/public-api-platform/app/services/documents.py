"""OpenAPI document, GraphQL schema, and changelog publication.

Like every other AI-IOS service's admin/internal-managed tables, there
is no ``POST`` route for any of these three -- docs/073's REST APIs
section lists exactly 15 endpoints and none of them publish
documentation. These service methods exist for internal authoring (or,
in tests, direct calls) and are only ever read over HTTP via
``GET /openapi`` and ``GET /graphql/schema``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.models.documents import ApiChangelogEntry, GraphQlSchema, OpenApiDocument
from app.repositories.documents import (
    ApiChangelogEntryRepository,
    GraphQlSchemaRepository,
    OpenApiDocumentRepository,
)


class OpenApiDocumentService:
    def __init__(self, repo: OpenApiDocumentRepository) -> None:
        self._repo = repo

    async def publish(
        self,
        organization_id: UUID,
        *,
        api_product_id: UUID,
        api_version_id: UUID,
        document: dict[str, Any],
        now: datetime,
    ) -> OpenApiDocument:
        return await self._repo.create(
            OpenApiDocument(
                organization_id=organization_id,
                api_product_id=api_product_id,
                api_version_id=api_version_id,
                document=document,
                is_published=True,
                published_at=now,
            )
        )


class GraphQlSchemaService:
    def __init__(self, repo: GraphQlSchemaRepository) -> None:
        self._repo = repo

    async def publish(
        self,
        organization_id: UUID,
        *,
        api_product_id: UUID,
        api_version_id: UUID,
        schema_sdl: str,
        now: datetime,
    ) -> GraphQlSchema:
        return await self._repo.create(
            GraphQlSchema(
                organization_id=organization_id,
                api_product_id=api_product_id,
                api_version_id=api_version_id,
                schema_sdl=schema_sdl,
                is_published=True,
                published_at=now,
            )
        )


class ApiChangelogService:
    def __init__(self, repo: ApiChangelogEntryRepository) -> None:
        self._repo = repo

    async def publish(
        self,
        organization_id: UUID,
        *,
        api_product_id: UUID,
        api_version_id: UUID,
        summary: str,
        is_breaking: bool,
        now: datetime,
    ) -> ApiChangelogEntry:
        return await self._repo.create(
            ApiChangelogEntry(
                organization_id=organization_id,
                api_product_id=api_product_id,
                api_version_id=api_version_id,
                summary=summary,
                is_breaking=is_breaking,
                published_at=now,
            )
        )


__all__ = ["ApiChangelogService", "GraphQlSchemaService", "OpenApiDocumentService"]
