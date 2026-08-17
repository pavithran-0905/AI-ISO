"""Configuration wizard profiles."""

from __future__ import annotations

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ConfigurationSection


class ConfigurationProfile(BaseModel):
    """``configuration_profiles`` -- one saved wizard step's
    configuration (organization setup, database, object storage,
    message queue, cache, Neo4j, AI provider, SMTP, notifications,
    license, backup, or monitoring)."""

    __tablename__ = "configuration_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_configuration_profile_name"),
    )

    name: Mapped[str] = mapped_column(String(128), index=True)
    section: Mapped[ConfigurationSection] = mapped_column(String(24), index=True)
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


__all__ = ["ConfigurationProfile"]
