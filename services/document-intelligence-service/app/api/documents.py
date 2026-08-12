"""The document endpoints (docs/063 "REST APIs").

All fifteen the spec names.

**Static segments are registered before the ``{document_id}`` catch-all.**
FastAPI matches in declaration order, so ``/documents/statistics``
declared after ``/documents/{document_id}`` is never reached -- the
catch-all takes it and fails trying to parse "statistics" as a UUID.

**Every route derives its tenant from the token.** No path, query or body
parameter names an organization; see :func:`app.api.deps.get_organization_id`
for why that is not a convenience.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from shared_core.exceptions.validation import ValidationError
from shared_core.logging.context import get_log_context

from app.api.deps import (
    Analytics,
    CurrentUserId,
    Ingestion,
    Notifications,
    OrganizationId,
    Pipeline,
    Reports,
    Repos,
    Review,
    ServiceSettings,
    Storage,
    require_administrator,
)
from app.models.enums import (
    DocumentStatus,
    ProcessingStage,
    ReportFormat,
    ReportKind,
)
from app.models.operations import DocumentReport, DocumentStatistic
from app.schemas.document import (
    MAX_PAGE_SIZE,
    ClassificationResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentSummaryResponse,
    DocumentUpdateRequest,
    DocumentUploadResponse,
    EntityResponse,
    ExtractionResponse,
    JobResponse,
    KeyValueResponse,
    ProcessRequest,
    ProcessResponse,
    ReportListResponse,
    ReportRequest,
    ReportResponse,
    ReviewDecisionRequest,
    ReviewOpenRequest,
    ReviewOutcomeResponse,
    ReviewResponse,
    StageOutcomeResponse,
    StatisticResponse,
    StatisticsResponse,
    SummarizeRequest,
    SummaryResponse,
    TableResponse,
    TranslateRequest,
    TranslationResponse,
    ValidationFindingResponse,
    ValidationResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse
from app.services.analytics import render
from app.summarization.summarizer import SummaryConfig, summarize_many
from app.translation.translator import (
    TranslationUnavailableError,
    detect_language,
    translate_many,
)

router = APIRouter(prefix="/documents", tags=["Documents"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


# ---- static segments, declared first ------------------------------------------------


@router.get(
    "/statistics",
    response_model=SuccessResponse[StatisticsResponse],
    summary="Recent processing statistics",
)
async def get_statistics(
    organization_id: OrganizationId,
    repos: Repos,
    analytics: Analytics,
    windows: Annotated[int, Query(ge=1, le=365)] = 24,
    refresh: Annotated[bool, Query()] = False,
) -> SuccessResponse[StatisticsResponse]:
    """Statistics windows for the caller's organization, newest first.

    ``refresh`` rolls up the most recent completed window first, so a
    dashboard opened moments after a batch finished does not show an empty
    latest window and read as a service that stopped working.
    """
    if refresh:
        await analytics.roll_up_all()
    rows = await repos.statistics.list_recent(organization_id, limit=windows)
    data = StatisticsResponse(windows=[_statistic(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Statistics retrieved.", data=data, meta=_meta())


@router.get(
    "/reports",
    response_model=SuccessResponse[ReportListResponse],
    summary="List generated reports",
)
async def list_reports(
    organization_id: OrganizationId,
    repos: Repos,
    kind: Annotated[ReportKind | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> SuccessResponse[ReportListResponse]:
    """Reports for the caller's organization, newest first."""
    rows = await repos.reports.list_for_org(organization_id, kind=kind, limit=limit)
    data = ReportListResponse(items=[_report(row, rendered=None) for row in rows], total=len(rows))
    return SuccessResponse(message="Reports retrieved.", data=data, meta=_meta())


