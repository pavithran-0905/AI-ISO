"""Synthetic monitoring checks and contract tests."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import CheckResultStatus, ContractTestType, SyntheticCheckType


class SyntheticCheck(BaseModel):
    """``synthetic_checks`` -- one synthetic monitoring probe's own
    outcome (an API check, a UI check, a login flow, a full workflow, a
    transaction, an availability/global check)."""

    __tablename__ = "synthetic_checks"
    __table_args__ = (Index("ix_synthetic_check_type", "check_type"),)

    name: Mapped[str] = mapped_column(String(128), index=True)
    check_type: Mapped[SyntheticCheckType] = mapped_column(String(16), index=True)
    status: Mapped[CheckResultStatus] = mapped_column(String(16), index=True)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    detail: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ContractTest(BaseModel):
    """``contract_tests`` -- one consumer/provider contract
    validation outcome."""

    __tablename__ = "contract_tests"
    __table_args__ = (Index("ix_contract_test_type", "contract_type"),)

    name: Mapped[str] = mapped_column(String(128), index=True)
    contract_type: Mapped[ContractTestType] = mapped_column(String(32), index=True)
    status: Mapped[CheckResultStatus] = mapped_column(String(16), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")


__all__ = ["ContractTest", "SyntheticCheck"]
