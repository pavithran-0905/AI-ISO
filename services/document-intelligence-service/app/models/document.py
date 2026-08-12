"""``documents``, ``document_versions``, ``document_pages``, and
``document_layouts``.

**The page is the unit of this service**, in a way it is not for
retrieval. OCR confidence, layout regions, rotation, and resolution are
all per-page facts, and a document-level average of any of them hides the
one bad page that is the reason a human is looking. Pages hang off the
version rather than the document, so re-OCR'ing under a better engine
produces a new set without destroying what the last extraction was
actually derived from.
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
    DocumentFormat,
    DocumentStatus,
    LayoutRegionKind,
    OcrEngineKind,
    OcrQuality,
)


class Document(BaseModel):
    """``documents`` -- one ingested document's stable identity.

    Identity is ``(organization_id, external_id)`` where the caller
    supplied one, so re-importing the same upstream document updates it
    rather than multiplying it.
    """

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_id", name="uq_di_document_external_id"),
        Index("ix_di_document_status", "status"),
        Index("ix_di_document_format", "document_format"),
        Index("ix_di_document_checksum", "checksum"),
    )

    external_id: Mapped[str | None] = mapped_column(String(512), default=None)
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    filename: Mapped[str | None] = mapped_column(String(512), default=None)
    document_format: Mapped[DocumentFormat] = mapped_column(String(16), index=True)
    content_type: Mapped[str | None] = mapped_column(String(128), default=None)
    status: Mapped[DocumentStatus] = mapped_column(
        String(24), default=DocumentStatus.UPLOADED, index=True
    )
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str | None] = mapped_column(String(128), default=None, index=True)
    """SHA-256 of the raw bytes. Both the idempotency key for re-import
    and the first pass of duplicate detection -- two documents with the
    same checksum are the same document however they were named."""
    storage_bucket: Mapped[str | None] = mapped_column(String(128), default=None)
    storage_key: Mapped[str | None] = mapped_column(String(1_024), default=None)
    """Where the original bytes live. Kept because every stage after
    parsing may need to go back to them: a better OCR engine, a
    re-extraction under a new template, or a reviewer who wants to see
    the page as it was scanned."""
    source_uri: Mapped[str | None] = mapped_column(String(2_048), default=None)
    language: Mapped[str | None] = mapped_column(String(16), default=None)
    """Detected, not assumed. ``None`` until something has actually
    looked -- defaulting to English would make every translation decision
    wrong for the documents that most need one."""
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    current_version_number: Mapped[int | None] = mapped_column(Integer, default=None)
    requires_ocr: Mapped[bool] = mapped_column(Boolean, default=False)
    """Set once the text layer has actually been tried and found empty.
    A format-level guess would route every PDF through OCR."""
    ocr_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    mean_ocr_confidence: Mapped[float | None] = mapped_column(Float, default=None)
    lowest_page_confidence: Mapped[float | None] = mapped_column(Float, default=None)
    """The worst page, kept alongside the mean. A forty-page scan
    averaging 0.94 with one page at 0.3 is a document with an unreadable
    page, and the mean is precisely the number that hides it."""
    overall_confidence: Mapped[float | None] = mapped_column(Float, default=None)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    review_reason: Mapped[str | None] = mapped_column(String(512), default=None)
    """Why a human is needed, in words. "Requires review" with no reason
    makes the reviewer re-derive the machine's doubt before they can act
    on it."""
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    processing_duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), default=None, index=True
    )
    """The document this one duplicates. A pointer rather than a deletion:
    the upload really happened, somebody may have referenced it, and the
    right answer to "why is this not being processed?" is a link to the
    original."""
    archive_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), default=None, index=True
    )
    """Set on documents extracted from a ZIP, pointing at the archive.
    Deleting the archive takes its members with it, which is what
    somebody deleting an archive means."""
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    document_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    owner_id: Mapped[str | None] = mapped_column(String(128), default=None)
    uploaded_by: Mapped[str | None] = mapped_column(String(128), default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)


class DocumentVersion(BaseModel):
    """``document_versions`` -- one immutable processing pass.

    Holds the extracted text and the settings it was produced under. A new
    version is written whenever the content changes or the document is
    reprocessed, so "what text did that extraction actually see?" stays
    answerable after a better engine has replaced it -- which is the whole
    basis of being able to audit an approval.
    """

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_di_version_number"),
        Index("ix_di_version_current", "is_current"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(128), index=True)
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    parser: Mapped[str | None] = mapped_column(String(64), default=None)
    ocr_engine: Mapped[OcrEngineKind] = mapped_column(String(16), default=OcrEngineKind.NONE)
    ocr_languages: Mapped[list[str]] = mapped_column(JSON, default=list)
    """Which languages OCR was run under. Recorded because running an
    English model over a German scan produces confident nonsense, and the
    only way to recognise that later is to know what was asked for."""
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_reprocess: Mapped[bool] = mapped_column(Boolean, default=False)
    """Whether this version came from reprocessing rather than new
    content. The distinction decides whether downstream extraction can be
    reused or has to be redone."""
    settings_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    """The thresholds and engine settings in force for this pass. Without
    it, a result that looks wrong today cannot be told apart from one
    that was right under yesterday's configuration."""
    extracted_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    produced_by: Mapped[str | None] = mapped_column(String(128), default=None)


