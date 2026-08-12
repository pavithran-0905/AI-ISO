"""``documents``, ``document_versions``, ``document_chunks``, and
``document_metadata``.

**A chunk belongs to a document *version*, not to a document.** Re-parsing
or re-chunking a document produces a new set of chunks, and the old ones
have to stay reachable until the new index is live -- otherwise every
reindex is a window during which retrieval returns nothing. Hanging
chunks off the version is what makes an incremental reindex atomic from
a reader's point of view.
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
    ChunkKind,
    ChunkStrategy,
    ClassificationLevel,
    DocumentStatus,
    SourceKind,
)


class Document(BaseModel):
    """``documents`` -- one ingested document's stable identity.

    Identity is ``(organization_id, external_id)`` where the caller
    supplied one, so re-importing the same upstream document updates it
    rather than creating a duplicate. That is what makes source
    synchronisation idempotent: a Confluence page re-fetched on every
    sweep must not multiply.
    """

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_id", name="uq_document_external_id"),
        Index("ix_document_status", "status"),
        Index("ix_document_classification", "classification"),
        Index("ix_document_source_kind", "source_kind"),
    )

    knowledge_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="SET NULL"), default=None, index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(512), default=None)
    """The upstream system's own identifier -- a Confluence page id, a
    git path, an S3 key. ``None`` for a direct upload, which is why the
    unique constraint tolerates it: PostgreSQL treats NULLs as distinct,
    so unlimited uploads coexist while imports stay deduplicated."""
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    source_kind: Mapped[SourceKind] = mapped_column(String(24), index=True)
    status: Mapped[DocumentStatus] = mapped_column(
        String(16), default=DocumentStatus.PENDING, index=True
    )
    classification: Mapped[ClassificationLevel] = mapped_column(
        String(16), default=ClassificationLevel.INTERNAL, index=True
    )
    """Defaults to ``INTERNAL``, never ``PUBLIC``. A document whose
    sensitivity nobody declared is not public knowledge, and defaulting
    the other way would disclose by omission."""
    project_scope_id: Mapped[uuid.UUID | None] = mapped_column(default=None, index=True)
    """Project isolation, alongside the organization scope every query
    already carries. ``None`` means organization-wide."""
    allowed_roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    """Empty means "any role in the organization". Non-empty restricts
    retrieval to callers holding one of these."""
    allowed_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(16), default="en")
    content_type: Mapped[str | None] = mapped_column(String(128), default=None)
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str | None] = mapped_column(String(128), default=None, index=True)
    """SHA-256 of the raw bytes. The cheapest possible answer to "has
    this actually changed?" during a sync sweep -- without it every
    incremental sync re-parses and re-embeds every unchanged document,
    which is the single largest avoidable cost in this service."""
    storage_bucket: Mapped[str | None] = mapped_column(String(128), default=None)
    storage_key: Mapped[str | None] = mapped_column(String(1_024), default=None)
    """Where the original bytes live in object storage. The parsed text
    is in ``document_versions``; the original is kept so a re-parse with
    a better parser never requires re-fetching from upstream."""
    source_uri: Mapped[str | None] = mapped_column(String(2_048), default=None)
    current_version_number: Mapped[int | None] = mapped_column(Integer, default=None)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    retrieval_count: Mapped[int] = mapped_column(Integer, default=0)
    last_retrieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    indexed_checksum: Mapped[str | None] = mapped_column(String(128), default=None)
    """The checksum that was actually indexed. Differing from
    ``checksum`` is precisely "this document has changed since it was
    last indexed", which is what an incremental sweep selects on."""
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    owner_id: Mapped[str | None] = mapped_column(String(128), default=None)
    ingested_by: Mapped[str | None] = mapped_column(String(128), default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)


