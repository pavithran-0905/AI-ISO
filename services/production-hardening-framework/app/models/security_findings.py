"""Security findings -- issues detected across hardening, security
review, or runtime protection."""

from __future__ import annotations

from shared_core.database.base import BaseModel
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import FindingSeverity, FindingStatus, HardeningTargetType


class SecurityFinding(BaseModel):
    """``security_findings`` -- one detected security issue."""

    __tablename__ = "security_findings"

    target_type: Mapped[HardeningTargetType] = mapped_column(String(24), index=True)
    severity: Mapped[FindingSeverity] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(256))
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[FindingStatus] = mapped_column(
        String(16), default=FindingStatus.OPEN, index=True
    )


__all__ = ["SecurityFinding"]
