"""Migration history, configuration migrations, and plugin migrations
carried out during an upgrade job."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import MigrationType, UpgradeJobStatus


class MigrationHistory(BaseModel):
    """``migration_history`` -- one migration step carried out (or
    attempted) during an upgrade job."""

    __tablename__ = "migration_history"
    __table_args__ = (
        Index("ix_migration_history_job", "upgrade_job_id"),
        Index("ix_migration_history_status", "status"),
    )

    upgrade_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("upgrade_jobs.id", ondelete="CASCADE"), index=True
    )
    migration_type: Mapped[MigrationType] = mapped_column(String(24), index=True)
    status: Mapped[UpgradeJobStatus] = mapped_column(
        String(16), default=UpgradeJobStatus.PENDING, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ConfigurationMigration(BaseModel):
    """``configuration_migrations`` -- one configuration key's own
    before/after value, applied during an upgrade job."""

    __tablename__ = "configuration_migrations"
    __table_args__ = (Index("ix_configuration_migration_job", "upgrade_job_id"),)

    upgrade_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("upgrade_jobs.id", ondelete="CASCADE"), index=True
    )
    config_key: Mapped[str] = mapped_column(String(256))
    old_value: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    new_value: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PluginMigration(BaseModel):
    """``plugin_migrations`` -- one plugin's own version migration,
    applied during an upgrade job."""

    __tablename__ = "plugin_migrations"
    __table_args__ = (Index("ix_plugin_migration_job", "upgrade_job_id"),)

    upgrade_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("upgrade_jobs.id", ondelete="CASCADE"), index=True
    )
    plugin_name: Mapped[str] = mapped_column(String(128), index=True)
    from_version: Mapped[str] = mapped_column(String(32))
    to_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[UpgradeJobStatus] = mapped_column(
        String(16), default=UpgradeJobStatus.PENDING, index=True
    )


__all__ = ["ConfigurationMigration", "MigrationHistory", "PluginMigration"]
