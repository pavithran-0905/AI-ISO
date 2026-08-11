"""The ``/rag`` surface (docs/062 "REST APIs" -- the 13 literal endpoints).

**Registration order inside this router matters.** Every route with a
static path segment (``/documents/search``, ``/documents/{id}/content``)
is declared before ``GET/PUT/DELETE /documents/{document_id}``.
FastAPI/Starlette matches in registration order and ``{document_id}`` is
a catch-all at that same one-segment shape -- declared first it would
hijack ``GET /rag/documents/search`` as ``document_id="search"`` and fail
UUID parsing before the request reached the handler that owns the path.
The same bug class already found and fixed in
notification-center-service, plugin-marketplace-service,
ai-agent-platform-service, and prompt-management-service.

**Every route authenticates, including the read-only ones.** Retrieval
reads across a corpus the caller has never seen; an unauthenticated
search endpoint is a corpus-wide disclosure with a nice JSON envelope.
The read routes take :data:`~app.api.deps.Caller`, which cannot be built
without a verified token -- so authentication is structural here rather
than remembered.
"""

from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from shared_core.exceptions.validation import ValidationError
from shared_core.logging.context import get_log_context

from app.api.deps import (
    AnalyticsSvc,
    AuditRepo,
    Caller,
    DocumentSvc,
    IndexingSvc,
    IngestionSvc,
    JobsRepo,
    ReportsRepo,
    RetrievalSvc,
    ServiceSettings,
    SourceSvc,
    StatisticsRepo,
)
from app.context.assembler import AssembledContext
from app.models.enums import (
    DocumentStatus,
    IndexKind,
    ReportKind,
)
from app.schemas.analytics import (
    AuditResponse,
    ReportRequest,
    ReportResponse,
    SourceCreateRequest,
    SourceResponse,
    SourceUpdateRequest,
    StatisticResponse,
    SyncReportRequest,
)
from app.schemas.document import (
    DocumentChunkResponse,
    DocumentIngestRequest,
    DocumentResponse,
    DocumentUpdateRequest,
    DocumentVersionResponse,
    IndexingJobResponse,
    IndexRequest,
    IndexResultResponse,
    IngestionResponse,
    ReindexRequest,
)
from app.schemas.response import ResponseMeta, SuccessResponse
from app.schemas.retrieval import (
    CitationResponse,
    ContextRequest,
    ContextResponse,
    EvaluationResponse,
    FeedbackRequest,
    FeedbackResponse,
    MetricResponse,
    RetrievalResponse,
    RetrieveRequest,
    SearchHitResponse,
    SearchRequest,
)
from app.services.indexing import IndexResult
from app.services.retrieval import RetrievalOutput
from app.services.sources import SyncOutcome