class DocumentPage(BaseModel):
    """``document_pages`` -- one page of one version.

    The row a reviewer is actually looking at, and the level every OCR and
    layout fact is recorded at.
    """

    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("document_version_id", "page_number", name="uq_di_page_number"),
        Index("ix_di_page_document", "document_id"),
        Index("ix_di_page_quality", "ocr_quality"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int] = mapped_column(Integer)
    """1-based, matching how everyone refers to a page. A 0-based page
    number in a citation is an off-by-one nobody notices until they open
    the document."""
    content: Mapped[str] = mapped_column(Text, default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    character_count: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[float | None] = mapped_column(Float, default=None)
    height: Mapped[float | None] = mapped_column(Float, default=None)
    rotation_degrees: Mapped[int] = mapped_column(Integer, default=0)
    """How far the page was rotated to read it. Recorded because a page
    that needed 90 degrees of correction is a scanning problem somebody
    should fix at the scanner, not one to keep correcting per document."""
    resolution_dpi: Mapped[int | None] = mapped_column(Integer, default=None)
    is_scanned: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_engine: Mapped[OcrEngineKind] = mapped_column(String(16), default=OcrEngineKind.NONE)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, default=None)
    ocr_quality: Mapped[OcrQuality | None] = mapped_column(String(16), default=None, index=True)
    ocr_duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    word_confidences: Mapped[list[float]] = mapped_column(JSON, default=list)
    """Per-word confidence, kept so a reviewer can be shown *which* words
    are doubtful rather than told the page is. A page-level number cannot
    highlight anything."""
    detected_language: Mapped[str | None] = mapped_column(String(16), default=None)
    column_count: Mapped[int] = mapped_column(Integer, default=1)
    has_tables: Mapped[bool] = mapped_column(Boolean, default=False)
    has_images: Mapped[bool] = mapped_column(Boolean, default=False)
    has_signatures: Mapped[bool] = mapped_column(Boolean, default=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)


class DocumentLayout(BaseModel):
    """``document_layouts`` -- one detected region on one page.

    Regions carry their bounding box and their place in the reading order,
    because that ordering is what turns a two-column scan into prose
    somebody can read rather than interleaved half-sentences.
    """

    __tablename__ = "document_layouts"
    __table_args__ = (
        Index("ix_di_layout_page", "document_page_id"),
        Index("ix_di_layout_kind", "region_kind"),
        UniqueConstraint("document_page_id", "reading_order", name="uq_di_layout_reading_order"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    document_page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_pages.id", ondelete="CASCADE"), index=True
    )
    region_kind: Mapped[LayoutRegionKind] = mapped_column(
        String(16), default=LayoutRegionKind.PARAGRAPH, index=True
    )
    reading_order: Mapped[int] = mapped_column(Integer, default=0)
    """0-based position in the order a human reads the page. Unique per
    page: two regions claiming the same slot means the ordering is
    ambiguous, and an ambiguous reading order silently scrambles a
    multi-column document."""
    content: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    left: Mapped[float | None] = mapped_column(Float, default=None)
    top: Mapped[float | None] = mapped_column(Float, default=None)
    width: Mapped[float | None] = mapped_column(Float, default=None)
    height: Mapped[float | None] = mapped_column(Float, default=None)
    """Bounding box in page coordinates, all four nullable together: a
    region derived from a text layer has no geometry, and inventing one
    would put a highlight over the wrong part of the page."""
    column_index: Mapped[int] = mapped_column(Integer, default=0)
    heading_level: Mapped[int | None] = mapped_column(Integer, default=None)
    section_path: Mapped[str | None] = mapped_column(String(1_024), default=None)
    region_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


__all__ = ["Document", "DocumentLayout", "DocumentPage", "DocumentVersion"]
