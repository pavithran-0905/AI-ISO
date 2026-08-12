"""Every enumerated value this service stores.

All ``StrEnum``, so a column round-trips as the string it reads as and a
log line names the value rather than an ordinal. **A loaded row's enum
column is a plain ``str`` at runtime**, not the enum member -- compare
with ``==``, never ``is``, the convention every prior AI-IOS service
follows.
"""

from __future__ import annotations

from enum import StrEnum


class DocumentFormat(StrEnum):
    """What a document *is*, as distinct from where it came from.

    The spec's own list, plus ``UNKNOWN`` for the case that actually
    happens: bytes arriving with no filename, no content type, and no
    recognisable signature. Guessing a format there produces a parse that
    fails confusingly rather than a rejection that says what is missing.
    """

    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "markdown"
    HTML = "html"
    RTF = "rtf"
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"
    XML = "xml"
    YAML = "yaml"
    IMAGE = "image"
    TIFF = "tiff"
    ZIP = "zip"
    UNKNOWN = "unknown"


IMAGE_FORMATS = frozenset({DocumentFormat.IMAGE, DocumentFormat.TIFF})
"""Formats that carry no text layer at all, so OCR is the only way to
read them. A document in one of these with OCR unavailable is not a parse
failure -- it is a deployment that cannot read it, which is a different
message to a different person."""

TEXT_LAYER_FORMATS = frozenset(
    {
        DocumentFormat.PDF,
        DocumentFormat.DOCX,
        DocumentFormat.TXT,
        DocumentFormat.MARKDOWN,
        DocumentFormat.HTML,
        DocumentFormat.RTF,
        DocumentFormat.CSV,
        DocumentFormat.XLSX,
        DocumentFormat.JSON,
        DocumentFormat.XML,
        DocumentFormat.YAML,
    }
)
"""Formats a parser can read without OCR. A PDF is in both worlds -- it
may or may not have a text layer -- and which one it turns out to be is
discovered per document, not assumed per format."""


class DocumentStatus(StrEnum):
    """Where one document sits in its lifecycle.

    Every stage the spec's DOCUMENT LIFECYCLE section names, in the order
    a document passes through them, plus the two terminal states.
    """

    UPLOADED = "uploaded"
    VALIDATING = "validating"
    OCR_PENDING = "ocr_pending"
    OCR_COMPLETE = "ocr_complete"
    PARSING = "parsing"
    PARSED = "parsed"
    CLASSIFYING = "classifying"
    CLASSIFIED = "classified"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    SUMMARIZING = "summarizing"
    TRANSLATING = "translating"
    REVIEW_PENDING = "review_pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    FAILED = "failed"
    DELETED = "deleted"


TERMINAL_STATUSES = frozenset(
    {
        DocumentStatus.APPROVED,
        DocumentStatus.REJECTED,
        DocumentStatus.ARCHIVED,
        DocumentStatus.FAILED,
        DocumentStatus.DELETED,
    }
)
"""Statuses the pipeline will not advance past on its own. A sweep that
re-picked these would reprocess an archived document forever and undo a
rejection nobody asked it to revisit."""


class ProcessingStage(StrEnum):
    """One step of the pipeline, as recorded on a job.

    Named separately from :class:`DocumentStatus` because a job runs *a*
    stage while the document sits *in* a status, and conflating them
    makes "which step failed" unanswerable once the document has moved on.
    """

    VALIDATION = "validation"
    OCR = "ocr"
    PARSING = "parsing"
    LAYOUT = "layout"
    CLASSIFICATION = "classification"
    ENTITY_EXTRACTION = "entity_extraction"
    TABLE_EXTRACTION = "table_extraction"
    FORM_EXTRACTION = "form_extraction"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    VALIDATION_RULES = "validation_rules"
    INDEXING = "indexing"


