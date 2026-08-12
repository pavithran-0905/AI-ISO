"""Request and response schemas for the document endpoints.

**No schema accepts an organization id.** It comes from the caller's
verified token and from nowhere else; a field here would let any caller
name any tenant, and every repository in this service scopes on the value
it is handed.

**Confidence is optional in every response.** ``None`` means nothing
scored that document, which is a different fact from a document scored at
zero -- and a schema declaring ``float`` with a zero default would erase
the distinction on the way out of the service.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    DocumentCategory,
    DocumentFormat,
    DocumentStatus,
    EntityKind,
    ProcessingStage,
    ReportFormat,
    ReportKind,
    ReviewDecision,
    ReviewStatus,
    SummaryKind,
    TableExportFormat,
)

MAX_TITLE_LENGTH = 512
MAX_TAGS = 32
MAX_PAGE_SIZE = 200


class _Base(BaseModel):
    """Shared configuration for every schema here."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    """``extra="forbid"`` on purpose: a client sending
    ``organization_id`` in a body should get a clear rejection rather than
    have the field silently ignored and quietly operate on its own tenant
    while believing it named another."""


# ---- documents ---------------------------------------------------------------------


class DocumentUploadRequest(_Base):
    """Metadata accompanying an uploaded document.

    The bytes arrive as a multipart file, not in this body: base64 in JSON
    inflates a 50 MB scan to 67 MB and holds all of it in memory twice.
    """

    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    tags: list[str] = Field(default_factory=list, max_length=MAX_TAGS)
    stages: list[ProcessingStage] | None = Field(
        default=None,
        description=(
            "Stages to run. Parsing is always added, since every other stage "
            "reads what it produces."
        ),
    )
    priority: int = Field(default=100, ge=1, le=1000)

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, value: list[str]) -> list[str]:
        """Drop blanks and duplicates, preserving order."""
        seen: dict[str, None] = {}
        for tag in value:
            cleaned = tag.strip()
            if cleaned:
                seen.setdefault(cleaned, None)
        return list(seen)


class DocumentUpdateRequest(_Base):
    """Fields a caller may change on an existing document.

    Deliberately narrow. Nothing the pipeline derived is editable here --
    page counts, confidences and statuses are findings, and letting a
    client set them would make every metric in the service unverifiable.
    """

    title: str | None = Field(default=None, min_length=1, max_length=MAX_TITLE_LENGTH)
    description: str | None = Field(default=None, max_length=4_000)
    tags: list[str] | None = Field(default=None, max_length=MAX_TAGS)
    owner_id: str | None = Field(default=None, max_length=128)


class DocumentSummaryResponse(_Base):
    """One document in a listing."""

    id: UUID
    title: str
    filename: str | None = None
    document_format: DocumentFormat
    status: DocumentStatus
    byte_size: int
    page_count: int
    word_count: int
    requires_ocr: bool
    requires_review: bool
    review_reason: str | None = None
    overall_confidence: float | None = None
    is_duplicate: bool = False
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentDetailResponse(DocumentSummaryResponse):
    """One document with everything the detail view needs."""

    description: str | None = None
    content_type: str | None = None
    checksum: str | None = None
    current_version_number: int | None = None
    mean_ocr_confidence: float | None = None
    lowest_page_confidence: float | None = None
    """Reported beside the mean, because a forty-page scan averaging 0.92
    with one page at 0.31 is not a document anyone should treat as read."""
    ocr_completed: bool = False
    processing_duration_ms: float | None = None
    duplicate_of_id: UUID | None = None
    owner_id: str | None = None
    uploaded_by: str | None = None
    error: str | None = None


class DocumentListResponse(_Base):
    """A page of documents."""

    items: list[DocumentSummaryResponse]
    total: int
    limit: int
    offset: int


class DocumentUploadResponse(_Base):
    """What an upload returns."""

    document: DocumentDetailResponse
    job_id: UUID | None = None
    is_duplicate: bool = False
    duplicate_of_id: UUID | None = None
    will_process: bool = True
    message: str


# ---- processing --------------------------------------------------------------------


class ProcessRequest(_Base):
    """Ask for a document to be processed again."""

    stages: list[ProcessingStage] | None = None
    priority: int = Field(default=50, ge=1, le=1000)


class StageOutcomeResponse(_Base):
    """What one pipeline stage did."""

    stage: ProcessingStage
    succeeded: bool
    duration_ms: float
    detail: dict[str, object] = Field(default_factory=dict)
    error: str | None = None


class JobResponse(_Base):
    """One pipeline run."""

    id: UUID
    document_id: UUID | None = None
    status: str
    stages: list[str] = Field(default_factory=list)
    current_stage: ProcessingStage | None = None
    attempts: int = 0
    max_attempts: int = 3
    duration_ms: float | None = None
    pages_processed: int = 0
    entities_extracted: int = 0
    tables_extracted: int = 0
    fields_extracted: int = 0
    stages_succeeded: int = 0
    stages_failed: int = 0
    error: str | None = None
    scheduled_at: datetime | None = None
    completed_at: datetime | None = None


class ProcessResponse(_Base):
    """The result of running the pipeline."""

    job: JobResponse
    version_number: int | None = None
    outcomes: list[StageOutcomeResponse] = Field(default_factory=list)
    requires_review: bool = False
    review_reason: str | None = None


# ---- extraction results ------------------------------------------------------------


class EntityResponse(_Base):
    """One extracted entity."""

    id: UUID
    entity_kind: EntityKind
    custom_kind: str | None = None
    value: str
    normalized_value: str
    confidence: float
    page_number: int | None = None
    start_offset: int
    end_offset: int
    context: str | None = None
    is_confirmed: bool = False
    is_redacted: bool = False


class TableResponse(_Base):
    """One extracted table."""

    id: UUID
    sequence: int
    caption: str | None = None
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    row_count: int
    column_count: int
    has_header_row: bool = False
    has_merged_cells: bool = False
    spans_pages: bool = False
    confidence: float
    warning: str | None = Field(
        default=None,
        description=(
            "Set when the table is a lossy rendering -- a merged cell has no "
            "CSV representation, and a consumer unaware of that reads the "
            "repeated value as a real repetition."
        ),
    )


class KeyValueResponse(_Base):
    """One extracted form field."""

    id: UUID
    key: str
    normalized_key: str
    value: str | None = None
    corrected_value: str | None = None
    """The reviewer's value, stored beside the original rather than over
    it -- which is what keeps the correction rate measurable."""
    field_kind: str
    is_checked: bool | None = None
    confidence: float
    page_number: int | None = None
    is_confirmed: bool = False
    corrected_by: str | None = None


class ClassificationResponse(_Base):
    """One classification label."""

    id: UUID
    category: DocumentCategory
    custom_category: str | None = None
    confidence: float
    method: str
    is_primary: bool
    rationale: str | None = None
    matched_terms: list[str] = Field(default_factory=list)
    routed_to: str | None = None


class ExtractionResponse(_Base):
    """Everything extracted from one version."""

    version_number: int
    entities: list[EntityResponse] = Field(default_factory=list)
    tables: list[TableResponse] = Field(default_factory=list)
    fields: list[KeyValueResponse] = Field(default_factory=list)
    classifications: list[ClassificationResponse] = Field(default_factory=list)


class TableExportRequest(_Base):
    """Ask for a table in a particular format."""

    table_format: TableExportFormat = TableExportFormat.CSV


# ---- summarization and translation --------------------------------------------------


class SummarizeRequest(_Base):
    """Ask for summaries of a document."""

    kinds: list[SummaryKind] = Field(default_factory=lambda: [SummaryKind.EXECUTIVE])
    sentence_count: int = Field(default=5, ge=1, le=50)
    max_words: int = Field(default=200, ge=20, le=2_000)


class SummaryResponse(_Base):
    """One summary."""

    summary_kind: SummaryKind
    content: str
    confidence: float
    word_count: int
    compression_ratio: float
    keywords: list[str] = Field(default_factory=list)
    fallback_used: bool = Field(
        default=False,
        description=(
            "An abstractive summary was asked for and extraction was used "
            "instead. The caller must be able to tell which it got."
        ),
    )


class TranslateRequest(_Base):
    """Ask for a translation."""

    target_languages: list[str] = Field(min_length=1, max_length=10)
    source_language: str | None = Field(default=None, max_length=16)

    @field_validator("target_languages")
    @classmethod
    def _clean_languages(cls, value: list[str]) -> list[str]:
        """Lowercase, deduplicate, and reject blanks.

        Raises:
            ValueError: On a blank language tag, which would otherwise
                reach the backend as a request to translate into "".
        """
        cleaned: dict[str, None] = {}
        for tag in value:
            normalized = tag.strip().lower()
            if not normalized:
                raise ValueError("A target language cannot be blank.")
            cleaned.setdefault(normalized, None)
        return list(cleaned)


class TranslationResponse(_Base):
    """One translation."""

    source_language: str
    target_language: str
    content: str
    confidence: float
    is_faithful: bool = True
    preserved_terms: list[str] = Field(default_factory=list)
    lost_terms: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---- validation and review ----------------------------------------------------------


class ValidationFindingResponse(_Base):
    """One validation finding."""

    rule_name: str
    rule_kind: str
    outcome: str
    message: str
    field_name: str | None = None
    expected: str | None = None
    actual: str | None = None
    is_blocking: bool = False


class ValidationResponse(_Base):
    """A validation report."""

    version_number: int
    findings: list[ValidationFindingResponse] = Field(default_factory=list)
    is_valid: bool
    is_complete: bool = Field(
        description=(
            "Whether every rule actually ran. Separate from is_valid: a "
            "document can have no failures because half its rules never "
            "executed, and approving on is_valid alone would approve it."
        )
    )
    completeness: float
    requires_review: bool
    rules_evaluated: int = Field(
        default=0,
        description=(
            "How many rules actually ran. Reported because is_valid=true with "
            "zero rules evaluated means nothing was checked, not that the "
            "document passed -- and a caller auto-approving on is_valid alone "
            "would approve every document on a deployment with no rules "
            "configured."
        ),
    )
    warnings: list[str] = Field(default_factory=list)


class ReviewOpenRequest(_Base):
    """Open a review."""

    reason: str = Field(min_length=1, max_length=512)
    priority: int = Field(default=100, ge=1, le=1000)
    due_hours: int | None = Field(default=None, ge=1, le=8_760)
    assigned_to: str | None = Field(default=None, max_length=128)


class ReviewDecisionRequest(_Base):
    """Close a review."""

    decision: ReviewDecision
    corrections: dict[str, str] = Field(default_factory=dict)
    comment: str | None = Field(default=None, max_length=4_000)
    annotations: list[dict[str, object]] = Field(default_factory=list, max_length=500)


class ReviewResponse(_Base):
    """One review."""

    id: UUID
    document_id: UUID
    document_version_id: UUID
    status: ReviewStatus
    decision: ReviewDecision | None = None
    reason: str
    priority: int
    assigned_to: str | None = None
    reviewer_id: str | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = None
    corrections_applied: int = 0
    fields_corrected: list[str] = Field(default_factory=list)
    escalated_to: str | None = None
    comment: str | None = None


class ReviewOutcomeResponse(_Base):
    """What closing a review changed."""

    review: ReviewResponse
    document_status: DocumentStatus
    corrections_applied: int
    fields_corrected: list[str] = Field(default_factory=list)
    requeued: bool = False


# ---- statistics and reports ---------------------------------------------------------


class StatisticResponse(_Base):
    """One statistics window."""

    window_start: datetime
    window_end: datetime
    documents_total: int
    documents_processed: int
    documents_failed: int
    documents_awaiting_review: int
    pages_total: int
    pages_ocred: int
    entities_extracted: int
    tables_extracted: int
    fields_extracted: int
    mean_ocr_confidence: float | None = None
    mean_extraction_confidence: float | None = None
    mean_processing_ms: float | None = None
    correction_rate: float | None = Field(
        default=None,
        description=(
            "None where nobody reviewed anything. Reporting 0.0 for "
            "unmeasured would read as a perfect extractor."
        ),
    )
    review_count: int = 0
    by_format: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)


class StatisticsResponse(_Base):
    """Recent statistics windows."""

    windows: list[StatisticResponse]
    total: int


class ReportRequest(_Base):
    """Ask for a report."""

    kind: ReportKind
    report_format: ReportFormat = ReportFormat.JSON
    title: str | None = Field(default=None, max_length=255)
    windows: int = Field(default=30, ge=1, le=365)


class ReportResponse(_Base):
    """One report."""

    id: UUID
    kind: ReportKind
    report_format: ReportFormat
    title: str
    status: str
    row_count: int | None = None
    content: dict[str, object] = Field(default_factory=dict)
    rendered: str | None = None
    generated_at: datetime | None = None
    duration_ms: float | None = None
    error: str | None = None


class ReportListResponse(_Base):
    """A page of reports."""

    items: list[ReportResponse]
    total: int


__all__ = [
    "MAX_PAGE_SIZE",
    "MAX_TAGS",
    "MAX_TITLE_LENGTH",
    "ClassificationResponse",
    "DocumentDetailResponse",
    "DocumentListResponse",
    "DocumentSummaryResponse",
    "DocumentUpdateRequest",
    "DocumentUploadRequest",
    "DocumentUploadResponse",
    "EntityResponse",
    "ExtractionResponse",
    "JobResponse",
    "KeyValueResponse",
    "ProcessRequest",
    "ProcessResponse",
    "ReportListResponse",
    "ReportRequest",
    "ReportResponse",
    "ReviewDecisionRequest",
    "ReviewOpenRequest",
    "ReviewOutcomeResponse",
    "ReviewResponse",
    "StageOutcomeResponse",
    "StatisticResponse",
    "StatisticsResponse",
    "SummarizeRequest",
    "SummaryResponse",
    "TableExportRequest",
    "TableResponse",
    "TranslateRequest",
    "TranslationResponse",
    "ValidationFindingResponse",
    "ValidationResponse",
]