class DocumentVersion(BaseModel):
    """``document_versions`` -- one immutable parse of one document.

    Holds the *extracted text*, not the original bytes. A new version is
    written whenever the upstream content changes or the document is
    re-parsed, so "what text was actually indexed when that answer was
    generated?" stays answerable after the source has moved on -- which
    is the whole basis of citation traceability.
    """

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_version_number"),
        Index("ix_document_version_current", "is_current"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    """Monotonic per document. Integers rather than semver: nobody
    hand-authors a document version, so there is no major/minor decision
    to express -- it is a sequence."""
    content: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(128), index=True)
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int | None] = mapped_column(Integer, default=None)
    parser: Mapped[str | None] = mapped_column(String(64), default=None)
    """Which parser produced this text. Recorded because a re-parse under
    a different parser is a legitimate reason for the text to change
    without the source having changed at all, and without this the diff
    looks like upstream drift."""
    parse_duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    extracted_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    """Title, author, creation date, page labels -- whatever the format
    itself carried. Kept apart from ``document_metadata``, which is what
    a *human or a rule* asserted about the document."""
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    authored_by: Mapped[str | None] = mapped_column(String(128), default=None)
    """Who asked for this parse, as a caller identifier string.

    Named apart from ``AuditMixin.created_by`` deliberately: that column is
    a ``UUID``, and redefining it as a ``str`` here would break the
    substitutability the mixin exists to provide -- the same defect
    prompt-management-service carried on ``PromptVersion``. Only MyPy
    finds this; nothing at runtime objects until something reads the
    column expecting a UUID."""


class DocumentChunk(BaseModel):
    """``document_chunks`` -- one retrievable unit of text.

    The row a retrieval actually returns. Carries enough positional
    information (``sequence``, ``start_offset``, ``page_number``,
    ``section_path``) to build a citation that a human can follow back to
    a specific place in the original -- a citation that only names the
    document is not evidence, it is a gesture at evidence.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_version_id", "sequence", name="uq_chunk_sequence"),
        Index("ix_chunk_document", "document_id"),
        Index("ix_chunk_kind", "chunk_kind"),
        Index("ix_chunk_embedded", "is_embedded"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    chunk_kind: Mapped[ChunkKind] = mapped_column(String(16), default=ChunkKind.TEXT, index=True)
    strategy: Mapped[ChunkStrategy] = mapped_column(String(24), default=ChunkStrategy.FIXED_SIZE)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    character_count: Mapped[int] = mapped_column(Integer, default=0)
    start_offset: Mapped[int] = mapped_column(Integer, default=0)
    end_offset: Mapped[int] = mapped_column(Integer, default=0)
    page_number: Mapped[int | None] = mapped_column(Integer, default=None)
    section_path: Mapped[str | None] = mapped_column(String(1_024), default=None)
    """The heading trail this chunk sits under, e.g.
    ``"Operations > Backups > Restore"``. What turns "page 14" into a
    reference someone can actually act on."""
    heading: Mapped[str | None] = mapped_column(String(512), default=None)
    overlap_tokens: Mapped[int] = mapped_column(Integer, default=0)
    is_embedded: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    """Denormalised from ``embedding_vectors`` so the indexing sweep can
    select work with one indexed predicate instead of an anti-join
    against a table with a row per chunk per model."""
    embedding_model: Mapped[str | None] = mapped_column(String(128), default=None)
    entity_keys: Mapped[list[str]] = mapped_column(JSON, default=list)
    """Graph node keys mentioned in this chunk, resolved at ingestion.
    The join between the vector world and the knowledge graph -- without
    it, GraphRAG expansion would have to re-extract entities on every
    query."""
    chunk_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class DocumentMetadata(BaseModel):
    """``document_metadata`` -- one asserted fact about a document.

    A row per key rather than a JSON blob on ``documents``, because these
    are *filterable*: "every document where ``department = finance``" is
    a metadata filter on retrieval, and that has to be an indexed
    equality on a column, not a scan of a JSON object.
    """

    __tablename__ = "document_metadata"
    __table_args__ = (
        UniqueConstraint("document_id", "key", name="uq_document_metadata_key"),
        Index("ix_document_metadata_key_value", "key", "value"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(128))
    value: Mapped[str] = mapped_column(String(1_024))
    """Stored as text even for numbers and dates. A metadata filter is an
    equality or set-membership test in practice, and one column that
    always compares the same way beats three nullable typed columns that
    each need their own filter path."""
    value_type: Mapped[str] = mapped_column(String(16), default="string")
    is_extracted: Mapped[bool] = mapped_column(Boolean, default=False)
    """Whether the parser found this or a human asserted it. An extracted
    value can be overwritten by the next parse; an asserted one must
    not be."""
    is_filterable: Mapped[bool] = mapped_column(Boolean, default=True)


__all__ = ["Document", "DocumentChunk", "DocumentMetadata", "DocumentVersion"]
