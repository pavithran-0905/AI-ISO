"""The processing pipeline (docs/063 "PROCESSING PIPELINE").

One job, one document, a list of stages run in order. Each stage records
its own outcome on the job, so "which step failed" stays answerable after
the document has moved on.

**One failing stage does not fail the document.** A scan whose tables
could not be extracted still has its text, its entities and its
classification, and discarding all of that because one extractor
stumbled would make the pipeline less useful the harder the document is.
Stages record their failures and the run continues; only a failure to
*parse* stops everything, because every later stage reads what parsing
produced.

**Stage order is a dependency order, not a preference.** Parsing feeds
OCR, both feed layout, and everything downstream reads the version they
produce. The runner enforces it rather than trusting the caller's list,
because a job requesting extraction without parsing would otherwise
extract from an empty string and report success.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from shared_core.logging.logger import get_logger

from app.classification.classifier import ClassifierConfig, classify
from app.documents.parser import ParsedDocument, parse
from app.entities.extractor import ExtractionSummary, extract_entities
from app.events.document_events import (
    ClassificationCompletedEvent,
    ExtractionCompletedEvent,
    OcrCompletedEvent,
    ProcessingFailedEvent,
    ValidationCompletedEvent,
)
from app.forms.extractor import FormConfig, extract_fields
from app.layout.analyzer import LayoutConfig, analyze_text
from app.models.document import DocumentPage, DocumentVersion
from app.models.enums import (
    DocumentStatus,
    JobStatus,
    ProcessingStage,
    ocr_quality_for,
)
from app.models.extraction import (
    DocumentClassification,
    DocumentEntity,
    DocumentForm,
    DocumentKeyValue,
    DocumentTable,
)
from app.models.operations import DocumentProcessingJob, DocumentValidationResult
from app.services.bundle import Repositories
from app.tables.extractor import TableConfig, extract_tables
from app.types import EventPublisher
from app.validation.engine import Rule, ValidationConfig, validate

_LOGGER = get_logger(__name__)
_SOURCE_SERVICE = "document-intelligence-service"

STAGE_ORDER: tuple[ProcessingStage, ...] = (
    ProcessingStage.PARSING,
    ProcessingStage.OCR,
    ProcessingStage.LAYOUT,
    ProcessingStage.ENTITY_EXTRACTION,
    ProcessingStage.TABLE_EXTRACTION,
    ProcessingStage.FORM_EXTRACTION,
    ProcessingStage.CLASSIFICATION,
    ProcessingStage.VALIDATION_RULES,
    ProcessingStage.SUMMARIZATION,
    ProcessingStage.TRANSLATION,
    ProcessingStage.INDEXING,
)
"""Every stage in dependency order. A job's own stage list is sorted into
this order before it runs.

