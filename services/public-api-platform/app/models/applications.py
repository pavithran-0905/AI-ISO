"""Developer applications and their rotatable credentials."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ApplicationStatus, CredentialStatus


class DeveloperApplication(BaseModel):
    """``developer_applications`` -- one registered application
    belonging to a developer account."""

    __tablename__ = "developer_applications"
    __table_args__ = (Index("ix_developer_application_status", "status"),)

    developer_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("developer_accounts.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(String(2048), default="")
    redirect_uris: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_origins: Mapped[list[str]] = mapped_column(JSON, default=list)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[ApplicationStatus] = mapped_column(
        String(16), default=ApplicationStatus.PENDING, index=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ApplicationCredential(BaseModel):
    """``application_credentials`` -- one client id/secret pair issued
    to an application (distinct from its OAuth clients and API keys,
    which are their own tables for their own protocols)."""

    __tablename__ = "application_credentials"
    __table_args__ = (Index("ix_application_credential_status", "status"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("developer_applications.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_secret_hash: Mapped[str] = mapped_column(String(128))
    status: Mapped[CredentialStatus] = mapped_column(
        String(16), default=CredentialStatus.ACTIVE, index=True
    )
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["ApplicationCredential", "DeveloperApplication"]
