"""API keys, personal access tokens, OAuth clients, and OAuth tokens."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import CredentialStatus, OAuthTokenStatus, OAuthTokenType


class ApiKey(BaseModel):
    """``api_keys`` -- one application-scoped API key."""

    __tablename__ = "api_keys"
    __table_args__ = (Index("ix_api_key_status", "status"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("developer_applications.id", ondelete="CASCADE"), index=True
    )
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[CredentialStatus] = mapped_column(
        String(16), default=CredentialStatus.ACTIVE, index=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class PersonalAccessToken(BaseModel):
    """``personal_access_tokens`` -- one developer-account-scoped
    long-lived token, not tied to any single application."""

    __tablename__ = "personal_access_tokens"
    __table_args__ = (Index("ix_pat_status", "status"),)

    developer_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("developer_accounts.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128), default="")
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[CredentialStatus] = mapped_column(
        String(16), default=CredentialStatus.ACTIVE, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class OAuthClient(BaseModel):
    """``oauth_clients`` -- one application's OAuth2 client
    registration."""

    __tablename__ = "oauth_clients"
    __table_args__ = (Index("ix_oauth_client_status", "status"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("developer_applications.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_secret_hash: Mapped[str] = mapped_column(String(128))
    grant_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    redirect_uris: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[CredentialStatus] = mapped_column(
        String(16), default=CredentialStatus.ACTIVE, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class OAuthToken(BaseModel):
    """``oauth_tokens`` -- one issued OAuth2 access or refresh token."""

    __tablename__ = "oauth_tokens"
    __table_args__ = (
        Index("ix_oauth_token_client", "oauth_client_id"),
        Index("ix_oauth_token_status", "status"),
    )

    oauth_client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("oauth_clients.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    token_type: Mapped[OAuthTokenType] = mapped_column(String(8), index=True)
    status: Mapped[OAuthTokenStatus] = mapped_column(
        String(16), default=OAuthTokenStatus.ACTIVE, index=True
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["ApiKey", "OAuthClient", "OAuthToken", "PersonalAccessToken"]
