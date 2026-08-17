"""Hardening profiles -- the named target/benchmark combination a
hardening run is executed against."""

from __future__ import annotations

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import CisBenchmark, HardeningTargetType


class HardeningProfile(BaseModel):
    """``hardening_profiles`` -- one named hardening target/benchmark
    combination."""

    __tablename__ = "hardening_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_hardening_profile_name"),
    )

    name: Mapped[str] = mapped_column(String(256), index=True)
    target_type: Mapped[HardeningTargetType] = mapped_column(String(24), index=True)
    benchmark: Mapped[CisBenchmark] = mapped_column(String(24), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


__all__ = ["HardeningProfile"]
