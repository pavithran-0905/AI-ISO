"""The compatibility matrix -- known compatibility outcomes between
version pairs, per compatibility dimension."""

from __future__ import annotations

from shared_core.database.base import BaseModel
from sqlalchemy import Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import CheckResultStatus, CompatibilityType


class CompatibilityMatrixEntry(BaseModel):
    """``compatibility_matrix`` -- one known compatibility outcome
    between a *from* and *to* version, for one compatibility
    dimension (version, API, schema, plugin, connector, OS,
    Kubernetes, cloud, dependency)."""

    __tablename__ = "compatibility_matrix"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "from_version",
            "to_version",
            "compatibility_type",
            name="uq_compatibility_matrix_entry",
        ),
        Index("ix_compatibility_matrix_type", "compatibility_type"),
    )

    from_version: Mapped[str] = mapped_column(String(32), index=True)
    to_version: Mapped[str] = mapped_column(String(32), index=True)
    compatibility_type: Mapped[CompatibilityType] = mapped_column(String(24), index=True)
    status: Mapped[CheckResultStatus] = mapped_column(String(16), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")


__all__ = ["CompatibilityMatrixEntry"]