router = APIRouter(prefix="/rag", tags=["RAG"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _decode(content_base64: str) -> bytes:
    """Decode an uploaded body.

    Raises:
        ValidationError: If the payload is not valid base64. Validated
            strictly -- ``validate=False`` silently discards characters
            outside the alphabet, which would let a truncated or corrupted
            upload decode into *something* and be ingested as if it were
            the document somebody sent.
    """
    try:
        return base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValidationError(
            f"content_base64 is not valid base64: {exc}. The field must hold the "
            "document's raw bytes, base64-encoded."
        ) from exc


def _retrieval_response(output: RetrievalOutput) -> RetrievalResponse:
    """Render one retrieval, without its context block."""
    return RetrievalResponse(
        query_id=output.query.id,
        query=output.query.query_text,
        strategy=output.query.strategy,
        outcome=output.query.outcome,
        results=[
            SearchHitResponse(
                chunk_id=item.chunk.id,
                document_id=item.document.id,
                document_title=item.document.title,
                rank=item.rank,
                score=item.score,
                content=item.chunk.content,
                page_number=item.chunk.page_number,
                section_path=item.chunk.section_path,
                heading=item.chunk.heading,
                arm_scores=item.arm_scores,
                arm_ranks=item.arm_ranks,
            )
            for item in output.results
        ],
        candidates=output.candidates,
        denied=output.denied,
        duration_ms=output.query.duration_ms,
        embedding_ms=output.query.embedding_ms,
        search_ms=output.query.search_ms,
        rerank_ms=output.query.rerank_ms,
    )


def _context_response(query_id: UUID, assembled: AssembledContext) -> list[CitationResponse]:
    """Render the citations of one assembled context block."""
    return [
        CitationResponse(
            label=citation.label,
            chunk_key=citation.chunk_key,
            document_id=citation.document_id,
            document_title=citation.document_title,
            page_number=citation.page_number,
            section_path=citation.section_path,
            source_uri=citation.source_uri,
            score=citation.score,
            rendered=citation.render(),
        )
        for citation in assembled.citations
    ]


def _index_result(result: IndexResult) -> IndexResultResponse:
    """Render one document's indexing outcome."""
    return IndexResultResponse(
        document_id=result.document_id,
        embedded=result.embedded,
        reused=result.reused,
        skipped=result.skipped,
        tokens=result.tokens,
        cost_usd=round(result.cost_usd, 8),
        error=result.error,
    )


def _capped(requested: int, settings: ServiceSettings) -> int:
    """*requested* clamped to the deployment's own ceiling.

    Clamped rather than refused: a caller asking for more than the
    deployment allows gets the deployment's maximum, which is what they
    would have asked for had they known it. A 422 here would break a
    client over a limit it cannot see.
    """
    return min(requested, settings.max_top_k)


# ---- documents: static segments first; see this module's own docstring ------


@router.post(
    "/documents",
    response_model=SuccessResponse[IngestionResponse],
    status_code=201,
    summary="Ingest a document",
)
async def ingest_document(
    body: DocumentIngestRequest,
    caller: Caller,
    ingestion: IngestionSvc,
) -> SuccessResponse[IngestionResponse]:
    """Parse, scan, chunk, and store one document.

    Indexing is deliberately separate -- see ``POST /rag/index``. A parse
    failure should not consume an embedding quota, and an embedding
    outage should not lose a parse.
    """
    result = await ingestion.ingest(
        organization_id=caller.organization_id,
        data=_decode(body.content_base64),
        title=body.title,
        filename=body.filename,
        content_type=body.content_type,
        source_kind=body.source_kind,
        external_id=body.external_id,
        knowledge_source_id=body.knowledge_source_id,
        classification=body.classification,
        allowed_roles=body.allowed_roles,
        tags=body.tags,
        project_scope_id=body.project_scope_id,
        source_uri=body.source_uri,
        chunk_strategy=body.chunk_strategy,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
        ingested_by=caller.user_id,
    )
    payload = IngestionResponse(
        document=DocumentResponse.model_validate(result.document),
        version_number=result.version.version_number if result.version else None,
        chunk_count=result.chunk_count,
        unchanged=result.unchanged,
        blocked=result.blocked,
        findings=result.findings,
        warnings=result.warnings,
    )
    message = (
        "Ingestion was blocked by scanning."
        if result.blocked
        else (
            "Content was unchanged; nothing was re-parsed."
            if result.unchanged
            else "Document ingested."
        )
    )
    return SuccessResponse(message=message, data=payload, meta=_meta())


@router.get(
    "/documents",
    response_model=SuccessResponse[list[DocumentResponse]],
    summary="List documents",
)
async def list_documents(
    caller: Caller,
    documents: DocumentSvc,
    status: DocumentStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SuccessResponse[list[DocumentResponse]]:
    """Documents this caller may see, newest first."""
    rows = await documents.list_documents(caller, status=status, limit=limit, offset=offset)
    return SuccessResponse(
        message="Documents listed.",
        data=[DocumentResponse.model_validate(row) for row in rows],
        meta=_meta(),
    )


@router.get(
    "/documents/search",
    response_model=SuccessResponse[list[DocumentResponse]],
    summary="Search documents by title",
)
async def search_documents(
    caller: Caller,
    documents: DocumentSvc,
    q: Annotated[str, Query(min_length=1, max_length=512)],
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> SuccessResponse[list[DocumentResponse]]:
    """Title and description search over documents this caller may see.

    Distinct from ``POST /rag/search``, which searches document *content*.
    This one answers "which document was that?", not "what does the corpus
    say about this?".
    """
    rows = await documents.search_documents(caller, q, limit=limit)
    return SuccessResponse(
        message="Documents searched.",
        data=[DocumentResponse.model_validate(row) for row in rows],
        meta=_meta(),
    )


@router.get(
    "/documents/{document_id}/content",
    response_model=SuccessResponse[DocumentVersionResponse],
    summary="Read a document's extracted text",
)
async def read_document_content(
    document_id: UUID, caller: Caller, documents: DocumentSvc
) -> SuccessResponse[DocumentVersionResponse]:
    """The live version's extracted text.

    Its own endpoint rather than a field on the document response: a
    listing of a thousand documents would otherwise ship a thousand
    documents' worth of text into every log and proxy cache on the way.
    """
    version = await documents.get_current_version(caller, document_id)
    return SuccessResponse(
        message="Content returned.",
        data=DocumentVersionResponse.model_validate(version),
        meta=_meta(),
    )


@router.get(
    "/documents/{document_id}/chunks",
    response_model=SuccessResponse[list[DocumentChunkResponse]],
    summary="List a document's chunks",
)
async def list_document_chunks(
    document_id: UUID,
    caller: Caller,
    documents: DocumentSvc,
    limit: Annotated[int, Query(ge=1, le=10_000)] = 1_000,
) -> SuccessResponse[list[DocumentChunkResponse]]:
    """The live version's chunks, in document order."""
    rows = await documents.list_chunks(caller, document_id, limit=limit)
    return SuccessResponse(
        message="Chunks listed.",
        data=[DocumentChunkResponse.model_validate(row) for row in rows],
        meta=_meta(),
    )


@router.post(
    "/documents/{document_id}/restore",
    response_model=SuccessResponse[DocumentResponse],
    summary="Restore an archived document",
)
async def restore_document(
    document_id: UUID, caller: Caller, documents: DocumentSvc
) -> SuccessResponse[DocumentResponse]:
    """Return an archived document to the corpus.

    A *deleted* document cannot be restored: its embeddings are gone, so
    putting the row back would add something retrieval can never return.
    """
    document = await documents.restore_document(caller, document_id)
    return SuccessResponse(
        message="Document restored.",
        data=DocumentResponse.model_validate(document),
        meta=_meta(),
    )


@router.get(
    "/documents/{document_id}",
    response_model=SuccessResponse[DocumentResponse],
    summary="Read one document",
)
async def read_document(
    document_id: UUID, caller: Caller, documents: DocumentSvc
) -> SuccessResponse[DocumentResponse]:
    """One document, without its text."""
    document = await documents.get_document(caller, document_id)
    return SuccessResponse(
        message="Document returned.",
        data=DocumentResponse.model_validate(document),
        meta=_meta(),
    )


@router.put(
    "/documents/{document_id}",
    response_model=SuccessResponse[DocumentResponse],
    summary="Update a document",
)
async def update_document(
    document_id: UUID,
    body: DocumentUpdateRequest,
    caller: Caller,
    documents: DocumentSvc,
) -> SuccessResponse[DocumentResponse]:
    """Change a document's descriptive and access fields.

    Content is not editable: it comes from a parse of the original bytes,
    and editing it in place would break the guarantee versions exist for.
    Re-ingest to change content.
    """
    document = await documents.update_document(
        caller,
        document_id,
        title=body.title,
        description=body.description,
        classification=body.classification,
        allowed_roles=body.allowed_roles,
        tags=body.tags,
        owner_id=body.owner_id,
        expires_at=body.expires_at,
        metadata=body.metadata,
    )
    return SuccessResponse(
        message="Document updated.",
        data=DocumentResponse.model_validate(document),
        meta=_meta(),
    )


@router.delete(
    "/documents/{document_id}",
    response_model=SuccessResponse[DocumentResponse],
    summary="Delete or archive a document",
)
async def delete_document(
    document_id: UUID,
    caller: Caller,
    documents: DocumentSvc,
    archive: Annotated[bool, Query()] = False,
) -> SuccessResponse[DocumentResponse]:
    """Remove a document from retrieval.

    ``archive=true`` is reversible and keeps the embeddings, so restoring
    costs nothing. The default destroys the embeddings and soft-deletes
    the row: keeping the vectors beside a row marked deleted would leave
    the content fully retrievable under a record saying it was removed.
    """
    document = (
        await documents.archive_document(caller, document_id)
        if archive
        else await documents.delete_document(caller, document_id)
    )
    return SuccessResponse(
        message="Document archived." if archive else "Document deleted.",
        data=DocumentResponse.model_validate(document),
        meta=_meta(),
    )


# ---- indexing ---------------------------------------------------------------


@router.post(
    "/index",
    response_model=SuccessResponse[IndexResultResponse | IndexingJobResponse],
    summary="Index a document, or queue a sweep",
)
async def index_documents(
    body: IndexRequest,
    caller: Caller,
    indexing: IndexingSvc,
) -> SuccessResponse[IndexResultResponse | IndexingJobResponse]:
    """Index one document synchronously, or queue an incremental sweep.

    Naming a document indexes it now, because a caller who just uploaded
    one wants to know whether it worked. Naming none queues a job, because
    a corpus-wide sweep does not belong inside a request that has to
    answer.
    """
    if body.document_id is not None:
        result = await indexing.index_document(
            caller.organization_id, body.document_id, force=body.force
        )
        return SuccessResponse(
            message="Document indexed." if result.succeeded else "Indexing failed.",
            data=_index_result(result),
            meta=_meta(),
        )

    job = await indexing.queue_job(
        caller.organization_id,
        kind=IndexKind.INCREMENTAL,
        knowledge_source_id=body.knowledge_source_id,
        priority=body.priority,
        requested_by=caller.user_id,
    )
    return SuccessResponse(
        message="Indexing job queued.",
        data=IndexingJobResponse.model_validate(job),
        meta=_meta(),
    )


@router.post(
    "/reindex",
    response_model=SuccessResponse[IndexingJobResponse],
    status_code=202,
    summary="Queue a reindex",
)
async def reindex(
    body: ReindexRequest,
    caller: Caller,
    indexing: IndexingSvc,
) -> SuccessResponse[IndexingJobResponse]:
    """Queue a full or incremental reindex.

    Always asynchronous, and 202 rather than 200: a full reindex of a real
    corpus outlives any sensible request timeout, and returning 200 would
    promise it had finished.
    """
    job = await indexing.queue_job(
        caller.organization_id,
        kind=IndexKind.FULL if body.full else IndexKind.INCREMENTAL,
        knowledge_source_id=body.knowledge_source_id,
        priority=body.priority,
        requested_by=caller.user_id,
    )
    return SuccessResponse(
        message="Reindex queued.",
        data=IndexingJobResponse.model_validate(job),
        meta=_meta(),
    )


@router.get(
    "/index/jobs",
    response_model=SuccessResponse[list[IndexingJobResponse]],
    summary="List indexing jobs",
)
async def list_indexing_jobs(
    caller: Caller,
    jobs: JobsRepo,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SuccessResponse[list[IndexingJobResponse]]:
    """Indexing jobs in this organization, newest first."""
    rows = await jobs.list_for_org(caller.organization_id, limit=limit, offset=offset)
    return SuccessResponse(
        message="Indexing jobs listed.",
        data=[IndexingJobResponse.model_validate(row) for row in rows],
        meta=_meta(),
    )


# ---- retrieval ---------------------------------------------------------------


@router.post(
    "/search",
    response_model=SuccessResponse[RetrievalResponse],
    summary="Search the corpus",
)
async def search(
    body: SearchRequest,
    caller: Caller,
    retrieval: RetrievalSvc,
    settings: ServiceSettings,
) -> SuccessResponse[RetrievalResponse]:
    """Ranked chunks, with no context assembly."""
    output = await retrieval.retrieve(
        caller,
        body.query,
        strategy=body.strategy,
        fusion_method=body.fusion_method,
        rerank_method=body.rerank_method,
        top_k=_capped(body.top_k, settings),
        min_similarity=body.min_similarity,
        metadata_filters=body.metadata_filters,
        document_ids=body.document_ids,
        weights=body.weights,
    )
    return SuccessResponse(
        message="Search completed.", data=_retrieval_response(output), meta=_meta()
    )


@router.post(
    "/retrieve",
    response_model=SuccessResponse[RetrievalResponse],
    summary="Retrieve chunks for a query",
)
async def retrieve(
    body: RetrieveRequest,
    caller: Caller,
    retrieval: RetrievalSvc,
    settings: ServiceSettings,
) -> SuccessResponse[RetrievalResponse]:
    """The same search, framed as retrieval for a downstream generator."""
    output = await retrieval.retrieve(
        caller,
        body.query,
        strategy=body.strategy,
        fusion_method=body.fusion_method,
        rerank_method=body.rerank_method,
        top_k=_capped(body.top_k, settings),
        min_similarity=body.min_similarity,
        metadata_filters=body.metadata_filters,
        document_ids=body.document_ids,
        weights=body.weights,
    )
    return SuccessResponse(
        message="Retrieval completed.", data=_retrieval_response(output), meta=_meta()
    )


@router.post(
    "/context",
    response_model=SuccessResponse[ContextResponse],
    summary="Assemble a context block",
)
async def build_context(
    body: ContextRequest,
    caller: Caller,
    retrieval: RetrievalSvc,
    settings: ServiceSettings,
) -> SuccessResponse[ContextResponse]:
    """Retrieve and assemble a token-budgeted, cited context block."""
    output = await retrieval.build_context(
        caller,
        body.query,
        max_tokens=min(body.max_tokens, settings.max_context_tokens),
        include_citations=body.include_citations,
        allow_partial=body.allow_partial,
        strategy=body.strategy,
        fusion_method=body.fusion_method,
        rerank_method=body.rerank_method,
        top_k=_capped(body.top_k, settings),
        min_similarity=body.min_similarity,
        metadata_filters=body.metadata_filters,
        document_ids=body.document_ids,
        weights=body.weights,
    )
    assembled = output.context
    payload = ContextResponse(
        query_id=output.retrieval.query.id,
        text=assembled.text,
        citations=_context_response(output.retrieval.query.id, assembled),
        included=assembled.included,
        excluded=assembled.excluded,
        duplicates_dropped=assembled.duplicates_dropped,
        token_count=assembled.token_count,
        budget=assembled.budget,
        truncated=assembled.truncated,
        retrieval=_retrieval_response(output.retrieval),
    )
    return SuccessResponse(message="Context assembled.", data=payload, meta=_meta())


@router.post(
    "/retrieve/{query_id}/feedback",
    response_model=SuccessResponse[FeedbackResponse],
    status_code=201,
    summary="Submit retrieval feedback",
)
async def submit_feedback(
    query_id: UUID,
    body: FeedbackRequest,
    caller: Caller,
    retrieval: RetrievalSvc,
) -> SuccessResponse[FeedbackResponse]:
    """Record one human judgement about one retrieval.

    The ground truth every offline metric is measured against. Without it
    this service can report how fast it was, never how right.
    """
    recorded = await retrieval.submit_feedback(
        caller,
        query_id,
        verdict=body.verdict,
        chunk_id=body.chunk_id,
        rank=body.rank,
        relevance=body.relevance,
        comment=body.comment,
    )
    return SuccessResponse(
        message="Feedback recorded.",
        data=FeedbackResponse.model_validate(recorded),
        meta=_meta(),
    )


@router.get(
    "/retrieve/{query_id}/evaluation",
    response_model=SuccessResponse[list[MetricResponse]],
    summary="Evaluate one retrieval",
)
async def evaluate_one(
    query_id: UUID,
    caller: Caller,
    analytics: AnalyticsSvc,
    k: Annotated[int, Query(ge=1, le=500)] = 10,
) -> SuccessResponse[list[MetricResponse]]:
    """Every metric for one query, unaveraged."""
    measured = await analytics.evaluate_query(caller.organization_id, query_id, k=k)
    return SuccessResponse(
        message="Retrieval evaluated.",
        data=[
            MetricResponse(
                name=result.name,
                value=result.value,
                considered=result.considered,
                relevant_total=result.relevant_total,
                measurable=result.is_measurable,
            )
            for result in measured.values()
        ],
        meta=_meta(),
    )


# ---- sources -----------------------------------------------------------------


@router.post(
    "/sources",
    response_model=SuccessResponse[SourceResponse],
    status_code=201,
    summary="Register a knowledge source",
)
async def create_source(
    body: SourceCreateRequest, caller: Caller, sources: SourceSvc
) -> SuccessResponse[SourceResponse]:
    """Register a configured place documents come from."""
    source = await sources.create_source(
        caller.organization_id,
        slug=body.slug,
        name=body.name,
        source_kind=body.source_kind,
        description=body.description,
        uri=body.uri,
        credential_reference=body.credential_reference,
        sync_enabled=body.sync_enabled,
        sync_interval_seconds=body.sync_interval_seconds,
        default_classification=body.default_classification,
        default_tags=body.default_tags,
        allowed_roles=body.allowed_roles,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
        chunk_strategy=body.chunk_strategy,
        configuration=body.configuration,
        created_by=caller.user_id,
    )
    return SuccessResponse(
        message="Knowledge source registered.",
        data=SourceResponse.model_validate(source),
        meta=_meta(),
    )


@router.get(
    "/sources",
    response_model=SuccessResponse[list[SourceResponse]],
    summary="List knowledge sources",
)
async def list_sources(
    caller: Caller,
    sources: SourceSvc,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SuccessResponse[list[SourceResponse]]:
    """Every source in this organization, newest first."""
    rows = await sources.list_sources(caller.organization_id, limit=limit, offset=offset)
    return SuccessResponse(
        message="Knowledge sources listed.",
        data=[SourceResponse.model_validate(row) for row in rows],
        meta=_meta(),
    )


@router.post(
    "/sources/{source_id}/sync",
    response_model=SuccessResponse[SourceResponse],
    summary="Report a sync outcome",
)
async def report_sync(
    source_id: UUID,
    body: SyncReportRequest,
    caller: Caller,
    sources: SourceSvc,
) -> SuccessResponse[SourceResponse]:
    """Record what a connector's sync attempt produced.

    The seam between this service and whatever actually talks to
    Confluence, SharePoint, or S3 -- none of which ships here, because no
    instance of any of them exists in this platform's infrastructure to
    have tested a client against.
    """
    claimed = await sources.claim_for_sync(caller.organization_id, source_id)
    updated = await sources.record_sync(
        SyncOutcome(
            source=claimed,
            documents_seen=body.documents_seen,
            documents_ingested=body.documents_ingested,
            documents_failed=body.documents_failed,
            cursor=body.cursor,
            error=body.error,
        )
    )
    return SuccessResponse(
        message="Sync recorded.", data=SourceResponse.model_validate(updated), meta=_meta()
    )


@router.get(
    "/sources/{source_id}",
    response_model=SuccessResponse[SourceResponse],
    summary="Read one knowledge source",
)
async def read_source(
    source_id: UUID, caller: Caller, sources: SourceSvc
) -> SuccessResponse[SourceResponse]:
    """One knowledge source."""
    source = await sources.get_source(caller.organization_id, source_id)
    return SuccessResponse(
        message="Knowledge source returned.",
        data=SourceResponse.model_validate(source),
        meta=_meta(),
    )


@router.put(
    "/sources/{source_id}",
    response_model=SuccessResponse[SourceResponse],
    summary="Update a knowledge source",
)
async def update_source(
    source_id: UUID,
    body: SourceUpdateRequest,
    caller: Caller,
    sources: SourceSvc,
) -> SuccessResponse[SourceResponse]:
    """Reconfigure a source. Slug and kind are identity and not editable."""
    source = await sources.update_source(
        caller.organization_id,
        source_id,
        name=body.name,
        description=body.description,
        uri=body.uri,
        credential_reference=body.credential_reference,
        is_enabled=body.is_enabled,
        sync_enabled=body.sync_enabled,
        sync_interval_seconds=body.sync_interval_seconds,
        default_classification=body.default_classification,
        default_tags=body.default_tags,
        allowed_roles=body.allowed_roles,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
        chunk_strategy=body.chunk_strategy,
        configuration=body.configuration,
        updated_by=caller.user_id,
    )
    return SuccessResponse(
        message="Knowledge source updated.",
        data=SourceResponse.model_validate(source),
        meta=_meta(),
    )


@router.delete(
    "/sources/{source_id}",
    response_model=SuccessResponse[SourceResponse],
    summary="Retire a knowledge source",
)
async def delete_source(
    source_id: UUID, caller: Caller, sources: SourceSvc
) -> SuccessResponse[SourceResponse]:
    """Retire a source, leaving its documents in place.

    The documents keep their content and stay retrievable. Cascading the
    delete would remove a corpus because somebody removed a *schedule*.
    """
    source = await sources.delete_source(
        caller.organization_id, source_id, deleted_by=caller.user_id
    )
    return SuccessResponse(
        message="Knowledge source retired.",
        data=SourceResponse.model_validate(source),
        meta=_meta(),
    )


# ---- statistics and reports ----------------------------------------------------


@router.get(
    "/statistics",
    response_model=SuccessResponse[list[StatisticResponse]],
    summary="Read RAG statistics",
)
async def read_statistics(
    caller: Caller,
    analytics: AnalyticsSvc,
    statistics: StatisticsRepo,
    days: Annotated[int, Query(ge=1, le=365)] = 7,
    refresh: Annotated[bool, Query()] = False,
) -> SuccessResponse[list[StatisticResponse]]:
    """Rolled-up windows, oldest first.

    ``refresh=true`` computes a window now instead of waiting for the
    rollup worker -- which is what a dashboard opened straight after a
    bulk import needs, since the worker's window has not closed yet.
    """
    if refresh:
        await analytics.compute_statistics(caller.organization_id)
    rows = await statistics.list_since(
        caller.organization_id, since=datetime.now(UTC) - timedelta(days=days)
    )
    return SuccessResponse(
        message="Statistics returned.",
        data=[StatisticResponse.model_validate(row) for row in rows],
        meta=_meta(),
    )


@router.get(
    "/statistics/evaluation",
    response_model=SuccessResponse[EvaluationResponse],
    summary="Evaluate retrieval quality",
)
async def read_evaluation(
    caller: Caller,
    analytics: AnalyticsSvc,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    k: Annotated[int, Query(ge=1, le=500)] = 10,
) -> SuccessResponse[EvaluationResponse]:
    """Averaged metrics over judged queries only.

    A query nobody judged is excluded rather than scored zero: including
    it would drive every metric towards zero in proportion to how little
    feedback exists, so the service would look worse the less anyone
    reviewed it.
    """
    summary = await analytics.evaluate(
        caller.organization_id, since=datetime.now(UTC) - timedelta(days=days), k=k
    )
    return SuccessResponse(
        message="Retrieval evaluated.",
        data=EvaluationResponse(
            queries_evaluated=summary.queries_evaluated,
            measurable=summary.is_measurable,
            metrics=summary.metrics,
            unmeasurable=summary.unmeasurable,
        ),
        meta=_meta(),
    )


@router.get(
    "/reports",
    response_model=SuccessResponse[list[ReportResponse]],
    summary="List generated reports",
)
async def list_reports(
    caller: Caller,
    reports: ReportsRepo,
    kind: ReportKind | None = None,
) -> SuccessResponse[list[ReportResponse]]:
    """Reports for this organization, newest first."""
    rows = await reports.list_for_org(caller.organization_id, kind=kind)
    return SuccessResponse(
        message="Reports listed.",
        data=[ReportResponse.model_validate(row) for row in rows],
        meta=_meta(),
    )


@router.post(
    "/reports",
    response_model=SuccessResponse[ReportResponse],
    status_code=201,
    summary="Generate a report",
)
async def generate_report(
    body: ReportRequest, caller: Caller, analytics: AnalyticsSvc
) -> SuccessResponse[ReportResponse]:
    """Build one report and store it.

    A failed report is returned as ``FAILED`` with its reason rather than
    raising: reports are scheduled artefacts as often as interactive ones,
    and a nightly job that vanishes on error leaves nothing to explain the
    gap.
    """
    report = await analytics.generate_report(
        caller.organization_id,
        body.kind,
        report_format=body.report_format,
        since=body.since,
        title=body.title,
        generated_by=caller.user_id,
    )
    return SuccessResponse(
        message="Report generated.", data=ReportResponse.model_validate(report), meta=_meta()
    )


@router.get(
    "/audit",
    response_model=SuccessResponse[list[AuditResponse]],
    summary="Read the audit trail",
)
async def read_audit(
    caller: Caller,
    audit: AuditRepo,
    limit: Annotated[int, Query(ge=1, le=1_000)] = 200,
) -> SuccessResponse[list[AuditResponse]]:
    """Recent audit entries, newest first."""
    rows = await audit.list_for_org(caller.organization_id, limit=limit)
    return SuccessResponse(
        message="Audit trail returned.",
        data=[AuditResponse.model_validate(row) for row in rows],
        meta=_meta(),
    )


__all__ = ["router"]
