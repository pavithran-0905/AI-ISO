"""``knowledge_sources``, ``indexing_jobs``, ``rag_statistics``,
``rag_reports``, and ``rag_audit``.
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    AuditAction,
    ClassificationLevel,
    IndexKind,
    IndexStatus,
    ReportFormat,
    ReportKind,
    ReportStatus,
    SourceKind,
    SyncStatus,
)


class KnowledgeSource(BaseModel):
    """``knowledge_sources`` -- one upstream system documents come from.

    **No credential is stored here.** ``credential_reference`` holds a
    lookup key resolved live against secrets-management-service, the same
    contract prompt-management-service uses for its secret variables. A
    Confluence token written into this table would be a credential in a
    database, in every backup of it, and in any log line rendering the
    row -- and this table is read on every sync sweep.
    """

    __tablename__ = "knowledge_sources"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_knowledge_source_slug"),
        Index("ix_knowledge_source_kind", "source_kind"),
        Index("ix_knowledge_source_sync_status", "sync_status"),
    )

    slug: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    source_kind: Mapped[SourceKind] = mapped_column(String(24), index=True)
    uri: Mapped[str | None] = mapped_column(String(2_048), default=None)
    credential_reference: Mapped[str | None] = mapped_column(String(255), default=None)
    """A lookup key, never a value. See this class's own docstring."""
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    sync_interval_seconds: Mapped[int] = mapped_column(Integer, default=3_600)
    sync_status: Mapped[SyncStatus] = mapped_column(
        String(16), default=SyncStatus.NEVER_SYNCED, index=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_sync_cursor: Mapped[str | None] = mapped_column(String(512), default=None)
    """Where the last incremental sync got to -- a timestamp, a git SHA,
    a continuation token. What makes "Incremental Updates" incremental
    rather than a full re-fetch that only *looks* incremental."""
    last_sync_error: Mapped[str | None] = mapped_column(Text, default=None)
    default_classification: Mapped[ClassificationLevel] = mapped_column(
        String(16), default=ClassificationLevel.INTERNAL
    )
    """Applied to every document imported from here. ``INTERNAL``, not
    ``PUBLIC``: a source whose sensitivity nobody declared should not
    silently publish its contents to every caller."""
    default_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    chunk_size: Mapped[int | None] = mapped_column(Integer, default=None)
    chunk_overlap: Mapped[int | None] = mapped_column(Integer, default=None)
    chunk_strategy: Mapped[str | None] = mapped_column(String(24), default=None)
    """Per-source overrides. A git repository of code and a Confluence
    space of prose want different chunking, and forcing one global
    strategy makes the service worse at both."""
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    configuration: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class IndexingJob(BaseModel):
    """``indexing_jobs`` -- one unit of indexing work.

    Persisted rather than held in memory so an interrupted index is
    recoverable: a worker that dies mid-job leaves a ``RUNNING`` row with
    a ``started_at``, which the next sweep can see is stale and reclaim.
    An in-memory queue would lose the work silently and leave the
    documents unindexed with nothing recording that they should be.
    """

    __tablename__ = "indexing_jobs"
    __table_args__ = (
        Index("ix_indexing_job_status", "status"),
        Index("ix_indexing_job_scheduled_at", "scheduled_at"),
        Index("ix_indexing_job_priority", "priority"),
    )

    knowledge_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), default=None, index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), default=None, index=True
    )
    """Set for a single-document job, ``None`` for a whole-source or
    whole-organization one. Both shapes are real: a realtime index of one
    upload and a scheduled reindex of everything."""
    kind: Mapped[IndexKind] = mapped_column(String(16), default=IndexKind.INCREMENTAL, index=True)
    status: Mapped[IndexStatus] = mapped_column(String(16), default=IndexStatus.QUEUED, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    """Lower runs first ("Priority Index"). 100 is the default so both
    raising and lowering priority are possible without renumbering."""
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    documents_total: Mapped[int] = mapped_column(Integer, default=0)
    documents_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    documents_failed: Mapped[int] = mapped_column(Integer, default=0)
    chunks_created: Mapped[int] = mapped_column(Integer, default=0)
    vectors_created: Mapped[int] = mapped_column(Integer, default=0)
    tokens_embedded: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    requested_by: Mapped[str | None] = mapped_column(String(128), default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    job_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class RagStatistic(BaseModel):
    """``rag_statistics`` -- one rolled-up activity window.

    Windows rather than live aggregates, for the same reason every prior
    AI-IOS service does it: a dashboard that recomputes from the
    execution tables on every load scales with history rather than with
    what it displays.
    """

    __tablename__ = "rag_statistics"
    __table_args__ = (Index("ix_rag_statistic_window", "window_start", "window_end"),)

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    documents_total: Mapped[int] = mapped_column(Integer, default=0)
    documents_indexed: Mapped[int] = mapped_column(Integer, default=0)
    documents_failed: Mapped[int] = mapped_column(Integer, default=0)
    chunks_total: Mapped[int] = mapped_column(Integer, default=0)
    vectors_total: Mapped[int] = mapped_column(Integer, default=0)
    index_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    retrieval_count: Mapped[int] = mapped_column(Integer, default=0)
    retrievals_empty: Mapped[int] = mapped_column(Integer, default=0)
    retrievals_denied: Mapped[int] = mapped_column(Integer, default=0)
    average_latency_ms: Mapped[float | None] = mapped_column(Float, default=None)
    average_result_count: Mapped[float | None] = mapped_column(Float, default=None)
    tokens_embedded: Mapped[int] = mapped_column(Integer, default=0)
    embedding_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    search_accuracy: Mapped[float | None] = mapped_column(Float, default=None)
    """Precision over the window's own human feedback. ``None`` where
    nobody gave feedback -- reporting 0.0 for "unmeasured" would look
    like a service returning nothing useful."""
    top_sources: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    top_documents: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    unanswered_queries: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    """The queries that returned nothing, with counts. The most
    actionable output of this whole table: it is a ranked list of
    documents the organization does not have."""
    by_strategy: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    by_source_kind: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)


class RagReport(BaseModel):
    """``rag_reports`` -- one generated report."""

    __tablename__ = "rag_reports"
    __table_args__ = (Index("ix_rag_report_kind", "kind"),)

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


class RagAudit(BaseModel):
    """``rag_audit`` -- the append-only audit trail.

    Append-only by discipline, not by trigger: nothing in this service
    updates or deletes a row here. **Retrieval queries are audited**, and
    that is the point of the table rather than an incidental use -- who
    read which document, and when, is the question an access review
    actually asks.
    """

    __tablename__ = "rag_audit"
    __table_args__ = (
        Index("ix_rag_audit_action", "action"),
        Index("ix_rag_audit_occurred_at", "occurred_at"),
        Index("ix_rag_audit_entity", "entity_type", "entity_id"),
    )

    action: Mapped[AuditAction] = mapped_column(String(32), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(default=None, index=True)
    entity_reference: Mapped[str | None] = mapped_column(String(512), default=None)
    actor_id: Mapped[str | None] = mapped_column(String(128), default=None, index=True)
    actor_type: Mapped[str] = mapped_column(String(32), default="user")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    summary: Mapped[str] = mapped_column(String(512))
    succeeded: Mapped[bool] = mapped_column(Boolean, default=True)
    changes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    context: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64), default=None)
    ip_address: Mapped[str | None] = mapped_column(String(64), default=None)


__all__ = ["IndexingJob", "KnowledgeSource", "RagAudit", "RagReport", "RagStatistic"]