class JobStatus(StrEnum):
    """One processing job's own outcome."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    """Some stages succeeded and some did not. Its own status, not a
    flavour of ``COMPLETED``: a document whose OCR worked and whose
    extraction failed reads as done if recorded as success, and the half
    that failed is then invisible."""
    FAILED = "failed"
    CANCELLED = "cancelled"


class OcrEngineKind(StrEnum):
    """Which OCR implementation backs a page.

    ``NONE`` is a real value, recorded on pages read from a text layer:
    "this page needed no OCR" and "this page has not been OCR'd yet" are
    different facts, and a null cannot tell them apart.
    """

    NONE = "none"
    TESSERACT = "tesseract"
    EXTERNAL = "external"


class OcrQuality(StrEnum):
    """How much a page's OCR should be trusted.

    Banded rather than left as a bare float, because the decision anybody
    makes on it is categorical: index it, review it, or reject the scan.
    """

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNREADABLE = "unreadable"


class LayoutRegionKind(StrEnum):
    """What a detected region on a page is."""

    HEADER = "header"
    FOOTER = "footer"
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"
    SIGNATURE = "signature"
    STAMP = "stamp"
    MARGIN_NOTE = "margin_note"
    PAGE_NUMBER = "page_number"
    UNKNOWN = "unknown"


class ClassificationMethod(StrEnum):
    """How a document's category was decided.

    Recorded per classification, because a rule match and a template
    match warrant different amounts of trust and a reviewer needs to know
    which one produced the label in front of them.
    """

    RULE = "rule"
    TEMPLATE = "template"
    KEYWORD = "keyword"
    STRUCTURE = "structure"
    AI = "ai"
    MANUAL = "manual"


class DocumentCategory(StrEnum):
    """The categories this service ships with.

    Deliberately generic infrastructure-and-operations categories rather
    than business document types: the spec's DO NOT IMPLEMENT list rules
    out "Business-specific Document Templates", and a fixed set of
    invoice/purchase-order/contract labels is exactly that. Organizations
    add their own through
    :class:`~app.models.document.ClassificationRule`.
    """

    RUNBOOK = "runbook"
    POLICY = "policy"
    REPORT = "report"
    SPECIFICATION = "specification"
    CORRESPONDENCE = "correspondence"
    FORM = "form"
    LOG = "log"
    CONFIGURATION = "configuration"
    DIAGRAM = "diagram"
    CERTIFICATE = "certificate"
    OTHER = "other"


class EntityKind(StrEnum):
    """What an extracted entity is.

    Every kind the spec names. The infrastructure kinds -- hostname, IP,
    asset name, serial number -- are the ones this platform actually
    reasons over, and they are the ones a general-purpose NER model is
    worst at.
    """

    PERSON = "person"
    ORGANIZATION = "organization"
    ADDRESS = "address"
    EMAIL = "email"
    PHONE = "phone"
    DATE = "date"
    CURRENCY = "currency"
    IDENTIFIER = "identifier"
    ASSET_NAME = "asset_name"
    HOSTNAME = "hostname"
    IP_ADDRESS = "ip_address"
    URL = "url"
    SERIAL_NUMBER = "serial_number"
    CUSTOM = "custom"


class ExtractionMethod(StrEnum):
    """How a value was extracted."""

    PATTERN = "pattern"
    LAYOUT = "layout"
    TEMPLATE = "template"
    HEURISTIC = "heuristic"
    AI = "ai"
    MANUAL = "manual"


class TableExportFormat(StrEnum):
    """A rendering an extracted table can be exported as."""

    CSV = "csv"
    JSON = "json"
    XLSX = "xlsx"
    MARKDOWN = "markdown"


class FormFieldKind(StrEnum):
    """What one field on a form is."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SIGNATURE = "signature"
    HANDWRITTEN = "handwritten"
    SELECTION = "selection"


class SummaryKind(StrEnum):
    """Which summary of a document this is.

    A document has several at once: an executive summary and a technical
    one answer different questions for different readers, and storing
    only "the" summary means whichever was generated last wins.
    """

    EXECUTIVE = "executive"
    TECHNICAL = "technical"
    BULLET = "bullet"
    SECTION = "section"
    EXTRACTIVE = "extractive"
    ABSTRACTIVE = "abstractive"


class ValidationRuleKind(StrEnum):
    """What a validation rule checks."""

    REQUIRED_FIELD = "required_field"
    SCHEMA = "schema"
    BUSINESS_RULE = "business_rule"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    DUPLICATE = "duplicate"
    CONFIDENCE_THRESHOLD = "confidence_threshold"


class ValidationOutcome(StrEnum):
    """What one validation rule concluded.

    ``SKIPPED`` is distinct from ``PASSED``: a rule that could not run --
    because the field it checks was never extracted -- has not validated
    anything, and recording it as a pass is how an incomplete document
    reaches approval.
    """

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