@router.post(
    "/reports",
    response_model=SuccessResponse[ReportResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate a report",
)
async def create_report(
    payload: ReportRequest,
    organization_id: OrganizationId,
    user_id: CurrentUserId,
    reports: Reports,
) -> SuccessResponse[ReportResponse]:
    """Generate a report synchronously and return it rendered."""
    report = await reports.request(
        organization_id=organization_id,
        kind=payload.kind,
        report_format=payload.report_format,
        title=payload.title,
        requested_by=user_id,
    )
    await reports.generate(report, windows=payload.windows)
    rendered = render(report) if report.content else None
    return SuccessResponse(
        message=f"Report generated with status {report.status!s}.",
        data=_report(report, rendered=rendered),
        meta=_meta(),
    )


@router.post(
    "/statistics/rollup",
    response_model=SuccessResponse[dict[str, int]],
    dependencies=[Depends(require_administrator)],
    summary="Roll up statistics now (administrators only)",
)
async def rollup_statistics(analytics: Analytics) -> SuccessResponse[dict[str, int]]:
    """Force a statistics rollup across every organization.

    Administrator-gated: it reads across tenants by design, which is
    exactly why no ordinary token may trigger it.
    """
    rows = await analytics.roll_up_all()
    return SuccessResponse(message="Rollup completed.", data={"windows": len(rows)}, meta=_meta())


# ---- collection ----------------------------------------------------------------------


@router.get(
    "",
    response_model=SuccessResponse[DocumentListResponse],
    summary="List documents",
)
async def list_documents(
    organization_id: OrganizationId,
    repos: Repos,
    document_status: Annotated[DocumentStatus | None, Query(alias="status")] = None,
    query: Annotated[str | None, Query(max_length=255)] = None,
    awaiting_review: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SuccessResponse[DocumentListResponse]:
    """Documents in the caller's organization."""
    if awaiting_review:
        rows = await repos.documents.list_awaiting_review(organization_id, limit=limit)
    elif document_status is not None:
        rows = await repos.documents.list_by_status(
            organization_id, document_status, limit=limit, offset=offset
        )
    else:
        rows = await repos.documents.search_in_org(organization_id, query or "", limit=limit)
    data = DocumentListResponse(
        items=[_summary(row) for row in rows],
        total=len(rows),
        limit=limit,
        offset=offset,
    )
    return SuccessResponse(message="Documents retrieved.", data=data, meta=_meta())


@router.post(
    "",
    response_model=SuccessResponse[DocumentUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
)
async def upload_document(
    organization_id: OrganizationId,
    user_id: CurrentUserId,
    ingestion: Ingestion,
    file: Annotated[UploadFile, File(description="The document itself")],
    title: Annotated[str | None, Form()] = None,
    tags: Annotated[str | None, Form(description="Comma-separated tags")] = None,
    priority: Annotated[int, Form(ge=1, le=1000)] = 100,
) -> SuccessResponse[DocumentUploadResponse]:
    """Accept a document as multipart and queue it for processing.

    Multipart rather than JSON: base64 inflates a 50 MB scan by a third
    and holds it in memory twice over.
    """
    data = await file.read()
    result = await ingestion.ingest(
        organization_id=organization_id,
        data=data,
        title=(title or file.filename or "Untitled document"),
        filename=file.filename,
        content_type=file.content_type,
        uploaded_by=user_id,
        tags=[tag.strip() for tag in (tags or "").split(",") if tag.strip()],
        priority=priority,
    )
    message = (
        "Document accepted and queued for processing."
        if result.will_process
        else "Document accepted; identical content already exists, so processing was skipped."
    )
    payload = DocumentUploadResponse(
        document=_detail(result.document),
        job_id=result.job.id if result.job else None,
        is_duplicate=result.is_duplicate,
        duplicate_of_id=result.duplicate_of.id if result.duplicate_of else None,
        will_process=result.will_process,
        message=message,
    )
    return SuccessResponse(message=message, data=payload, meta=_meta())


# ---- one document --------------------------------------------------------------------


@router.get(
    "/{document_id}",
    response_model=SuccessResponse[DocumentDetailResponse],
    summary="Get one document",
)
async def get_document(
    document_id: UUID, organization_id: OrganizationId, repos: Repos
) -> SuccessResponse[DocumentDetailResponse]:
    """One document from the caller's organization."""
    document = await repos.documents.require_in_org(organization_id, document_id)
    return SuccessResponse(message="Document retrieved.", data=_detail(document), meta=_meta())


@router.put(
    "/{document_id}",
    response_model=SuccessResponse[DocumentDetailResponse],
    summary="Update a document's metadata",
)
async def update_document(
    document_id: UUID,
    payload: DocumentUpdateRequest,
    organization_id: OrganizationId,
    repos: Repos,
) -> SuccessResponse[DocumentDetailResponse]:
    """Change a document's editable metadata.

    Only the fields a human owns. Nothing the pipeline derived is editable
    -- statuses, page counts and confidences are findings, and a client
    that could set them would make every metric here unverifiable.
    """
    document = await repos.documents.require_in_org(organization_id, document_id)
    for name, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(document, name, value)
    return SuccessResponse(message="Document updated.", data=_detail(document), meta=_meta())


@router.delete(
    "/{document_id}",
    response_model=SuccessResponse[DocumentDetailResponse],
    summary="Delete a document",
)
async def delete_document(
    document_id: UUID,
    organization_id: OrganizationId,
    user_id: CurrentUserId,
    repos: Repos,
) -> SuccessResponse[DocumentDetailResponse]:
    """Soft-delete a document.

    Soft, because the audit trail references it and a hard delete would
    leave audit rows pointing at nothing -- which is indistinguishable
    from an audit trail that was tampered with.
    """
    document = await repos.documents.require_in_org(organization_id, document_id)
    await repos.documents.delete(document.id)
    from datetime import UTC, datetime  # noqa: PLC0415 -- only needed on this path

    from app.models.operations import DocumentAudit  # noqa: PLC0415

    await repos.audits.create(
        DocumentAudit(
            organization_id=organization_id,
            action="deleted",
            entity_type="document",
            entity_id=document.id,
            occurred_at=datetime.now(UTC),
            actor_id=user_id,
            summary=f"Document {document.title!r} was deleted.",
        )
    )
    return SuccessResponse(message="Document deleted.", data=_detail(document), meta=_meta())


# ---- processing actions ---------------------------------------------------------------


@router.post(
    "/{document_id}/ocr",
    response_model=SuccessResponse[ProcessResponse],
    summary="Run OCR over a document",
)
async def run_ocr(
    document_id: UUID,
    organization_id: OrganizationId,
    user_id: CurrentUserId,
    ingestion: Ingestion,
    pipeline: Pipeline,
    repos: Repos,
    notifications: Notifications,
    storage: Storage,
) -> SuccessResponse[ProcessResponse]:
    """Re-read a document with OCR."""
    return await _run(
        stages=(ProcessingStage.PARSING, ProcessingStage.OCR),
        document_id=document_id,
        organization_id=organization_id,
        user_id=user_id,
        ingestion=ingestion,
        pipeline=pipeline,
        repos=repos,
        notifications=notifications,
        storage=storage,
        message="OCR completed.",
    )


@router.post(
    "/{document_id}/classify",
    response_model=SuccessResponse[ProcessResponse],
    summary="Classify a document",
)
async def classify_document(
    document_id: UUID,
    organization_id: OrganizationId,
    user_id: CurrentUserId,
    ingestion: Ingestion,
    pipeline: Pipeline,
    repos: Repos,
    notifications: Notifications,
    storage: Storage,
) -> SuccessResponse[ProcessResponse]:
    """Re-classify a document.

    Form extraction runs alongside, because template matching needs the
    field labels it produces -- classification alone would silently skip
    every template.
    """
    return await _run(
        stages=(
            ProcessingStage.PARSING,
            ProcessingStage.FORM_EXTRACTION,
            ProcessingStage.CLASSIFICATION,
        ),
        document_id=document_id,
        organization_id=organization_id,
        user_id=user_id,
        ingestion=ingestion,
        pipeline=pipeline,
        repos=repos,
        notifications=notifications,
        storage=storage,
        message="Classification completed.",
    )


@router.post(
    "/{document_id}/extract",
    response_model=SuccessResponse[ProcessResponse],
    summary="Extract entities, tables and fields",
)
async def extract_document(
    document_id: UUID,
    payload: ProcessRequest,
    organization_id: OrganizationId,
    user_id: CurrentUserId,
    ingestion: Ingestion,
    pipeline: Pipeline,
    repos: Repos,
    notifications: Notifications,
    storage: Storage,
) -> SuccessResponse[ProcessResponse]:
    """Run the extraction stages over a document."""
    stages = (
        tuple(payload.stages)
        if payload.stages
        else (
            ProcessingStage.PARSING,
            ProcessingStage.LAYOUT,
            ProcessingStage.ENTITY_EXTRACTION,
            ProcessingStage.TABLE_EXTRACTION,
            ProcessingStage.FORM_EXTRACTION,
            ProcessingStage.CLASSIFICATION,
        )
    )
    return await _run(
        stages=stages,
        document_id=document_id,
        organization_id=organization_id,
        user_id=user_id,
        ingestion=ingestion,
        pipeline=pipeline,
        repos=repos,
        notifications=notifications,
        storage=storage,
        message="Extraction completed.",
        priority=payload.priority,
    )


@router.get(
    "/{document_id}/extraction",
    response_model=SuccessResponse[ExtractionResponse],
    summary="Get what was extracted",
)
async def get_extraction(
    document_id: UUID, organization_id: OrganizationId, repos: Repos
) -> SuccessResponse[ExtractionResponse]:
    """Everything extracted from a document's current version."""
    await repos.documents.require_in_org(organization_id, document_id)
    version = await repos.versions.require_current(document_id)
    data = ExtractionResponse(
        version_number=version.version_number,
        entities=[
            EntityResponse.model_validate(row, from_attributes=True)
            for row in await repos.entities.list_for_version(version.id)
        ],
        tables=[_table(row) for row in await repos.tables.list_for_version(version.id)],
        fields=[
            KeyValueResponse.model_validate(row, from_attributes=True)
            for row in await repos.key_values.list_for_version(version.id)
        ],
        classifications=[
            ClassificationResponse.model_validate(row, from_attributes=True)
            for row in await repos.classifications.list_for_version(version.id)
        ],
    )
    return SuccessResponse(message="Extraction retrieved.", data=data, meta=_meta())


@router.post(
    "/{document_id}/summarize",
    response_model=SuccessResponse[list[SummaryResponse]],
    summary="Summarize a document",
)
async def summarize_document(
    document_id: UUID,
    payload: SummarizeRequest,
    organization_id: OrganizationId,
    repos: Repos,
) -> SuccessResponse[list[SummaryResponse]]:
    """Summarize a document's current version and store the summaries."""
    from app.models.extraction import DocumentSummary  # noqa: PLC0415

    await repos.documents.require_in_org(organization_id, document_id)
    version = await repos.versions.require_current(document_id)
    config = SummaryConfig(sentence_count=payload.sentence_count, max_words=payload.max_words)
    produced = summarize_many(version.content, payload.kinds, config=config)

    responses: list[SummaryResponse] = []
    for kind, summary in produced.items():
        existing = await repos.summaries.find_of_kind(version.id, kind)
        if existing is None:
            await repos.summaries.create(
                DocumentSummary(
                    organization_id=organization_id,
                    document_id=document_id,
                    document_version_id=version.id,
                    summary_kind=kind,
                    content=summary.text,
                    confidence=summary.confidence,
                )
            )
        else:
            existing.content = summary.text
            existing.confidence = summary.confidence
        responses.append(
            SummaryResponse(
                summary_kind=kind,
                content=summary.text,
                confidence=summary.confidence,
                word_count=summary.word_count,
                compression_ratio=summary.compression_ratio,
                keywords=list(summary.keywords),
                fallback_used=summary.fallback_used,
            )
        )
    return SuccessResponse(
        message=f"{len(responses)} summary/summaries produced.",
        data=responses,
        meta=_meta(),
    )


@router.post(
    "/{document_id}/translate",
    response_model=SuccessResponse[list[TranslationResponse]],
    summary="Translate a document",
)
async def translate_document(
    document_id: UUID,
    payload: TranslateRequest,
    organization_id: OrganizationId,
    repos: Repos,
    settings: ServiceSettings,
    notifications: Notifications,
    user_id: CurrentUserId,
) -> SuccessResponse[list[TranslationResponse]]:
    """Translate a document's current version.

    Raises:
        ValidationError: When translation is disabled, or when no backend
            is configured. Both return a clear 400 rather than storing the
            source text labelled as a translation, which nothing
            downstream could ever detect as wrong.
    """
    from app.models.extraction import DocumentTranslation  # noqa: PLC0415

    if not settings.translation_enabled:
        raise ValidationError("Translation is disabled on this deployment.")

    await repos.documents.require_in_org(organization_id, document_id)
    version = await repos.versions.require_current(document_id)
    try:
        produced = translate_many(
            version.content,
            payload.target_languages,
            backend=None,
            source=payload.source_language,
        )
    except TranslationUnavailableError as error:
        raise ValidationError(
            f"No translation backend is configured on this deployment: {error}"
        ) from error

    responses: list[TranslationResponse] = []
    for target, result in produced.items():
        existing = await repos.translations.find_in_language(version.id, target)
        if existing is None:
            await repos.translations.create(
                DocumentTranslation(
                    organization_id=organization_id,
                    document_id=document_id,
                    document_version_id=version.id,
                    source_language=result.source_language,
                    target_language=target,
                    content=result.text,
                    confidence=result.confidence,
                )
            )
        else:
            existing.content = result.text
            existing.confidence = result.confidence
        if notifications is not None:
            await notifications.send_translation_completed(
                user_id,
                title=version.document_id.hex,
                target_language=target,
                is_faithful=result.is_faithful,
            )
        responses.append(
            TranslationResponse(
                source_language=result.source_language,
                target_language=target,
                content=result.text,
                confidence=result.confidence,
                is_faithful=result.is_faithful,
                preserved_terms=list(result.preserved_terms),
                lost_terms=list(result.lost_placeholders),
                warnings=list(result.warnings),
            )
        )
    return SuccessResponse(
        message=f"{len(responses)} translation(s) produced.", data=responses, meta=_meta()
    )


@router.get(
    "/{document_id}/language",
    response_model=SuccessResponse[dict[str, object]],
    summary="Detect a document's language",
)
async def detect_document_language(
    document_id: UUID, organization_id: OrganizationId, repos: Repos
) -> SuccessResponse[dict[str, object]]:
    """The detected language of a document's current version."""
    await repos.documents.require_in_org(organization_id, document_id)
    version = await repos.versions.require_current(document_id)
    guess = detect_language(version.content)
    data: dict[str, object] = {
        "language": guess.language,
        "confidence": guess.confidence,
        "is_reliable": guess.is_reliable,
        "scores": dict(guess.scores),
    }
    return SuccessResponse(message="Language detected.", data=data, meta=_meta())


@router.post(
    "/{document_id}/validate",
    response_model=SuccessResponse[ValidationResponse],
    summary="Validate a document",
)
async def validate_document(
    document_id: UUID,
    organization_id: OrganizationId,
    user_id: CurrentUserId,
    ingestion: Ingestion,
    pipeline: Pipeline,
    repos: Repos,
    notifications: Notifications,
    storage: Storage,
) -> SuccessResponse[ValidationResponse]:
    """Re-validate a document and return the findings."""
    await _run(
        stages=(
            ProcessingStage.PARSING,
            ProcessingStage.FORM_EXTRACTION,
            ProcessingStage.VALIDATION_RULES,
        ),
        document_id=document_id,
        organization_id=organization_id,
        user_id=user_id,
        ingestion=ingestion,
        pipeline=pipeline,
        repos=repos,
        notifications=notifications,
        storage=storage,
        message="Validation completed.",
    )
    version = await repos.versions.require_current(document_id)
    findings = await repos.validations.list_for_version(version.id)
    document = await repos.documents.require_in_org(organization_id, document_id)
    blocking = await repos.validations.has_blocking(version.id)
    data = ValidationResponse(
        version_number=version.version_number,
        findings=[
            ValidationFindingResponse(
                rule_name=row.rule_name,
                rule_kind=str(row.rule_kind),
                outcome=str(row.outcome),
                message=row.message,
                field_name=row.field_name,
                expected=row.expected,
                actual=row.actual,
                is_blocking=row.is_blocking,
            )
            for row in findings
        ],
        is_valid=not blocking,
        is_complete=not any(str(row.outcome) == "skipped" for row in findings),
        completeness=next((row.score or 0.0 for row in findings), 0.0),
        requires_review=document.requires_review,
        rules_evaluated=len(findings),
        warnings=(
            []
            if findings
            else [
                "No validation rules are configured on this deployment, so this "
                "document was not checked. is_valid reflects an absence of "
                "failures, not a passed validation."
            ]
        ),
    )
    return SuccessResponse(message="Validation completed.", data=data, meta=_meta())


# ---- review ---------------------------------------------------------------------------


@router.post(
    "/{document_id}/review",
    response_model=SuccessResponse[ReviewResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Open a review",
)
async def open_review(
    document_id: UUID,
    payload: ReviewOpenRequest,
    organization_id: OrganizationId,
    review: Review,
    notifications: Notifications,
    repos: Repos,
) -> SuccessResponse[ReviewResponse]:
    """Open a human review of a document."""
    opened = await review.open(
        organization_id=organization_id,
        document_id=document_id,
        reason=payload.reason,
        priority=payload.priority,
        due_hours=payload.due_hours,
        assigned_to=payload.assigned_to,
    )
    if notifications is not None and payload.assigned_to:
        document = await repos.documents.require_in_org(organization_id, document_id)
        await notifications.send_review_assigned(
            payload.assigned_to,
            title=document.title,
            reason=payload.reason,
            due_at=opened.due_at.isoformat() if opened.due_at else None,
        )
    return SuccessResponse(
        message="Review opened.",
        data=ReviewResponse.model_validate(opened, from_attributes=True),
        meta=_meta(),
    )


@router.get(
    "/{document_id}/reviews",
    response_model=SuccessResponse[list[ReviewResponse]],
    summary="List a document's reviews",
)
async def list_reviews(
    document_id: UUID, organization_id: OrganizationId, repos: Repos
) -> SuccessResponse[list[ReviewResponse]]:
    """Every review of a document, newest first."""
    await repos.documents.require_in_org(organization_id, document_id)
    rows = await repos.reviews.list_for_document(document_id)
    return SuccessResponse(
        message="Reviews retrieved.",
        data=[ReviewResponse.model_validate(row, from_attributes=True) for row in rows],
        meta=_meta(),
    )


@router.post(
    "/{document_id}/review/{review_id}/decision",
    response_model=SuccessResponse[ReviewOutcomeResponse],
    summary="Close a review with a decision",
)
async def decide_review(
    document_id: UUID,
    review_id: UUID,
    payload: ReviewDecisionRequest,
    organization_id: OrganizationId,
    user_id: CurrentUserId,
    review: Review,
    repos: Repos,
    notifications: Notifications,
) -> SuccessResponse[ReviewOutcomeResponse]:
    """Close a review, applying any corrections."""
    await repos.documents.require_in_org(organization_id, document_id)
    outcome = await review.complete(
        organization_id=organization_id,
        review_id=review_id,
        reviewer_id=user_id,
        decision=payload.decision,
        corrections=payload.corrections,
        comment=payload.comment,
        annotations=payload.annotations,
    )
    if notifications is not None:
        document = await repos.documents.require_in_org(organization_id, document_id)
        await notifications.send_review_completed(
            user_id,
            title=document.title,
            decision=str(payload.decision),
            corrections=outcome.corrections_applied,
        )
    data = ReviewOutcomeResponse(
        review=ReviewResponse.model_validate(outcome.review, from_attributes=True),
        document_status=outcome.document_status,
        corrections_applied=outcome.corrections_applied,
        fields_corrected=outcome.fields_corrected,
        requeued=outcome.requeued,
    )
    return SuccessResponse(message="Review completed.", data=data, meta=_meta())


# ---- shared plumbing -----------------------------------------------------------------


async def _run(
    *,
    stages: tuple[ProcessingStage, ...],
    document_id: UUID,
    organization_id: UUID,
    user_id: str,
    ingestion: Ingestion,
    pipeline: Pipeline,
    repos: Repos,
    notifications: Notifications,
    storage: Storage,
    message: str,
    priority: int = 50,
) -> SuccessResponse[ProcessResponse]:
    """Queue and run one pipeline pass, returning what it did.

    Synchronous on purpose for these endpoints: a caller who asked for
    re-extraction wants the result, and a 202 with a job id makes them
    poll. The worker path exists for the bulk case.
    """
    job = await ingestion.requeue(
        organization_id=organization_id,
        document_id=document_id,
        stages=stages,
        priority=priority,
        requested_by=user_id,
    )
    document = await repos.documents.require_in_org(organization_id, document_id)
    data = await _load_bytes(document, storage)
    result = await pipeline.run(job, data)

    if notifications is not None:
        await notifications.send_processing_completed(
            user_id,
            title=document.title,
            failed_stages=[str(stage) for stage in result.failed_stages],
            requires_review=result.requires_review,
        )
    payload = ProcessResponse(
        job=JobResponse.model_validate(result.job, from_attributes=True),
        version_number=result.version.version_number if result.version else None,
        outcomes=[
            StageOutcomeResponse(
                stage=item.stage,
                succeeded=item.succeeded,
                duration_ms=round(item.duration_ms, 3),
                detail=item.detail,
                error=item.error,
            )
            for item in result.outcomes
        ],
        requires_review=result.requires_review,
        review_reason=result.review_reason,
    )
    return SuccessResponse(message=message, data=payload, meta=_meta())


async def _load_bytes(document: object, storage: Storage) -> bytes:
    """The document's original bytes, read from the object store.

    The original bytes, never the extracted text: text is what parsing
    *produced*, so reconstructing from it would make a document's first
    processing run impossible and every later run a re-parse of a previous
    parse rather than of the document.

    Raises:
        ValidationError: When no object store is configured, which is a
            deployment that can serve reads but cannot process anything.
            Said plainly rather than returning an empty document.
    """
    if storage is None:
        raise ValidationError(
            "No document object store is configured on this deployment, so the "
            "original bytes cannot be read and the document cannot be processed."
        )
    return await storage.get(
        bucket=document.storage_bucket,  # type: ignore[attr-defined]
        key=document.storage_key,  # type: ignore[attr-defined]
    )


def _summary(row: object) -> DocumentSummaryResponse:
    """A document listing entry."""
    return DocumentSummaryResponse(
        id=row.id,  # type: ignore[attr-defined]
        title=row.title,  # type: ignore[attr-defined]
        filename=row.filename,  # type: ignore[attr-defined]
        document_format=row.document_format,  # type: ignore[attr-defined]
        status=row.status,  # type: ignore[attr-defined]
        byte_size=row.byte_size,  # type: ignore[attr-defined]
        page_count=row.page_count,  # type: ignore[attr-defined]
        word_count=row.word_count,  # type: ignore[attr-defined]
        requires_ocr=row.requires_ocr,  # type: ignore[attr-defined]
        requires_review=row.requires_review,  # type: ignore[attr-defined]
        review_reason=row.review_reason,  # type: ignore[attr-defined]
        overall_confidence=row.overall_confidence,  # type: ignore[attr-defined]
        is_duplicate=row.duplicate_of_id is not None,  # type: ignore[attr-defined]
        tags=list(row.tags or []),  # type: ignore[attr-defined]
        created_at=row.created_at,  # type: ignore[attr-defined]
        updated_at=row.updated_at,  # type: ignore[attr-defined]
    )


def _detail(row: object) -> DocumentDetailResponse:
    """A document detail entry."""
    base = _summary(row).model_dump()
    return DocumentDetailResponse(
        **base,
        description=row.description,  # type: ignore[attr-defined]
        content_type=row.content_type,  # type: ignore[attr-defined]
        checksum=row.checksum,  # type: ignore[attr-defined]
        current_version_number=row.current_version_number,  # type: ignore[attr-defined]
        mean_ocr_confidence=row.mean_ocr_confidence,  # type: ignore[attr-defined]
        lowest_page_confidence=row.lowest_page_confidence,  # type: ignore[attr-defined]
        ocr_completed=row.ocr_completed,  # type: ignore[attr-defined]
        processing_duration_ms=row.processing_duration_ms,  # type: ignore[attr-defined]
        duplicate_of_id=row.duplicate_of_id,  # type: ignore[attr-defined]
        owner_id=row.owner_id,  # type: ignore[attr-defined]
        uploaded_by=row.uploaded_by,  # type: ignore[attr-defined]
        error=row.error,  # type: ignore[attr-defined]
    )


def _table(row: object) -> TableResponse:
    """A table response, warning where the rendering is lossy."""
    warning = None
    if row.has_merged_cells:  # type: ignore[attr-defined]
        warning = (
            "This table contains merged cells. A flat rendering repeats the "
            "merged value, which is not a real repetition in the source."
        )
    return TableResponse(
        id=row.id,  # type: ignore[attr-defined]
        sequence=row.sequence,  # type: ignore[attr-defined]
        caption=row.caption,  # type: ignore[attr-defined]
        headers=list(row.headers or []),  # type: ignore[attr-defined]
        rows=[list(cells) for cells in (row.rows or [])],  # type: ignore[attr-defined]
        row_count=row.row_count,  # type: ignore[attr-defined]
        column_count=row.column_count,  # type: ignore[attr-defined]
        has_header_row=row.has_header_row,  # type: ignore[attr-defined]
        has_merged_cells=row.has_merged_cells,  # type: ignore[attr-defined]
        spans_pages=row.spans_pages,  # type: ignore[attr-defined]
        confidence=row.confidence,  # type: ignore[attr-defined]
        warning=warning,
    )


def _statistic(row: DocumentStatistic) -> StatisticResponse:
    """One statistics window as a response."""
    return StatisticResponse.model_validate(row, from_attributes=True)


def _report(row: DocumentReport, *, rendered: str | None) -> ReportResponse:
    """One report as a response."""
    return ReportResponse(
        id=row.id,
        kind=ReportKind(str(row.kind)),
        report_format=ReportFormat(str(row.report_format)),
        title=row.title,
        status=str(row.status),
        row_count=row.row_count,
        content=dict(row.content or {}),
        rendered=rendered,
        generated_at=row.generated_at,
        duration_ms=row.duration_ms,
        error=row.error,
    )


__all__ = ["router"]
