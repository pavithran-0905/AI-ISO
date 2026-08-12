"""``document_reviews``, ``document_validation_results``,
``document_processing_jobs``, ``document_statistics``,
``document_reports``, and ``document_audit``.

The operational half: what a human decided, what the rules concluded,
what the pipeline did, and what any of it cost.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    JobStatus,
    ProcessingStage,
    ReportFormat,
    ReportKind,
    ReportStatus,
    ReviewDecision,
    ReviewStatus,
    ValidationOutcome,
    ValidationRuleKind,
)


class DocumentReview(BaseModel):
    """``document_reviews`` -- one human pass over one document.

    A row per review rather than a status on the document, because a
    document can be reviewed more than once -- corrected, reprocessed,
    reviewed again -- and collapsing that to a single verdict loses the
    history an auditor is actually asking for.
    """

    __tablename__ = "document_reviews"
    __table_args__ = (
        Index("ix_di_review_document", "document_id"),
        Index("ix_di_review_status", "status"),
        Index("ix_di_review_assignee", "assigned_to"),
        Index("ix_di_review_due", "due_at"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ReviewStatus] = mapped_column(
        String(16), default=ReviewStatus.PENDING, index=True
    )
    decision: Mapped[ReviewDecision | None] = mapped_column(String(16), default=None)
    reason: Mapped[str] = mapped_column(String(512))
    """Why this document needs a person. Required, not optional: a review
    queue whose items do not say what is wrong with them is a queue
    somebody works through by re-deriving the machine's doubt one
    document at a time."""
    triggered_by_confidence: Mapped[float | None] = mapped_column(Float, default=None)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(128), default=None, index=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    reviewer_id: Mapped[str | None] = mapped_column(String(128), default=None)
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    annotations: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    """Free-form marks a reviewer left on the document -- a highlighted
    region, a note against a field. Stored as-is because their shape is
    the reviewing tool's business, not this service's."""
    corrections_applied: Mapped[int] = mapped_column(Integer, default=0)
    fields_corrected: Mapped[list[str]] = mapped_column(JSON, default=list)
    """Which fields the reviewer changed. The measurement that says where
    extraction is weakest, and the only one that can be aggregated across
    thousands of documents into a decision about what to fix."""
    escalated_to: Mapped[str | None] = mapped_column(String(128), default=None)
    escalation_reason: Mapped[str | None] = mapped_column(String(512), default=None)


class DocumentValidationResult(BaseModel):
    """``document_validation_results`` -- one rule's verdict on one document.

    A row per rule rather than a pass/fail on the document: "this failed
    validation" is not actionable, and "the required field 'serial
    number' was not found" is.
    """

    __tablename__ = "document_validation_results"
    __table_args__ = (
        Index("ix_di_validation_document", "document_id"),
        Index("ix_di_validation_outcome", "outcome"),
        Index("ix_di_validation_rule", "rule_kind"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    rule_kind: Mapped[ValidationRuleKind] = mapped_column(String(24), index=True)
    rule_name: Mapped[str] = mapped_column(String(255))
    outcome: Mapped[ValidationOutcome] = mapped_column(String(16), index=True)
    message: Mapped[str] = mapped_column(String(1_024))
    field_name: Mapped[str | None] = mapped_column(String(255), default=None)
    expected: Mapped[str | None] = mapped_column(String(512), default=None)
    actual: Mapped[str | None] = mapped_column(String(512), default=None)
    """What the rule wanted and what it found, side by side. A message
    alone makes the reader reconstruct the comparison the rule already
    made."""
    is_blocking: Mapped[bool] = mapped_column(Boolean, default=False)
    """Whether this failure stops the document. Not every failure should:
    a missing optional field is worth recording and not worth halting
    for, and treating all of them as blocking trains people to override
    the whole check."""
    score: Mapped[float | None] = mapped_column(Float, default=None)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), default=None
    )
    similarity: Mapped[float | None] = mapped_column(Float, default=None)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class DocumentProcessingJob(BaseModel):
    """``document_processing_jobs`` -- one run of the pipeline.

    Carries per-stage outcomes rather than one status, because a document
    whose OCR succeeded and whose table extraction failed has a specific
    problem, and a single ``FAILED`` sends somebody to re-run the whole
    pipeline to find out which part.
    """

    __tablename__ = "document_processing_jobs"
    __table_args__ = (
        Index("ix_di_job_status", "status"),
        Index("ix_di_job_document", "document_id"),
        Index("ix_di_job_scheduled", "scheduled_at"),
        Index("ix_di_job_priority", "priority"),
    )

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), default=None, index=True
    )
    status: Mapped[JobStatus] = mapped_column(String(16), default=JobStatus.QUEUED, index=True)
    stages: Mapped[list[str]] = mapped_column(JSON, default=list)
    """Which stages this job was asked to run, in order. Stored because
    a re-extraction that skips OCR is a legitimate job and its result
    should not read as an OCR failure."""
    current_stage: Mapped[ProcessingStage | None] = mapped_column(String(24), default=None)
    stage_results: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    pages_processed: Mapped[int] = mapped_column(Integer, default=0)
    entities_extracted: Mapped[int] = mapped_column(Integer, default=0)
    tables_extracted: Mapped[int] = mapped_column(Integer, default=0)
    fields_extracted: Mapped[int] = mapped_column(Integer, default=0)
    stages_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    stages_failed: Mapped[int] = mapped_column(Integer, default=0)
    requested_by: Mapped[str | None] = mapped_column(String(128), default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    job_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class DocumentStatistic(BaseModel):
    """``document_statistics`` -- one rolled-up window per organization."""

    __tablename__ = "document_statistics"
    __table_args__ = (Index("ix_di_statistic_window", "window_start"),)

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    documents_total: Mapped[int] = mapped_column(Integer, default=0)
    documents_processed: Mapped[int] = mapped_column(Integer, default=0)
    documents_failed: Mapped[int] = mapped_column(Integer, default=0)
    documents_awaiting_review: Mapped[int] = mapped_column(Integer, default=0)
    pages_total: Mapped[int] = mapped_column(Integer, default=0)
    pages_ocred: Mapped[int] = mapped_column(Integer, default=0)
    entities_extracted: Mapped[int] = mapped_column(Integer, default=0)
    tables_extracted: Mapped[int] = mapped_column(Integer, default=0)
    fields_extracted: Mapped[int] = mapped_column(Integer, default=0)
    mean_ocr_confidence: Mapped[float | None] = mapped_column(Float, default=None)
    mean_extraction_confidence: Mapped[float | None] = mapped_column(Float, default=None)
    mean_processing_ms: Mapped[float | None] = mapped_column(Float, default=None)
    correction_rate: Mapped[float | None] = mapped_column(Float, default=None)
    """Fields a reviewer changed over fields a reviewer saw. ``None``
    where nobody reviewed anything -- reporting 0.0 for "unmeasured"
    would read as a perfect extractor, which is the most misleading
    number this table could carry."""
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    mean_review_ms: Mapped[float | None] = mapped_column(Float, default=None)
    by_format: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    by_category: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    by_status: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    by_entity_kind: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    most_corrected_fields: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    """The fields humans fix most often, ranked. The most actionable
    output of this table: it names exactly which extractor to improve
    next."""
    lowest_confidence_documents: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)


class DocumentReport(BaseModel):
    """``document_reports`` -- one generated report."""

    __tablename__ = "document_reports"
    __table_args__ = (Index("ix_di_report_kind", "kind"),)

    kind: Mapped[ReportKind] = mapped_column(String(24), index=True)
    report_format: Mapped[ReportFormat] = mapped_column(String(16), default=ReportFormat.JSON)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[ReportStatus] = mapped_column(String(16), default=ReportStatus.PENDING)
    content: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    row_count: Mapped[int | None] = mapped_column(Integer, default=None)
    generated_by: Mapped[str | None] = mapped_column(String(128), default=None)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)


class DocumentAudit(BaseModel):
    """``document_audit`` -- one thing that happened, append-only.

    Nothing in this service updates or deletes a row here, and the
    repository offers no method that would.
    """

    __tablename__ = "document_audit"
    __table_args__ = (
        Index("ix_di_audit_action", "action"),
        Index("ix_di_audit_entity", "entity_type", "entity_id"),
        Index("ix_di_audit_occurred", "occurred_at"),
    )

    action: Mapped[str] = mapped_column(String(32), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    entity_reference: Mapped[str | None] = mapped_column(String(512), default=None)
    """A human-readable name for the entity, captured at the time. The
    row survives the document being deleted, and an audit trail of bare
    UUIDs is one nobody can read."""
    actor_id: Mapped[str | None] = mapped_column(String(128), default=None, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    summary: Mapped[str | None] = mapped_column(String(512), default=None)
    succeeded: Mapped[bool] = mapped_column(Boolean, default=True)
    stage: Mapped[ProcessingStage | None] = mapped_column(String(24), default=None)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


__all__ = [
    "DocumentAudit",
    "DocumentProcessingJob",
    "DocumentReport",
    "DocumentReview",
    "DocumentStatistic",
    "DocumentValidationResult",
]
