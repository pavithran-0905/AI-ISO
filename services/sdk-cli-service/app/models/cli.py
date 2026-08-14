"""CLI versions, plugins, profiles, sessions, usage, and updates."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import CliAuthMethod, CliUpdateStatus, PluginStatus


class CliVersion(BaseModel):
    """``cli_versions`` -- one released or draft version of the CLI."""

    __tablename__ = "cli_versions"
    __table_args__ = (Index("ix_cli_version_label", "version_label"),)

    version_label: Mapped[str] = mapped_column(String(32), index=True)
    """Deliberately not named ``version`` -- see
    ``app.models.sdk.SdkVersion.version_label``'s own docstring."""
    api_compatibility_version: Mapped[str] = mapped_column(String(32))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class CliPlugin(BaseModel):
    """``cli_plugins`` -- one CLI plugin, at any point in its own
    install lifecycle."""

    __tablename__ = "cli_plugins"
    __table_args__ = (
        Index("ix_cli_plugin_name", "name"),
        Index("ix_cli_plugin_status", "status"),
    )

    name: Mapped[str] = mapped_column(String(128), index=True)
    version_label: Mapped[str] = mapped_column(String(32))
    """Deliberately not named ``version`` -- see
    ``app.models.sdk.SdkVersion.version_label``'s own docstring."""
    status: Mapped[PluginStatus] = mapped_column(
        String(16), default=PluginStatus.AVAILABLE, index=True
    )
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    is_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    marketplace_ref: Mapped[str | None] = mapped_column(String(255), default=None)
    """A correlation id for this plugin's own listing in
    ``services/plugin-marketplace-service`` (Prompt 059) -- never a
    foreign key, since that table lives in a different service's
    database."""


class CliProfile(BaseModel):
    """``cli_profiles`` -- one named credential/context profile."""

    __tablename__ = "cli_profiles"
    __table_args__ = (Index("ix_cli_profile_name", "profile_name"),)

    profile_name: Mapped[str] = mapped_column(String(128), index=True)
    auth_method: Mapped[CliAuthMethod] = mapped_column(String(24))
    organization_context: Mapped[uuid.UUID | None] = mapped_column(default=None)
    project_context: Mapped[uuid.UUID | None] = mapped_column(default=None)
    region_context: Mapped[str | None] = mapped_column(String(64), default=None)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class CliSession(BaseModel):
    """``cli_sessions`` -- one authenticated CLI session for a profile."""

    __tablename__ = "cli_sessions"
    __table_args__ = (Index("ix_cli_session_profile", "profile_id"),)

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cli_profiles.id", ondelete="CASCADE"), index=True
    )
    auth_method: Mapped[CliAuthMethod] = mapped_column(String(24))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    """Whether this session is still usable -- ``False`` once force
    logged out, deliberately not named ``is_active`` (see this
    package's README on ``BaseEntityMixin``'s own reserved columns)."""


class CliUsage(BaseModel):
    """``cli_usage`` -- one executed CLI command event."""

    __tablename__ = "cli_usage"
    __table_args__ = (
        Index("ix_cli_usage_session", "session_id"),
        Index("ix_cli_usage_executed_at", "executed_at"),
    )

    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cli_sessions.id", ondelete="SET NULL"), default=None
    )
    command_group: Mapped[str] = mapped_column(String(64), index=True)
    command: Mapped[str] = mapped_column(String(128))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    succeeded: Mapped[bool] = mapped_column(Boolean, default=True)


class CliUpdate(BaseModel):
    """``cli_updates`` -- one CLI update attempt."""

    __tablename__ = "cli_updates"
    __table_args__ = (Index("ix_cli_update_status", "status"),)

    from_version: Mapped[str] = mapped_column(String(32))
    to_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[CliUpdateStatus] = mapped_column(
        String(16), default=CliUpdateStatus.PENDING, index=True
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["CliPlugin", "CliProfile", "CliSession", "CliUpdate", "CliUsage", "CliVersion"]
