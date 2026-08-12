"""``document_entities``, ``document_tables``, ``document_forms``,
``document_key_values``, ``document_classifications``,
``document_summaries``, and ``document_translations``.

**Every extracted value records where it came from and how sure the
extractor was.** Not decoration: the whole point of this service is that
a downstream system can decide whether to act on a value automatically or
route it to a person, and it cannot make that decision from the value
alone. A field with no confidence and no provenance is a guess presented
as a fact.
"""

from __future__ import annotations

import uuid

from shared_core.database.base import BaseModel
from sqlalchemy import (
    JSON,
    Boolean,
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
    ClassificationMethod,
    DocumentCategory,
    EntityKind,
    ExtractionMethod,
    FormFieldKind,
    SummaryKind,
)


class DocumentEntity(BaseModel):
    """``document_entities`` -- one thing the document mentions.

    Stored with its character offsets into the version's text, so a
    reviewer can be shown the entity in context rather than in isolation.
    An entity with no offset is unreviewable: "this document mentions
    10.0.0.4" is not something anybody can confirm without finding it.
    """

    __tablename__ = "document_entities"
    __table_args__ = (
        Index("ix_di_entity_document", "document_id"),
        Index("ix_di_entity_kind", "entity_kind"),
        Index("ix_di_entity_value", "normalized_value"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    document_page_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_pages.id", ondelete="SET NULL"), default=None, index=True
    )
    entity_kind: Mapped[EntityKind] = mapped_column(String(24), index=True)
    custom_kind: Mapped[str | None] = mapped_column(String(64), default=None)
    """The organization's own label, when ``entity_kind`` is ``CUSTOM``.
    Kept in its own column rather than overloading the enum, so adding a
    tenant's entity type never requires a migration."""
    value: Mapped[str] = mapped_column(String(2_048))
    normalized_value: Mapped[str] = mapped_column(String(2_048), index=True)
    """The canonical form: lowercased hostname, E.164 phone, ISO date.
    Indexed and matched on, because "Acme Corp." and "ACME CORP" are one
    organization and a filter on the raw value finds one of them."""
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        String(16), default=ExtractionMethod.PATTERN
    )
    start_offset: Mapped[int] = mapped_column(Integer, default=0)
    end_offset: Mapped[int] = mapped_column(Integer, default=0)
    page_number: Mapped[int | None] = mapped_column(Integer, default=None)
    context: Mapped[str | None] = mapped_column(String(512), default=None)
    """The surrounding sentence. Stored rather than recomputed, because
    the text it was cut from may have been superseded by a later version
    and the reviewer needs what the extractor saw."""
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_by: Mapped[str | None] = mapped_column(String(128), default=None)
    is_redacted: Mapped[bool] = mapped_column(Boolean, default=False)
    entity_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class DocumentTable(BaseModel):
    """``document_tables`` -- one table found in a document.

    The cells live in ``rows`` as a JSON grid rather than in their own
    table. A table is read, exported, and corrected as a whole; splitting
    it into a row per cell would turn every read into a thousand-row join
    and every export into a reassembly that can get the order wrong.
    """

    __tablename__ = "document_tables"
    __table_args__ = (
        Index("ix_di_table_document", "document_id"),
        UniqueConstraint("document_version_id", "sequence", name="uq_di_table_sequence"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    document_page_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_pages.id", ondelete="SET NULL"), default=None, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    caption: Mapped[str | None] = mapped_column(String(512), default=None)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    column_count: Mapped[int] = mapped_column(Integer, default=0)
    headers: Mapped[list[str]] = mapped_column(JSON, default=list)
    rows: Mapped[list[list[str]]] = mapped_column(JSON, default=list)
    has_header_row: Mapped[bool] = mapped_column(Boolean, default=False)
    has_footer_row: Mapped[bool] = mapped_column(Boolean, default=False)
    has_merged_cells: Mapped[bool] = mapped_column(Boolean, default=False)
    """Recorded because a merged cell is where an export silently loses
    information: CSV has no way to express one, so a consumer needs to
    know the flat file is a lossy rendering rather than the table."""
    spans_pages: Mapped[bool] = mapped_column(Boolean, default=False)
    first_page_number: Mapped[int | None] = mapped_column(Integer, default=None)
    last_page_number: Mapped[int | None] = mapped_column(Integer, default=None)
    parent_table_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_tables.id", ondelete="CASCADE"), default=None, index=True
    )
    """A nested table's parent. Nesting is rare and real; flattening it
    would merge two different things into one grid."""
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    cell_confidences: Mapped[list[list[float]]] = mapped_column(JSON, default=list)
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        String(16), default=ExtractionMethod.LAYOUT
    )
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    table_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class DocumentForm(BaseModel):
    """``document_forms`` -- one form detected in a document.

    A form is the container; its fields are ``document_key_values`` rows.
    Separated because a form has its own template match and completeness,
    and a loose key-value pair extracted from prose belongs to no form at
    all.
    """

    __tablename__ = "document_forms"
    __table_args__ = (
        Index("ix_di_form_document", "document_id"),
        UniqueConstraint("document_version_id", "sequence", name="uq_di_form_sequence"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    document_page_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_pages.id", ondelete="SET NULL"), default=None, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str | None] = mapped_column(String(255), default=None)
    template_id: Mapped[uuid.UUID | None] = mapped_column(default=None, index=True)
    template_match_score: Mapped[float | None] = mapped_column(Float, default=None)
    field_count: Mapped[int] = mapped_column(Integer, default=0)
    filled_field_count: Mapped[int] = mapped_column(Integer, default=0)
    completeness: Mapped[float] = mapped_column(Float, default=0.0)
    """Filled fields over expected fields. The number a router acts on:
    a half-completed form is not a form to process, it is one to send
    back."""
    has_signature: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        String(16), default=ExtractionMethod.LAYOUT
    )
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    form_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class DocumentKeyValue(BaseModel):
    """``document_key_values`` -- one label-and-value pair.

    Belongs to a form when one was detected and stands alone when the pair
    came from prose. Both are real: "Serial Number: X41-99" in a paragraph
    is exactly as extractable as the same pair in a form field, and
    requiring a form would discard it.
    """

    __tablename__ = "document_key_values"
    __table_args__ = (
        Index("ix_di_kv_document", "document_id"),
        Index("ix_di_kv_key", "normalized_key"),
        Index("ix_di_kv_form", "document_form_id"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    document_form_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_forms.id", ondelete="CASCADE"), default=None, index=True
    )
    document_page_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_pages.id", ondelete="SET NULL"), default=None, index=True
    )
    key: Mapped[str] = mapped_column(String(512))
    normalized_key: Mapped[str] = mapped_column(String(512), index=True)
    """Lowercased and stripped of punctuation, so "Serial No.",
    "serial no", and "SERIAL NO:" are one key. Filters are written
    against this; a filter on the raw key matches one document's spelling
    and misses the next."""
    value: Mapped[str | None] = mapped_column(Text, default=None)
    """``None`` for a field that exists and is empty -- an unticked
    checkbox, a blank signature line. Distinct from the row not existing,
    which means the field was never on the form."""
    field_kind: Mapped[FormFieldKind] = mapped_column(String(16), default=FormFieldKind.TEXT)
    is_checked: Mapped[bool | None] = mapped_column(Boolean, default=None)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    key_confidence: Mapped[float | None] = mapped_column(Float, default=None)
    """Confidence in the *label*, separate from the value. Reading the
    value correctly under the wrong label is the failure mode that puts a
    serial number into a date field, and one combined score cannot
    express it."""
    page_number: Mapped[int | None] = mapped_column(Integer, default=None)
    left: Mapped[float | None] = mapped_column(Float, default=None)
    top: Mapped[float | None] = mapped_column(Float, default=None)
    width: Mapped[float | None] = mapped_column(Float, default=None)
    height: Mapped[float | None] = mapped_column(Float, default=None)
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        String(16), default=ExtractionMethod.LAYOUT
    )
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    corrected_value: Mapped[str | None] = mapped_column(Text, default=None)
    """What a reviewer changed it to, kept beside the original rather
    than overwriting it. The pair is the only measurement of how often
    the extractor is wrong, which is the number that says whether it is
    improving."""
    corrected_by: Mapped[str | None] = mapped_column(String(128), default=None)


