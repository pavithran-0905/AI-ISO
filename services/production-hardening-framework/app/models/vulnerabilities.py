"""Vulnerability scan results."""

from __future__ import annotations

from shared_core.database.base import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import FindingSeverity, RemediationStatus, VulnerabilityScanType


class VulnerabilityScan(BaseModel):
    """``vulnerability_scans`` -- one detected vulnerability."""

    __tablename__ = "vulnerability_scans"

    scan_type: Mapped[VulnerabilityScanType] = mapped_column(String(16), index=True)
    cve_id: Mapped[str] = mapped_column(String(32), default="")
    severity: Mapped[FindingSeverity] = mapped_column(String(16), index=True)
    package_name: Mapped[str] = mapped_column(String(256))
    package_version: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[RemediationStatus] = mapped_column(
        String(16), default=RemediationStatus.OPEN, index=True
    )


__all__ = ["VulnerabilityScan"]