class ReviewStatus(StrEnum):
    """Where one review sits."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    EXPIRED = "expired"


class ReviewDecision(StrEnum):
    """What a reviewer concluded."""

    APPROVED = "approved"
    REJECTED = "rejected"
    CORRECTED = "corrected"
    REPROCESS = "reprocess"
    """Send it back through the pipeline. Distinct from a rejection: the
    document is fine and the extraction was not, so what needs redoing is
    the machine's work rather than the submitter's."""


class ReportKind(StrEnum):
    """Which report this is."""

    PROCESSING = "processing"
    ACCURACY = "accuracy"
    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    REVIEW = "review"
    THROUGHPUT = "throughput"
    AUDIT = "audit"


class ReportFormat(StrEnum):
    """How a report's content is rendered."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    HTML = "html"


class ReportStatus(StrEnum):
    """A report generation's own outcome."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditAction(StrEnum):
    """Everything this service records having done."""

    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_IMPORTED = "document_imported"
    DOCUMENT_UPDATED = "document_updated"
    DOCUMENT_ARCHIVED = "document_archived"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_RESTORED = "document_restored"
    OCR_COMPLETED = "ocr_completed"
    LAYOUT_ANALYSED = "layout_analysed"
    DOCUMENT_CLASSIFIED = "document_classified"
    ENTITIES_EXTRACTED = "entities_extracted"
    TABLES_EXTRACTED = "tables_extracted"
    FORMS_EXTRACTED = "forms_extracted"
    DOCUMENT_SUMMARIZED = "document_summarized"
    DOCUMENT_TRANSLATED = "document_translated"
    DOCUMENT_VALIDATED = "document_validated"
    REVIEW_REQUESTED = "review_requested"
    REVIEW_ASSIGNED = "review_assigned"
    REVIEW_COMPLETED = "review_completed"
    CORRECTION_APPLIED = "correction_applied"
    PROCESSING_STARTED = "processing_started"
    PROCESSING_COMPLETED = "processing_completed"
    ADMINISTRATIVE = "administrative"


_OCR_QUALITY_FLOORS: tuple[tuple[float, OcrQuality], ...] = (
    (0.95, OcrQuality.EXCELLENT),
    (0.85, OcrQuality.GOOD),
    (0.70, OcrQuality.FAIR),
    (0.40, OcrQuality.POOR),
)


def ocr_quality_for(confidence: float) -> OcrQuality:
    """Band a mean OCR confidence.

    The bands are wide on purpose. OCR confidence is not calibrated
    between engines or even between page images, so a two-decimal number
    invites a precision it does not have; what it can honestly support is
    "index this", "have somebody read it", or "rescan it".

    Raises:
        ValueError: If *confidence* is outside ``[0, 1]``. A value outside
            the range means the caller is passing a percentage or a raw
            engine score, and silently banding it would report a clean
            page as unreadable or the reverse.
    """
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(
            f"OCR confidence must be within [0, 1], got {confidence!r}. Engine scores "
            "reported as percentages must be divided by 100 before banding."
        )
    for floor, quality in _OCR_QUALITY_FLOORS:
        if confidence >= floor:
            return quality
    return OcrQuality.UNREADABLE


def is_terminal(status: DocumentStatus | str) -> bool:
    """Whether the pipeline should leave this document alone.

    Raises:
        ValueError: If *status* is not a known document status.
    """
    return DocumentStatus(str(status)) in TERMINAL_STATUSES


def needs_ocr(document_format: DocumentFormat | str) -> bool:
    """Whether this format can only be read by OCR.

    ``PDF`` returns ``False`` even though a scanned PDF needs OCR: the
    format alone cannot tell you, and the answer is discovered per
    document by trying the text layer first. Claiming otherwise here
    would send every PDF through OCR, which is slow, lossy, and wrong for
    the majority that have perfectly good text in them.
    """
    return DocumentFormat(str(document_format)) in IMAGE_FORMATS


__all__ = [
    "IMAGE_FORMATS",
    "TERMINAL_STATUSES",
    "TEXT_LAYER_FORMATS",
    "AuditAction",
    "ClassificationMethod",
    "DocumentCategory",
    "DocumentFormat",
    "DocumentStatus",
    "EntityKind",
    "ExtractionMethod",
    "FormFieldKind",
    "JobStatus",
    "LayoutRegionKind",
    "OcrEngineKind",
    "OcrQuality",
    "ProcessingStage",
    "ReportFormat",
    "ReportKind",
    "ReportStatus",
    "ReviewDecision",
    "ReviewStatus",
    "SummaryKind",
    "TableExportFormat",
    "ValidationOutcome",
    "ValidationRuleKind",
    "is_terminal",
    "needs_ocr",
    "ocr_quality_for",
]
