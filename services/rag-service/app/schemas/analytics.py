"""Request and response schemas for statistics, reports, and sources."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    ChunkStrategy,
    ClassificationLevel,
    ReportFormat,
    ReportKind,
    ReportStatus,
    SourceKind,
    SyncStatus,
)


class StatisticResponse(BaseModel):
    """One rolled-up window."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    window_start: datetime
    window_end: datetime
    documents_total: int
    documents_indexed: int
    documents_failed: int
    chunks_total: int
    vectors_total: int
    index_size_bytes: int
    retrieval_count: int
    retrievals_empty: int
    retrievals_denied: int
    average_latency_ms: float | None
    average_result_count: float | None
    tokens_embedded: int
    embedding_cost_usd: float
    search_accuracy: float | None
    """``null`` where nobody gave feedback. Not ``0.0`` -- that would read
    as a service returning nothing useful rather than one nobody has
    judged."""
    top_sources: list[dict[str, object]]
    top_documents: list[dict[str, object]]
    unanswered_queries: list[dict[str, object]]
    by_strategy: dict[str, int]
    by_source_kind: dict[str, int]
    created_at: datetime


class ReportRequest(BaseModel):
    """``POST /rag/reports`` -- generate one report."""

    model_config = ConfigDict(extra="forbid")

    kind: ReportKind
    report_format: ReportFormat = ReportFormat.JSON
    since: datetime | None = None
    title: str | None = Field(default=None, max_length=255)


class ReportResponse(BaseModel):
    """One generated report."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    kind: ReportKind
    report_format: ReportFormat
    title: str
    status: ReportStatus
    content: dict[str, object]
    row_count: int | None
    generated_by: str | None
    generated_at: datetime | None
    duration_ms: float | None
    error: str | None
    created_at: datetime


class SourceCreateRequest(BaseModel):
    """``POST /rag/sources`` -- register a knowledge source.

    ``credential_reference`` is a pointer into whatever secret store the
    deployment uses -- never a credential. A source row is returned by
    this API, logged, and included in reports; a password in it would be
    disclosed by all three.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    source_kind: SourceKind
    description: str | None = Field(default=None, max_length=4_000)
    uri: str | None = Field(default=None, max_length=2_048)
    credential_reference: str | None = Field(default=None, max_length=255)
    sync_enabled: bool = False
    sync_interval_seconds: int = Field(default=3_600, ge=60, le=2_592_000)
    default_classification: ClassificationLevel = ClassificationLevel.INTERNAL
    default_tags: list[str] = Field(default_factory=list, max_length=64)
    allowed_roles: list[str] = Field(default_factory=list, max_length=64)
    chunk_size: int | None = Field(default=None, ge=1, le=100_000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=99_999)
    chunk_strategy: ChunkStrategy | None = None
    configuration: dict[str, object] = Field(default_factory=dict, max_length=64)


class SourceUpdateRequest(BaseModel):
    """``PUT /rag/sources/{id}`` -- reconfigure a source.

    Slug and kind are absent: both are identity. Changing the slug orphans
    the schedule that referenced it, and changing the kind reinterprets
    every document already imported under it.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4_000)
    uri: str | None = Field(default=None, max_length=2_048)
    credential_reference: str | None = Field(default=None, max_length=255)
    is_enabled: bool | None = None
    sync_enabled: bool | None = None
    sync_interval_seconds: int | None = Field(default=None, ge=60, le=2_592_000)
    default_classification: ClassificationLevel | None = None
    default_tags: list[str] | None = Field(default=None, max_length=64)
    allowed_roles: list[str] | None = Field(default=None, max_length=64)
    chunk_size: int | None = Field(default=None, ge=1, le=100_000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=99_999)
    chunk_strategy: ChunkStrategy | None = None
    configuration: dict[str, object] | None = Field(default=None, max_length=64)


class SourceResponse(BaseModel):
    """One knowledge source."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    slug: str
    name: str
    description: str | None
    source_kind: SourceKind
    uri: str | None
    credential_reference: str | None
    is_enabled: bool
    sync_enabled: bool
    sync_interval_seconds: int
    sync_status: SyncStatus
    last_synced_at: datetime | None
    last_sync_cursor: str | None
    last_sync_error: str | None
    default_classification: ClassificationLevel
    default_tags: list[str]
    allowed_roles: list[str]
    chunk_size: int | None
    chunk_overlap: int | None
    chunk_strategy: str | None
    document_count: int
    configuration: dict[str, object]
    created_at: datetime
    updated_at: datetime


class SyncReportRequest(BaseModel):
    """``POST /rag/sources/{id}/sync`` -- what a connector fetched.

    The seam between this service and whatever actually talks to
    Confluence, SharePoint, or S3. None of those clients ship here, and
    this is where one reports its results.
    """

    model_config = ConfigDict(extra="forbid")

    documents_seen: int = Field(default=0, ge=0)
    documents_ingested: int = Field(default=0, ge=0)
    documents_failed: int = Field(default=0, ge=0)
    cursor: str | None = Field(default=None, max_length=512)
    error: str | None = Field(default=None, max_length=4_000)


class AuditResponse(BaseModel):
    """One audit entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    action: str
    entity_type: str
    entity_id: UUID | None
    entity_reference: str | None
    actor_id: str | None
    occurred_at: datetime
    summary: str | None
    succeeded: bool


__all__ = [
    "AuditResponse",
    "ReportRequest",
    "ReportResponse",
    "SourceCreateRequest",
    "SourceResponse",
    "SourceUpdateRequest",
    "StatisticResponse",
    "SyncReportRequest",
]
