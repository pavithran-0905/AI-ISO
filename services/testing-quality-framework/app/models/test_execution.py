"""Test runs and the individual test-case results within them."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import TestResultStatus, TestRunStatus


class TestRun(BaseModel):
    """``test_runs`` -- one execution of a test suite -- see
    ``app.pipeline.engine`` for the transition table this drives."""

    __tablename__ = "test_runs"
    __table_args__ = (
        Index("ix_test_run_suite", "test_suite_id"),
        Index("ix_test_run_status", "status"),
    )

    test_suite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_suites.id", ondelete="CASCADE"), index=True
    )
    test_environment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_environments.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[TestRunStatus] = mapped_column(
        String(16), default=TestRunStatus.PENDING, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    error_message: Mapped[str] = mapped_column(Text, default="")


class TestResult(BaseModel):
    """``test_results`` -- one test case's own outcome within a test
    run."""

    __tablename__ = "test_results"
    __table_args__ = (
        Index("ix_test_result_run", "test_run_id"),
        Index("ix_test_result_case", "test_case_id"),
    )

    test_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), index=True
    )
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_cases.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[TestResultStatus] = mapped_column(String(16), index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str] = mapped_column(Text, default="")


__all__ = ["TestResult", "TestRun"]
