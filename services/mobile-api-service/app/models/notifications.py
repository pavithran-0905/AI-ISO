"""Mobile push notifications and registered push tokens."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import NotificationDeliveryStatus, PushPlatform, PushTokenStatus


class MobilePushToken(BaseModel):
    """``mobile_push_tokens`` -- one device's registered FCM/APNs push
    token."""

    __tablename__ = "mobile_push_tokens"
    __table_args__ = (
        UniqueConstraint("device_id", "platform", name="uq_mobile_push_token_device_platform"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mobile_devices.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[PushPlatform] = mapped_column(String(8))
    token_value: Mapped[str] = mapped_column(String(512))
    status: Mapped[PushTokenStatus] = mapped_column(
        String(16), default=PushTokenStatus.ACTIVE, index=True
    )
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MobileNotification(BaseModel):
    """``mobile_notifications`` -- one push notification queued or sent
    to one device."""

    __tablename__ = "mobile_notifications"
    __table_args__ = (
        Index("ix_mobile_notification_device", "device_id"),
        Index("ix_mobile_notification_status", "status"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mobile_devices.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(String(2048))
    category: Mapped[str] = mapped_column(String(64), default="general")
    status: Mapped[NotificationDeliveryStatus] = mapped_column(
        String(16), default=NotificationDeliveryStatus.PENDING, index=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["MobileNotification", "MobilePushToken"]
