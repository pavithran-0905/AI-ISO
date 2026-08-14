"""Maintenance windows and platform announcements."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import AnnouncementScope, MaintenanceKind, MaintenanceStatus


class MaintenanceWindow(BaseModel):
    """``maintenance_windows`` -- one scheduled or in-progress
    maintenance operation."""

    __tablename__ = "maintenance_windows"
    __table_args__ = (
        Index("ix_maintenance_window_status", "status"),
        Index("ix_maintenance_window_starts_at", "starts_at"),
    )

    title: Mapped[str] = mapped_column(String(255))
    kind: Mapped[MaintenanceKind] = mapped_column(String(16), default=MaintenanceKind.ROUTINE)
    status: Mapped[MaintenanceStatus] = mapped_column(
        String(16), default=MaintenanceStatus.SCHEDULED, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    read_only_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[str | None] = mapped_column(String(128), default=None)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class PlatformAnnouncement(BaseModel):
    """``platform_announcements`` -- one banner/notice shown to
    operators or tenants."""

    __tablename__ = "platform_announcements"
    __table_args__ = (Index("ix_platform_announcement_scope", "scope"),)

    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    scope: Mapped[AnnouncementScope] = mapped_column(String(16), default=AnnouncementScope.GLOBAL)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


__all__ = ["MaintenanceWindow", "PlatformAnnouncement"]
