"""Health-gate verification results for upgrade jobs."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import CheckResultStatus, VerificationCheckType


class VerificationResult(BaseModel):
    """``verification_results`` -- one pre-upgrade or post-upgrade
    health-gate check outcome for an upgrade job."""

    __tablename__ = "verification_results"
    __table_args__ = (
        Index("ix_verification_result_job", "upgrade_job_id"),
        Index("ix_verification_result_check_type", "check_type"),
    )

    upgrade_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("upgrade_jobs.id", ondelete="CASCADE"), index=True
    )
    check_type: Mapped[VerificationCheckType] = mapped_column(String(24), index=True)
    status: Mapped[CheckResultStatus] = mapped_column(String(16), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = ["VerificationResult"]
