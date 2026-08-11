"""Request and response schemas for the document surface.

**No response schema carries a document's full text.** A document body
belongs to ``GET /rag/documents/{id}/content``, which the caller asks for
explicitly; putting it on the list response would mean every listing of a
thousand documents ships a thousand documents' worth of text, and every
one of those payloads lands in a log, a proxy cache, and a browser's
history.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    ChunkKind,
    ChunkStrategy,
    ClassificationLevel,
    DocumentStatus,
    SourceKind,
)

MAX_UPLOAD_BASE64_LENGTH = 69_910_700
"""Base64 inflates by 4/3, so this is the 50 MiB parse limit expressed in
encoded characters. Bounded in the schema so an oversized upload is
rejected before it is decoded into memory -- rejecting it afterwards
still requires holding it."""


class DocumentIngestRequest(BaseModel):
    """``POST /rag/documents`` -- ingest one document.

    Content arrives base64-encoded in JSON rather than as multipart. The
    tradeoff is a third more bytes on the wire in exchange for one
    request shape for uploads and connector pushes alike, and for content
    that survives a JSON round trip byte for byte -- a PDF sent as text
    does not.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=512)
    content_base64: str = Field(min_length=1, max_length=MAX_UPLOAD_BASE64_LENGTH)
    filename: str | None = Field(default=None, max_length=512)
    content_type: str | None = Field(default=None, max_length=128)
    source_kind: SourceKind | None = None
    external_id: str | None = Field(default=None, max_length=512)
    knowledge_source_id: UUID | None = None
    classification: ClassificationLevel = ClassificationLevel.INTERNAL
    allowed_roles: list[str] = Field(default_factory=list, max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=64)
    project_scope_id: UUID | None = None
    source_uri: str | None = Field(default=None, max_length=2_048)
    chunk_strategy: ChunkStrategy = ChunkStrategy.HYBRID
    chunk_size: int | None = Field(default=None, ge=1, le=100_000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=99_999)

    @field_validator("allowed_roles", "tags")
    @classmethod
    def _clean(cls, value: list[str]) -> list[str]:
        """Drop blanks and duplicates, preserving order.

        Order is preserved rather than sorted because tags are displayed
        in the order somebody chose, and a set would silently reorder
        them on every round trip.
        """
        seen: dict[str, None] = {}
        for item in value:
            trimmed = item.strip()
            if trimmed:
                seen.setdefault(trimmed, None)
        return list(seen)


class DocumentUpdateRequest(BaseModel):
    """``PUT /rag/documents/{id}`` -- change descriptive and access fields.

    Content is absent deliberately. Text comes from a parse of the
    original bytes, and editing it in place would break the guarantee
    versions exist for: that what was indexed can still be shown as it
    was. Re-ingest to change content.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = Field(default=None, max_length=4_000)
    classification: ClassificationLevel | None = None
    allowed_roles: list[str] | None = Field(default=None, max_length=64)
    tags: list[str] | None = Field(default=None, max_length=64)
    owner_id: str | None = Field(default=None, max_length=128)
    expires_at: datetime | None = None
    metadata: dict[str, str] | None = Field(default=None, max_length=64)


class DocumentResponse(BaseModel):
    """One document, without its text."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    knowledge_source_id: UUID | None
    external_id: str | None
    title: str
    description: str | None
    source_kind: SourceKind
    status: DocumentStatus
    classification: ClassificationLevel
    project_scope_id: UUID | None
    allowed_roles: list[str]
    tags: list[str]
    language: str
    content_type: str | None
    byte_size: int
    checksum: str | None
    source_uri: str | None
    current_version_number: int | None
    chunk_count: int
    token_count: int
    retrieval_count: int
    last_retrieved_at: datetime | None
    last_indexed_at: datetime | None
    indexed_checksum: str | None
    expires_at: datetime | None
    owner_id: str | None
    ingested_by: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class IngestionResponse(BaseModel):
    """What one ingestion produced.

    ``blocked`` and ``findings`` are returned rather than raising, because
    a document refused by scanning is a *result* the caller has to act on
    -- a 4xx with a bare message would not tell them which finding to fix.
    """

    document: DocumentResponse
    version_number: int | None = None
    chunk_count: int = 0
    unchanged: bool = False
    blocked: bool = False
    findings: list[dict[str, object]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentVersionResponse(BaseModel):
    """One parse of one document, including its text."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    version_number: int
    content: str
    checksum: str
    byte_size: int
    token_count: int
    page_count: int | None
    parser: str | None
    is_current: bool
    chunk_count: int
    extracted_metadata: dict[str, object]
    warnings: list[str]
    created_at: datetime


class DocumentChunkResponse(BaseModel):
    """One retrievable unit of text."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    document_version_id: UUID
    sequence: int
    content: str
    chunk_kind: ChunkKind
    strategy: ChunkStrategy
    token_count: int
    character_count: int
    start_offset: int
    end_offset: int
    page_number: int | None
    section_path: str | None
    heading: str | None
    overlap_tokens: int
    is_embedded: bool
    embedding_model: str | None


class IndexRequest(BaseModel):
    """``POST /rag/index`` -- index one document now, or queue a sweep."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID | None = None
    knowledge_source_id: UUID | None = None
    force: bool = False
    """Re-embed even unchanged chunks. For recovering from a vector store
    that lost data: the content-hash check would otherwise skip exactly
    the chunks that need rewriting, since the chunks are fine and only
    the vectors are missing."""
    priority: int = Field(default=100, ge=1, le=1_000)


class ReindexRequest(BaseModel):
    """``POST /rag/reindex`` -- queue a full or incremental reindex."""

    model_config = ConfigDict(extra="forbid")

    full: bool = False
    """A full reindex re-embeds everything and is charged for accordingly;
    an incremental one covers only documents whose content changed since
    they were last indexed."""
    knowledge_source_id: UUID | None = None
    priority: int = Field(default=100, ge=1, le=1_000)


class IndexResultResponse(BaseModel):
    """What indexing one document produced."""

    document_id: UUID
    embedded: int = 0
    reused: int = 0
    skipped: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    error: str | None = None


class IndexingJobResponse(BaseModel):
    """One queued or finished indexing job."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    document_id: UUID | None
    knowledge_source_id: UUID | None
    kind: str
    status: str
    priority: int
    scheduled_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    attempts: int
    max_attempts: int
    documents_total: int
    documents_succeeded: int
    documents_failed: int
    vectors_created: int
    tokens_embedded: int
    cost_usd: float
    duration_ms: float | None
    requested_by: str | None
    error: str | None


__all__ = [
    "MAX_UPLOAD_BASE64_LENGTH",
    "DocumentChunkResponse",
    "DocumentIngestRequest",
    "DocumentResponse",
    "DocumentUpdateRequest",
    "DocumentVersionResponse",
    "IndexRequest",
    "IndexResultResponse",
    "IndexingJobResponse",
    "IngestionResponse",
    "ReindexRequest",
]
