"""Document telemetry (docs/063 "TELEMETRY"): Upload, OCR, Layout Analysis,
Classification, Entity Extraction, Table Extraction, Validation, Review.

Integrates ``shared_core.telemetry`` (Prompt 024).

**Every call below passes attributes via ``**{...}``, never a literal
``attributes={...}`` keyword.** ``start_span``'s own signature is
``start_span(tracer, name, *, span_type=None, **attributes)`` -- there is
no parameter actually named ``attributes``, only that catch-all. Passing
one anyway silently drops every attribute onto the floor instead of
raising, a confirmed repo-wide defect in AI-IOS services built before
Prompt 054. This copy was written correct from the start.

**Spans carry identifiers, counts, and scores -- never document text,
extracted values, field values, or filenames.** This service exists to
find passport numbers, account details and signatures; a span is the
easiest place in a platform to publish them by accident, and a tracing
backend has different retention and access rules than this service's own
database. A filename is frequently the most identifying thing about a
document and is not needed to see how a stage performs.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry.trace import Span, Tracer
from shared_core.telemetry.span import SpanType, start_span


@contextmanager
def trace_upload(
    tracer: Tracer, *, document_format: str, byte_size: int, **attributes: object
) -> Iterator[Span]:
    """Span one document upload ("Upload").

    The format and byte size, never the filename or the title: both are
    frequently the most identifying thing about a document, and neither is
    needed to see how ingestion performs by format and size.
    """
    with start_span(
        tracer,
        "document.upload",
        span_type=SpanType.FILE_UPLOAD,
        **{
            "document.format": document_format,
            "document.byte_size": byte_size,
            **attributes,
        },
    ) as span:
        yield span


@contextmanager
def trace_ocr(tracer: Tracer, *, pages: int, engine: str, **attributes: object) -> Iterator[Span]:
    """Span one OCR pass ("OCR").

    The page count and engine. Confidence is recorded by the caller on the
    span it gets back, because it is only known once the pass finishes.
    """
    with start_span(
        tracer,
        "document.ocr",
        span_type=SpanType.WORKFLOW_STEP,
        **{"ocr.pages": pages, "ocr.engine": engine, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_layout(tracer: Tracer, *, pages: int, **attributes: object) -> Iterator[Span]:
    """Span layout analysis ("Layout Analysis")."""
    with start_span(
        tracer,
        "document.layout",
        span_type=SpanType.WORKFLOW_STEP,
        **{"layout.pages": pages, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_classification(tracer: Tracer, *, method: str, **attributes: object) -> Iterator[Span]:
    """Span classification ("Classification").

    The method, and the resulting *category* -- which is a label from a
    fixed enumeration, not document content, so it is safe to record and
    is the one attribute that makes a classification span useful.
    """
    with start_span(
        tracer,
        "document.classify",
        span_type=SpanType.WORKFLOW_STEP,
        **{"classification.method": method, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_entity_extraction(
    tracer: Tracer, *, text_length: int, **attributes: object
) -> Iterator[Span]:
    """Span entity extraction ("Entity Extraction").

    The length of the text scanned, never the text. Entity *kinds* and
    counts are safe and are recorded by the caller; entity *values* are
    exactly what this service was built to find and never leave the
    database.
    """
    with start_span(
        tracer,
        "document.extract_entities",
        span_type=SpanType.WORKFLOW_STEP,
        **{"extraction.text_length": text_length, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_table_extraction(tracer: Tracer, *, tables: int, **attributes: object) -> Iterator[Span]:
    """Span table extraction ("Table Extraction")."""
    with start_span(
        tracer,
        "document.extract_tables",
        span_type=SpanType.WORKFLOW_STEP,
        **{"extraction.tables": tables, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_form_extraction(tracer: Tracer, *, fields: int, **attributes: object) -> Iterator[Span]:
    """Span form extraction.

    Not in the spec's own list and added deliberately: form extraction is
    the slowest stage on a real form, and a trace that covers tables but
    not fields cannot explain where the time went.
    """
    with start_span(
        tracer,
        "document.extract_fields",
        span_type=SpanType.WORKFLOW_STEP,
        **{"extraction.fields": fields, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_validation(tracer: Tracer, *, rules: int, **attributes: object) -> Iterator[Span]:
    """Span validation ("Validation").

    The rule count, so a span shows whether zero rules ran -- which is the
    difference between a validated document and an unchecked one.
    """
    with start_span(
        tracer,
        "document.validate",
        span_type=SpanType.VALIDATION_STEP,
        **{"validation.rules": rules, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_review(
    tracer: Tracer, *, decision: str, corrections: int, **attributes: object
) -> Iterator[Span]:
    """Span one review decision ("Review").

    The decision and how many fields were corrected. Not the field names
    or values: a corrected field name can itself identify a form, and the
    value is the sensitive part.
    """
    with start_span(
        tracer,
        "document.review",
        span_type=SpanType.WORKFLOW_STEP,
        **{"review.decision": decision, "review.corrections": corrections, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_pipeline(tracer: Tracer, *, stages: int, **attributes: object) -> Iterator[Span]:
    """Span a whole pipeline run, as the parent of the stage spans."""
    with start_span(
        tracer,
        "document.pipeline",
        # BACKGROUND_JOB rather than WORKFLOW_STEP: this span is the
        # *parent* of the stage spans, and the enum has no WORKFLOW
        # member. A parent typed identically to its children makes a
        # trace impossible to read at a glance.
        span_type=SpanType.BACKGROUND_JOB,
        **{"pipeline.stages": stages, **attributes},
    ) as span:
        yield span


__all__ = [
    "trace_classification",
    "trace_entity_extraction",
    "trace_form_extraction",
    "trace_layout",
    "trace_ocr",
    "trace_pipeline",
    "trace_review",
    "trace_table_extraction",
    "trace_upload",
    "trace_validation",
]
