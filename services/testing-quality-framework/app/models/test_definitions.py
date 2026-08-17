"""Test suites and the test cases within them."""

from __future__ import annotations

import uuid

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import TestType


class TestSuite(BaseModel):
    """``test_suites`` -- one named collection of test cases."""

    __tablename__ = "test_suites"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_test_suite_name"),)

    name: Mapped[str] = mapped_column(String(256), index=True)
    test_type: Mapped[TestType] = mapped_column(String(24), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class TestCase(BaseModel):
    """``test_cases`` -- one individual test case within a suite."""

    __tablename__ = "test_cases"
    __table_args__ = (Index("ix_test_case_suite", "test_suite_id"),)

    test_suite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_suites.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


__all__ = ["TestCase", "TestSuite"]
