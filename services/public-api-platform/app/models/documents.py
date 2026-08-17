"""API versions and their published documentation artifacts."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ApiVersionStatus


class ApiVersion(BaseModel):
    """``api_versions`` -- one version of an API product."""

    __tablename__ = "api_versions"
    __table_args__ = (
        Index("ix_api_version_product", "api_product_id"),
        Index("ix_api_version_status", "status"),
        Index("ix_api_version_label", "version_label"),
    )

    api_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_products.id", ondelete="CASCADE"), index=True
    )
    version_label: Mapped[str] = mapped_column(String(32), index=True)
    """Deliberately not named ``version`` -- that is already
    ``BaseEntityMixin``'s own reserved optimistic-locking column. See
    ``services/sdk-cli-service``'s and ``services/mobile-api-service``'s
    own documented lesson on this exact collision."""
    status: Mapped[ApiVersionStatus] = mapped_column(
        String(16), default=ApiVersionStatus.DRAFT, index=True
    )
    is_breaking_change: Mapped[bool] = mapped_column(Boolean, default=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    sunset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class OpenApiDocument(BaseModel):
    """``openapi_documents`` -- one published OpenAPI document for an
    API product version."""

    __tablename__ = "openapi_documents"
    __table_args__ = (Index("ix_openapi_document_product", "api_product_id"),)

    api_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_products.id", ondelete="CASCADE"), index=True
    )
    api_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_versions.id", ondelete="CASCADE"), index=True
    )
    document: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class GraphQlSchema(BaseModel):
    """``graphql_schemas`` -- one published GraphQL SDL document for an
    API product version."""

    __tablename__ = "graphql_schemas"
    __table_args__ = (Index("ix_graphql_schema_product", "api_product_id"),)

    api_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_products.id", ondelete="CASCADE"), index=True
    )
    api_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_versions.id", ondelete="CASCADE"), index=True
    )
    schema_sdl: Mapped[str] = mapped_column(Text, default="")
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ApiChangelogEntry(BaseModel):
    """``api_changelog`` -- one published changelog entry for an API
    version."""

    __tablename__ = "api_changelog"
    __table_args__ = (Index("ix_api_changelog_product", "api_product_id"),)

    api_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_products.id", ondelete="CASCADE"), index=True
    )
    api_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_versions.id", ondelete="CASCADE"), index=True
    )
    summary: Mapped[str] = mapped_column(Text)
    is_breaking: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


__all__ = ["ApiChangelogEntry", "ApiVersion", "GraphQlSchema", "OpenApiDocument"]
