"""Production certifications."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import CertificationStatus


class ProductionCertification(BaseModel):
    """``production_certifications`` -- one named target's own
    production-readiness certification."""

    __tablename__ = "production_certifications"

    name: Mapped[str] = mapped_column(String(256), index=True)
    status: Mapped[CertificationStatus] = mapped_column(
        String(16), default=CertificationStatus.PENDING, index=True
    )
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["ProductionCertification"]
