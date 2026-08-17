"""Certificate inventory."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column


class CertificateInventoryEntry(BaseModel):
    """``certificate_inventory`` -- one tracked TLS certificate."""

    __tablename__ = "certificate_inventory"

    subject: Mapped[str] = mapped_column(String(256), index=True)
    issuer: Mapped[str] = mapped_column(String(256), default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    is_mutual_tls: Mapped[bool] = mapped_column(Boolean, default=False)
    is_expiring: Mapped[bool] = mapped_column(Boolean, default=False)
    """Set once the certificate first enters its own warning window --
    the edge-trigger flag ``CertificateExpirySweepWorker`` uses so a
    long-neglected certificate does not re-notify on every tick."""


__all__ = ["CertificateInventoryEntry"]