Classification runs *after* form extraction, which reads backwards until
you look at what template matching needs: the form's field labels. Form
extraction finds those without knowing the document's category, and
classification cannot match a template without them -- so with
classification first, template matching silently never fires and every
form is classified by keyword and structure alone."""

_ESSENTIAL = frozenset({ProcessingStage.PARSING})
"""Stages whose failure ends the run. Only parsing: everything else reads
what parsing produced, and there is nothing for them to read."""


@dataclass(slots=True)
class StageOutcome:
    """What one stage did."""

    stage: ProcessingStage
    succeeded: bool
    duration_ms: float
    detail: dict[str, object] = field(default_factory=dict)
    error: str | None = None

    def as_record(self) -> dict[str, object]:
        return {
            "succeeded": self.succeeded,
            "duration_ms": round(self.duration_ms, 3),
            "detail": self.detail,
            "error": self.error,
        }


@dataclass(slots=True)
class PipelineResult:
    """What a whole run produced."""

    job: DocumentProcessingJob
    version: DocumentVersion | None = None
    outcomes: list[StageOutcome] = field(default_factory=list)
    requires_review: bool = False
    review_reason: str | None = None

    @property
    def succeeded(self) -> bool:
        """Whether every stage that ran succeeded."""
        return bool(self.outcomes) and all(item.succeeded for item in self.outcomes)

    @property
    def failed_stages(self) -> list[ProcessingStage]:
        return [item.stage for item in self.outcomes if not item.succeeded]

    @property
    def total_ms(self) -> float:
        return round(sum(item.duration_ms for item in self.outcomes), 3)


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """Thresholds and engine settings for one run."""

    review_below_confidence: float = 0.7
    ocr_minimum_confidence: float = 0.6
    classifier: ClassifierConfig = field(default_factory=ClassifierConfig)
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    tables: TableConfig = field(default_factory=TableConfig)
    forms: FormConfig = field(default_factory=FormConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    validation_rules: tuple[Rule, ...] = ()


class PipelineService:
    """Runs the processing pipeline over one document."""

    def __init__(
        self,
        *,
        repositories: Repositories,
        publish: EventPublisher,
        config: PipelineConfig | None = None,
        ocr_engine: object | None = None,
    ) -> None:
        self._repos: Repositories = repositories
        self._publish = publish
        self._config = config or PipelineConfig()
        self._ocr = ocr_engine

    async def run(self, job: DocumentProcessingJob, data: bytes) -> PipelineResult:
        """Run *job*'s stages over *data*.

        Never raises for a stage failure: the result carries the outcomes
        and the job records them. An exception here would mean the worker
        lost the record of what happened, which is the one thing a
        pipeline must not do.
        """
        result = PipelineResult(job=job)
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        job.attempts += 1

        stages = self._ordered(job.stages)
        parsed: ParsedDocument | None = None
        version: DocumentVersion | None = None

        for stage in stages:
            job.current_stage = stage
            started = time.perf_counter()
            try:
                detail = await self._run_stage(stage, job, data, parsed, version)
                if stage is ProcessingStage.PARSING:
                    parsed = detail.pop("_parsed")  # type: ignore[assignment]
                    version = detail.pop("_version")  # type: ignore[assignment]
                outcome = StageOutcome(
                    stage=stage,
                    succeeded=True,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    detail=detail,
                )
            except Exception as error:
                outcome = StageOutcome(
                    stage=stage,
                    succeeded=False,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    error=str(error),
                )
                _LOGGER.warning(
                    "pipeline.stage_failed",
                    extra={
                        "job_id": str(job.id),
                        "stage": str(stage),
                        "error": str(error),
                    },
                )
            result.outcomes.append(outcome)
            job.stage_results[str(stage)] = outcome.as_record()

            if not outcome.succeeded and stage in _ESSENTIAL:
                break

        result.version = version
        await self._finish(job, result)
        return result

    def _ordered(self, requested: Sequence[str]) -> list[ProcessingStage]:
        """The requested stages, in dependency order and deduplicated.

        Parsing is prepended whenever anything else was asked for: every
        later stage reads the version parsing writes, and a job that
        omitted it would extract from nothing and call that a success.
        """
        wanted = {ProcessingStage(str(item)) for item in requested}
        if wanted and ProcessingStage.PARSING not in wanted:
            wanted.add(ProcessingStage.PARSING)
        return [stage for stage in STAGE_ORDER if stage in wanted]

    async def _run_stage(
        self,
        stage: ProcessingStage,
        job: DocumentProcessingJob,
        data: bytes,
        parsed: ParsedDocument | None,
        version: DocumentVersion | None,
    ) -> dict[str, object]:
        """Run one stage and return what it found.

        Raises:
            RuntimeError: When a stage runs without the version parsing
                should have produced. That is a programming error in the
                ordering rather than a document problem, and it must not
                be recorded as a document that failed extraction.
        """
        if stage is ProcessingStage.PARSING:
            return await self._parse(job, data)
        if version is None or parsed is None:
            raise RuntimeError(
                f"{stage!s} ran with no parsed version; the stage ordering is wrong."
            )
        handlers = {
            ProcessingStage.OCR: self._ocr_stage,
            ProcessingStage.LAYOUT: self._layout_stage,
            ProcessingStage.CLASSIFICATION: self._classify_stage,
            ProcessingStage.ENTITY_EXTRACTION: self._entities_stage,
            ProcessingStage.TABLE_EXTRACTION: self._tables_stage,
            ProcessingStage.FORM_EXTRACTION: self._forms_stage,
            ProcessingStage.VALIDATION_RULES: self._validate_stage,
        }
        handler = handlers.get(stage)
        if handler is None:
            # Summarization, translation and indexing are requested
            # explicitly through their own endpoints rather than run
            # here. Recorded as skipped rather than failed: nothing went
            # wrong, this runner simply does not own them.
            return {"skipped": True, "reason": f"{stage!s} is not run by the pipeline"}
        return await handler(job, parsed, version)

    async def _parse(self, job: DocumentProcessingJob, data: bytes) -> dict[str, object]:
        """Parse the bytes and write a new current version.

        Raises:
            DocumentParseError: When nothing could be read at all.
        """
        repos = self._repos
        document = await repos.documents.require_by_id(job.document_id)
        await repos.documents.mark_status(document.id, DocumentStatus.PARSING)

        parsed = parse(data, filename=document.filename, content_type=document.content_type)
        text = parsed.text
        number = await repos.versions.next_version_number(document.id)
        version = await repos.versions.create(
            DocumentVersion(
                organization_id=document.organization_id,
                document_id=document.id,
                version_number=number,
                content=text,
                checksum=f"sha256:{hashlib.sha256(text.encode()).hexdigest()}",
                byte_size=len(data),
                word_count=parsed.word_count,
                page_count=parsed.page_count,
                parser=str(parsed.format),
                is_current=True,
                extracted_metadata=dict(parsed.metadata),
                warnings=list(parsed.warnings),
                produced_by="pipeline",
            )
        )
        await repos.versions.demote_others(document.id, version.id)

        for page in parsed.pages:
            await repos.pages.create(
                DocumentPage(
                    organization_id=document.organization_id,
                    document_id=document.id,
                    document_version_id=version.id,
                    page_number=page.number,
                    content=page.text,
                    word_count=len(page.text.split()),
                    character_count=len(page.text),
                    width=page.width,
                    height=page.height,
                    rotation_degrees=page.rotation,
                    # ``is_scanned`` is the inverse of the parser's text
                    # layer flag: a page with no text layer is one only
                    # OCR can read, which is what "scanned" means here.
                    is_scanned=not page.has_text_layer,
                    has_images=page.image_count > 0,
                )
            )

        document.page_count = parsed.page_count
        document.word_count = parsed.word_count
        document.current_version_number = version.version_number
        document.requires_ocr = parsed.needs_ocr
        await repos.documents.mark_status(document.id, DocumentStatus.PARSED)
        job.pages_processed = parsed.page_count

        return {
            "_parsed": parsed,
            "_version": version,
            "pages": parsed.page_count,
            "words": parsed.word_count,
            "needs_ocr": parsed.needs_ocr,
            "warnings": len(parsed.warnings),
        }

    async def _ocr_stage(
        self, job: DocumentProcessingJob, parsed: ParsedDocument, version: DocumentVersion
    ) -> dict[str, object]:
        """Read pages that carry no text layer.

        Skipped where the document already has text: running OCR over a
        born-digital PDF costs seconds per page and produces a worse
        reading than the text layer it would replace.
        """
        if not parsed.needs_ocr:
            return {"skipped": True, "reason": "the document has a usable text layer"}
        if self._ocr is None:
            return {
                "skipped": True,
                "reason": "no OCR engine is configured; the document cannot be read",
                "needs_ocr": True,
            }

        result = self._ocr.read(parsed)
        document = await self._repos.documents.require_by_id(job.document_id)
        document.ocr_completed = True
        document.mean_ocr_confidence = result.confidence
        document.lowest_page_confidence = result.lowest_page_confidence

        await self._publish(
            OcrCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=document.organization_id,
                payload={
                    "document_id": str(document.id),
                    "version": version.version_number,
                    "pages": len(result.pages),
                    "mean_confidence": result.confidence,
                    "lowest_page_confidence": result.lowest_page_confidence,
                    "quality": str(ocr_quality_for(result.confidence)),
                },
            )
        )
        return {
            "pages": len(result.pages),
            "mean_confidence": result.confidence,
            "lowest_page_confidence": result.lowest_page_confidence,
        }

    async def _layout_stage(
        self, job: DocumentProcessingJob, parsed: ParsedDocument, version: DocumentVersion
    ) -> dict[str, object]:
        """Detect regions on each page."""
        from app.models.document import DocumentLayout  # noqa: PLC0415 -- avoids a cycle

        pages = await self._repos.pages.list_for_version(version.id)
        total = 0
        for page in pages:
            layout = analyze_text(page.content, config=self._config.layout)
            for region in layout.regions:
                await self._repos.layouts.create(
                    DocumentLayout(
                        organization_id=version.organization_id,
                        document_id=version.document_id,
                        document_page_id=page.id,
                        region_kind=region.kind,
                        reading_order=region.reading_order,
                        content=region.content[:8_000],
                        confidence=region.confidence,
                        column_index=region.column_index,
                        heading_level=region.heading_level,
                        section_path="/".join(region.section_path) or None,
                    )
                )
                total += 1
        return {"regions": total, "pages": len(pages)}

    async def _classify_stage(
        self, job: DocumentProcessingJob, parsed: ParsedDocument, version: DocumentVersion
    ) -> dict[str, object]:
        """Assign categories to the document.

        The field labels come from what form extraction already stored,
        rather than being re-derived here: doing that work twice risks the
        two disagreeing about what the form's labels are, and template
        matching would then match against labels no stored field has.
        """
        fields = await self._repos.key_values.list_for_version(version.id)
        outcome = classify(
            version.content,
            config=self._config.classifier,
            field_labels=[item.normalized_key for item in fields],
        )
        stored = []
        for index, label in enumerate(outcome.classifications):
            row = await self._repos.classifications.create(
                DocumentClassification(
                    organization_id=version.organization_id,
                    document_id=version.document_id,
                    document_version_id=version.id,
                    category=label.category,
                    confidence=label.confidence,
                    method=label.method,
                    is_primary=index == 0,
                    rationale=label.rationale,
                    matched_terms=list(label.matched_terms)[:32],
                    routed_to=outcome.routes[0] if outcome.routes else None,
                )
            )
            stored.append(row)
        if stored:
            await self._repos.classifications.demote_others(version.id, stored[0].id)
            await self._publish(
                ClassificationCompletedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=version.organization_id,
                    payload={
                        "document_id": str(version.document_id),
                        "version": version.version_number,
                        "primary_category": str(stored[0].category),
                        "confidence": stored[0].confidence,
                        "label_count": len(stored),
                        "routes": list(outcome.routes),
                    },
                )
            )
        return {"labels": len(stored), "routes": list(outcome.routes)}

    async def _entities_stage(
        self, job: DocumentProcessingJob, parsed: ParsedDocument, version: DocumentVersion
    ) -> dict[str, object]:
        """Extract entities from the version's text."""
        found = ExtractionSummary(entities=list(extract_entities(version.content)))
        for entity in found.entities:
            await self._repos.entities.create(
                DocumentEntity(
                    organization_id=version.organization_id,
                    document_id=version.document_id,
                    document_version_id=version.id,
                    entity_kind=entity.kind,
                    custom_kind=entity.custom_kind or None,
                    value=entity.value[:2_048],
                    normalized_value=entity.normalized_value[:2_048],
                    confidence=entity.confidence,
                    extraction_method=entity.method,
                    start_offset=entity.start,
                    end_offset=entity.end,
                    context=entity.context[:512] if entity.context else None,
                )
            )
        job.entities_extracted = len(found.entities)
        return {
            "entities": found.total,
            "by_kind": found.counts,
            "confidence": found.mean_confidence,
        }

    async def _tables_stage(
        self, job: DocumentProcessingJob, parsed: ParsedDocument, version: DocumentVersion
    ) -> dict[str, object]:
        """Extract tables from the version's text."""
        found = extract_tables(version.content, self._config.tables)
        for table in found:
            await self._repos.tables.create(
                DocumentTable(
                    organization_id=version.organization_id,
                    document_id=version.document_id,
                    document_version_id=version.id,
                    sequence=table.sequence,
                    caption=table.caption,
                    row_count=table.row_count,
                    column_count=table.column_count,
                    headers=list(table.headers),
                    rows=[list(row) for row in table.rows],
                    has_header_row=table.has_header_row,
                    has_merged_cells=table.has_merged_cells,
                    spans_pages=table.spans_pages,
                    confidence=table.confidence,
                    cell_confidences=[list(row) for row in table.cell_confidences],
                    extraction_method=table.method,
                    table_metadata={"warnings": table.warnings},
                )
            )
        job.tables_extracted = len(found)
        return {"tables": len(found)}

    async def _forms_stage(
        self, job: DocumentProcessingJob, parsed: ParsedDocument, version: DocumentVersion
    ) -> dict[str, object]:
        """Extract form fields and key-value pairs."""
        found = extract_fields(version.content, config=self._config.forms)
        if not found.fields:
            return {"fields": 0, "forms": 0}

        form = await self._repos.forms.create(
            DocumentForm(
                organization_id=version.organization_id,
                document_id=version.document_id,
                document_version_id=version.id,
                sequence=0,
                name=found.template_name,
                template_match_score=found.template_confidence or None,
                field_count=found.field_count,
                filled_field_count=found.field_count - found.blank_count,
                completeness=round(
                    (found.field_count - found.blank_count) / max(found.field_count, 1), 4
                ),
                has_signature=any(str(item.kind) == "signature" for item in found.fields),
                confidence=found.confidence,
                extraction_method=found.method,
            )
        )
        for item in found.fields:
            await self._repos.key_values.create(
                DocumentKeyValue(
                    organization_id=version.organization_id,
                    document_id=version.document_id,
                    document_version_id=version.id,
                    document_form_id=form.id,
                    key=item.label[:512],
                    normalized_key=item.normalized_label[:512],
                    value=item.value or None,
                    field_kind=item.kind,
                    is_checked=item.checked,
                    confidence=item.confidence,
                    extraction_method=item.method,
                    page_number=item.page_number,
                )
            )
        job.fields_extracted = found.field_count

        await self._publish(
            ExtractionCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=version.organization_id,
                payload={
                    "document_id": str(version.document_id),
                    "version": version.version_number,
                    "entities": job.entities_extracted,
                    "tables": job.tables_extracted,
                    "fields": job.fields_extracted,
                    "confidence": found.confidence,
                },
            )
        )
        return {
            "fields": found.field_count,
            "forms": 1,
            "blank": found.blank_count,
            "template": found.template_name,
            # Reported so it reaches the document's overall confidence:
            # on a form, how well the *fields* were read is most of what
            # "how well was this document read" means.
            "confidence": found.confidence,
        }

    async def _validate_stage(
        self, job: DocumentProcessingJob, parsed: ParsedDocument, version: DocumentVersion
    ) -> dict[str, object]:
        """Run the validation rules over what was extracted."""
        fields = await self._repos.key_values.list_for_version(version.id)
        values: dict[str, object] = {
            item.normalized_key: (item.corrected_value or item.value or "") for item in fields
        }
        confidences = {item.normalized_key: item.confidence for item in fields}

        await self._repos.validations.delete_for_version(version.id)
        report = validate(
            values,
            self._config.validation_rules,
            config=self._config.validation,
            confidences=confidences,
            text=version.content,
        )
        for finding in report.findings:
            await self._repos.validations.create(
                DocumentValidationResult(
                    organization_id=version.organization_id,
                    document_id=version.document_id,
                    document_version_id=version.id,
                    rule_kind=finding.kind,
                    rule_name=finding.rule,
                    outcome=finding.outcome,
                    message=finding.message[:1_024],
                    field_name=finding.field_name,
                    expected=finding.expected[:512] if finding.expected else None,
                    actual=finding.observed[:512] if finding.observed else None,
                    is_blocking=finding.is_blocking,
                    score=report.completeness,
                )
            )

        await self._publish(
            ValidationCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=version.organization_id,
                payload={
                    "document_id": str(version.document_id),
                    "version": version.version_number,
                    "is_valid": report.is_valid,
                    "is_complete": report.is_complete,
                    "completeness": report.completeness,
                    "summary": report.summary(),
                },
            )
        )
        return {
            "findings": len(report.findings),
            "valid": report.is_valid,
            "complete": report.is_complete,
            "completeness": report.completeness,
        }

    async def _finish(self, job: DocumentProcessingJob, result: PipelineResult) -> None:
        """Close the job and set the document's final status."""
        job.completed_at = datetime.now(UTC)
        job.duration_ms = result.total_ms
        job.stages_succeeded = sum(1 for item in result.outcomes if item.succeeded)
        job.stages_failed = len(result.failed_stages)
        job.current_stage = None

        essential_failed = any(stage in _ESSENTIAL for stage in result.failed_stages)
        # Three outcomes, not two. A run whose tables failed but whose
        # text, entities and classification all landed is neither a
        # success nor a failure, and calling it either one loses the
        # distinction a re-run decision depends on.
        if essential_failed:
            job.status = JobStatus.FAILED
        elif result.failed_stages:
            job.status = JobStatus.PARTIAL
        else:
            job.status = JobStatus.COMPLETED
        if result.failed_stages:
            job.error = "; ".join(
                f"{item.stage!s}: {item.error}" for item in result.outcomes if not item.succeeded
            )[:2_000]

        if job.document_id is None:  # pragma: no cover -- jobs always carry one here
            return
        document = await self._repos.documents.require_by_id(job.document_id)
        confidence = self._overall_confidence(result)
        document.overall_confidence = confidence
        document.processing_completed_at = job.completed_at
        document.processing_duration_ms = result.total_ms

        reason = self._review_reason(result, confidence)
        document.requires_review = reason is not None
        document.review_reason = reason
        result.requires_review = reason is not None
        result.review_reason = reason

        if essential_failed:
            status = DocumentStatus.FAILED
            await self._publish(
                ProcessingFailedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=document.organization_id,
                    payload={
                        "document_id": str(document.id),
                        "job_id": str(job.id),
                        "failed_stages": [str(stage) for stage in result.failed_stages],
                        "attempts": job.attempts,
                        "error": job.error,
                    },
                )
            )
        elif reason is not None:
            status = DocumentStatus.REVIEW_PENDING
        else:
            status = DocumentStatus.EXTRACTED
        await self._repos.documents.mark_status(document.id, status, error=job.error)

    def _overall_confidence(self, result: PipelineResult) -> float | None:
        """One number for how well the document was read.

        ``None`` where no stage reported a confidence, rather than 0.0: an
        unmeasured document and a badly-read one are different states, and
        collapsing them sends every unmeasured document to review while
        making the metric meaningless.
        """
        scores = [
            float(value)
            for item in result.outcomes
            for key, value in item.detail.items()
            if key in {"mean_confidence", "confidence"} and isinstance(value, (int, float))
        ]
        if not scores:
            return None
        return round(min(scores), 4)

    def _review_reason(self, result: PipelineResult, confidence: float | None) -> str | None:
        """Why this document needs a human, or ``None``."""
        if result.failed_stages:
            failed = ", ".join(str(stage) for stage in result.failed_stages)
            return f"stages failed: {failed}"
        for item in result.outcomes:
            if item.detail.get("valid") is False:
                return "validation found blocking failures"
            if item.detail.get("needs_ocr") is True:
                return "the document needs OCR and no engine is configured"
        if confidence is not None and confidence < self._config.review_below_confidence:
            return (
                f"confidence {confidence} is below the "
                f"{self._config.review_below_confidence} threshold"
            )
        return None


__all__ = [
    "STAGE_ORDER",
    "PipelineConfig",
    "PipelineResult",
    "PipelineService",
    "StageOutcome",
]