class DocumentClassification(BaseModel):
    """``document_classifications`` -- one label assigned to a document.

    A row per label rather than a column on ``documents``, because
    classification is multi-label: a document that is both a policy and a
    certificate is genuinely both, and forcing one loses whichever the
    router needed.
    """

    __tablename__ = "document_classifications"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id", "category", "custom_category", name="uq_di_classification"
        ),
        Index("ix_di_classification_document", "document_id"),
        Index("ix_di_classification_category", "category"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[DocumentCategory] = mapped_column(String(24), index=True)
    custom_category: Mapped[str] = mapped_column(String(128), default="")
    """The organization's own label, empty when the built-in category is
    the whole answer. Part of the unique key rather than nullable,
    because PostgreSQL treats NULLs as distinct and a nullable column
    here would let the same label be assigned repeatedly."""
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    method: Mapped[ClassificationMethod] = mapped_column(
        String(16), default=ClassificationMethod.RULE
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    rationale: Mapped[str | None] = mapped_column(String(512), default=None)
    """Which rule or which terms decided it. A classification nobody can
    explain is one nobody can correct -- and correcting the rule is the
    only thing that fixes the next thousand documents."""
    matched_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
    routed_to: Mapped[str | None] = mapped_column(String(255), default=None)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_by: Mapped[str | None] = mapped_column(String(128), default=None)


class DocumentSummary(BaseModel):
    """``document_summaries`` -- one summary of one version.

    Several per document at once, one per kind: an executive summary and
    a technical one answer different questions for different readers.
    """

    __tablename__ = "document_summaries"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id", "summary_kind", "section_path", name="uq_di_summary_kind"
        ),
        Index("ix_di_summary_document", "document_id"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    summary_kind: Mapped[SummaryKind] = mapped_column(String(16), index=True)
    section_path: Mapped[str] = mapped_column(String(512), default="")
    """Which section this summarises, empty for a whole-document summary.
    Part of the unique key so a section summary per section is possible
    without each one displacing the last."""
    content: Mapped[str] = mapped_column(Text)
    sentence_count: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    compression_ratio: Mapped[float | None] = mapped_column(Float, default=None)
    source_sentence_indices: Mapped[list[int]] = mapped_column(JSON, default=list)
    """Which sentences of the original an extractive summary selected.
    This is what makes the summary checkable: every sentence in it can be
    traced to one in the document, and an abstractive summary that cannot
    do that is a claim rather than a citation."""
    is_extractive: Mapped[bool] = mapped_column(Boolean, default=True)
    model_used: Mapped[str | None] = mapped_column(String(128), default=None)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    generated_by: Mapped[str | None] = mapped_column(String(128), default=None)


class DocumentTranslation(BaseModel):
    """``document_translations`` -- one document rendered in one language.

    Stored rather than generated on read: a translation is expensive, and
    a reviewer correcting one needs the correction to persist rather than
    be regenerated away on the next request.
    """

    __tablename__ = "document_translations"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id", "target_language", name="uq_di_translation_language"
        ),
        Index("ix_di_translation_document", "document_id"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    source_language: Mapped[str] = mapped_column(String(16))
    target_language: Mapped[str] = mapped_column(String(16), index=True)
    content: Mapped[str] = mapped_column(Text)
    detected_source: Mapped[bool] = mapped_column(Boolean, default=False)
    """Whether the source language was detected rather than declared. A
    detected language that was wrong explains a translation that reads as
    nonsense, and without this flag that failure looks like a bad
    translator."""
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    glossary_terms_applied: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    """Terms held to a required rendering. An infrastructure document's
    "host", "node", and "cluster" have to survive translation intact, and
    a general translator will happily paraphrase them into something a
    downstream match will miss."""
    preserved_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
    engine: Mapped[str | None] = mapped_column(String(64), default=None)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    translated_by: Mapped[str | None] = mapped_column(String(128), default=None)


__all__ = [
    "DocumentClassification",
    "DocumentEntity",
    "DocumentForm",
    "DocumentKeyValue",
    "DocumentSummary",
    "DocumentTable",
    "DocumentTranslation",
]
