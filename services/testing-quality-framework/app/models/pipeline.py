"""Pipeline (CI/CD run) results.

**A declared seam over the pipeline's own execution.** This service
tracks the *outcome* of a pipeline run reported back to it; it never
triggers or orchestrates a CI/CD platform itself, per docs/077's own
"DO NOT IMPLEMENT: CI/CD Platforms".
"""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import TestRunStatus


class PipelineResult(BaseModel):
    """``pipeline_results`` -- one CI/CD pipeline run's own outcome,
    as reported back to this service -- see ``app.pipeline.engine``
    for the transition table this drives."""

    __tablename__ = "pipeline_results"

    name: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[TestRunStatus] = mapped_column(
        String(16), default=TestRunStatus.PENDING, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    detail: Mapped[str] = mapped_column(Text, default="")


__all__ = ["PipelineResult"]
