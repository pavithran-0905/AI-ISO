"""FastAPI dependency injection for the RAG service.

One factory per business service, each building its own repositories from
the request-scoped session -- routes depend on services only.

**The caller's access scope is built here, from their token, and nowhere
else.** :func:`get_access_context` reads roles and clearance from the
verified JWT claims. Reading them from a query parameter or a body field
would let any caller name any clearance, and every access decision in
this service is made against that context.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from shared_core.database.session import session_scope
from shared_core.exceptions.authentication import AuthenticationError
from shared_core.security.jwt import decode_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import RagServiceSettings
from app.embeddings.service import EmbeddingService
from app.graph_rag.retriever import GraphRetriever
from app.models.enums import ClassificationLevel
from app.repositories.analytics import (
    IndexingJobRepository,
    KnowledgeSourceRepository,
    RagAuditRepository,
    RagReportRepository,
    RagStatisticRepository,
)
from app.repositories.document import (
    DocumentChunkRepository,
    DocumentMetadataRepository,
    DocumentRepository,
    DocumentVersionRepository,
)
from app.repositories.embedding import EmbeddingVectorRepository
from app.repositories.retrieval import (
    RerankingResultRepository,
    RetrievalFeedbackRepository,
    RetrievalQueryRepository,
    RetrievalResultRepository,
)
from app.security.access import AccessContext
from app.services.analytics import AnalyticsService
from app.services.documents import DocumentService
from app.services.indexing import IndexingService
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService
from app.services.sources import SourceService
from app.types import EventPublisher
from app.vector_store.base import VectorStore
from app.vector_store.registry import build_store

_bearer_scheme = HTTPBearer(auto_error=False)

ADMINISTRATOR_ROLES = frozenset({"admin", "administrator", "platform_admin", "rag_admin"})
"""Roles that bypass role and project scoping -- never classification. An
administrator's job is to manage the corpus, which does not by itself
entitle them to read every secret in it."""

_CLEARANCE_CLAIM = "clearance"
_ROLES_CLAIM = "roles"
_PROJECTS_CLAIM = "projects"
_ORGANIZATION_CLAIM = "organization_id"


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped database session, committing on success."""
    session_factory = request.app.state.db_session_factory
    async with session_scope(session_factory) as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_event_publisher(request: Request) -> EventPublisher:
    """The process-wide domain-event publisher."""
    return request.app.state.publish_event  # type: ignore[no-any-return]


EventPublisherDep = Annotated[EventPublisher, Depends(get_event_publisher)]


def get_service_settings(request: Request) -> RagServiceSettings:
    """This service's own configuration."""
    return request.app.state.service_settings  # type: ignore[no-any-return]


ServiceSettings = Annotated[RagServiceSettings, Depends(get_service_settings)]


def get_http_client(request: Request) -> httpx.AsyncClient:
    """The process-wide outbound HTTP client."""
    return request.app.state.http_client  # type: ignore[no-any-return]


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


def get_embedding_service(request: Request) -> EmbeddingService:
    """The process-wide embedding service.

    Process-wide rather than per-request because it owns the provider
    client and the vector cache, and rebuilding either per request would
    discard the cache that makes re-embedding free.
    """
    return request.app.state.embeddings  # type: ignore[no-any-return]


Embeddings = Annotated[EmbeddingService, Depends(get_embedding_service)]


def get_graph_retriever(request: Request) -> GraphRetriever | None:
    """The GraphRAG retriever, or ``None`` when GraphRAG is disabled."""
    return request.app.state.graph_retriever  # type: ignore[no-any-return]


Graph = Annotated["GraphRetriever | None", Depends(get_graph_retriever)]


# ---- authentication and access scope ----------------------------------------


async def get_token_claims(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> dict[str, Any]:
    """Verified claims from the caller's Bearer token.

    Raises:
        AuthenticationError: If no valid Bearer token is presented.
    """
    if credentials is None:
        raise AuthenticationError("Authentication required.")
    public_key = request.app.state.jwt_public_key
    return dict(decode_token(credentials.credentials, public_key=public_key))


TokenClaims = Annotated[dict[str, Any], Depends(get_token_claims)]


async def get_current_user_id(claims: TokenClaims) -> UUID:
    """The calling user's id.

    Raises:
        AuthenticationError: If the token carries no usable subject.
    """
    try:
        return UUID(str(claims["sub"]))
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("The token carries no valid subject claim.") from exc


CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]


async def get_access_context(claims: TokenClaims) -> AccessContext:
    """Build the caller's access scope from their verified token.

    **The organization comes from the token and from nowhere else.** Taking
    it as a request parameter -- which is how several earlier AI-IOS
    services accept it -- would be a cross-tenant read here: every
    repository scopes on the value it is given, and
    :func:`~app.security.access.can_read` compares the document's
    organization against the *context's*, so a caller who supplied
    somebody else's organization id would pass both checks and be served
    that tenant's corpus. There is no legitimate cross-tenant retrieval in
    this service, so the parameter is not offered.

    An unrecognised ``clearance`` claim falls back to ``PUBLIC`` rather
    than raising. A token minted by an older issuer, or by one that spells
    a level differently, then sees public documents only -- which is the
    safe direction to fail. Raising instead would take the service down
    for every caller the moment a claim vocabulary drifted; defaulting
    *upwards* would disclose.

    Raises:
        AuthenticationError: If the token names no organization. Failing
            is the only safe option: there is no default tenant, and
            guessing one would either disclose another tenant's corpus or
            silently return nothing.
    """
    raw_organization = claims.get(_ORGANIZATION_CLAIM)
    try:
        organization_id = UUID(str(raw_organization))
    except (TypeError, ValueError) as exc:
        raise AuthenticationError(
            "The token carries no valid organization_id claim, so there is no tenant "
            "to scope this request to."
        ) from exc

    roles = _string_list(claims.get(_ROLES_CLAIM))
    return AccessContext(
        organization_id=organization_id,
        user_id=str(claims.get("sub", "")) or None,
        roles=frozenset(role.strip().lower() for role in roles if role.strip()),
        clearance=_clearance(claims.get(_CLEARANCE_CLAIM)),
        project_scope_ids=frozenset(_uuid_list(claims.get(_PROJECTS_CLAIM))),
        is_administrator=bool(ADMINISTRATOR_ROLES & {role.lower() for role in roles}),
    )


Caller = Annotated[AccessContext, Depends(get_access_context)]


def _clearance(value: object) -> ClassificationLevel:
    """A classification level from a claim, defaulting to ``PUBLIC``."""
    try:
        return ClassificationLevel(str(value))
    except ValueError:
        return ClassificationLevel.PUBLIC


def _string_list(value: object) -> list[str]:
    """A claim that should be a list of strings, however it arrived.

    A comma-separated string is accepted because that is how several
    issuers encode ``roles``, and rejecting it would fail closed in a way
    that looks like a permissions bug rather than a claim-format one.
    """
    if isinstance(value, str):
        return [part for part in value.split(",") if part.strip()]
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value]
    return []


def _uuid_list(value: object) -> list[UUID]:
    """UUIDs from a claim, silently dropping anything malformed.

    Dropping rather than raising: a single unparseable project id would
    otherwise deny the caller every project they legitimately hold.
    """
    resolved: list[UUID] = []
    for item in _string_list(value):
        try:
            resolved.append(UUID(item.strip()))
        except ValueError:
            continue
    return resolved


# ---- repositories -----------------------------------------------------------


def get_documents_repo(session: DbSession) -> DocumentRepository:
    """The current request's document repository."""
    return DocumentRepository(session)


DocumentsRepo = Annotated[DocumentRepository, Depends(get_documents_repo)]


def get_versions_repo(session: DbSession) -> DocumentVersionRepository:
    """The current request's version repository."""
    return DocumentVersionRepository(session)


VersionsRepo = Annotated[DocumentVersionRepository, Depends(get_versions_repo)]


def get_chunks_repo(session: DbSession) -> DocumentChunkRepository:
    """The current request's chunk repository."""
    return DocumentChunkRepository(session)


ChunksRepo = Annotated[DocumentChunkRepository, Depends(get_chunks_repo)]


def get_metadata_repo(session: DbSession) -> DocumentMetadataRepository:
    """The current request's document-metadata repository."""
    return DocumentMetadataRepository(session)


MetadataRepo = Annotated[DocumentMetadataRepository, Depends(get_metadata_repo)]


def get_vectors_repo(session: DbSession) -> EmbeddingVectorRepository:
    """The current request's embedding-vector repository."""
    return EmbeddingVectorRepository(session)


VectorsRepo = Annotated[EmbeddingVectorRepository, Depends(get_vectors_repo)]


def get_jobs_repo(session: DbSession) -> IndexingJobRepository:
    """The current request's indexing-job repository."""
    return IndexingJobRepository(session)


JobsRepo = Annotated[IndexingJobRepository, Depends(get_jobs_repo)]


def get_sources_repo(session: DbSession) -> KnowledgeSourceRepository:
    """The current request's knowledge-source repository."""
    return KnowledgeSourceRepository(session)


SourcesRepo = Annotated[KnowledgeSourceRepository, Depends(get_sources_repo)]


def get_queries_repo(session: DbSession) -> RetrievalQueryRepository:
    """The current request's retrieval-query repository."""
    return RetrievalQueryRepository(session)


QueriesRepo = Annotated[RetrievalQueryRepository, Depends(get_queries_repo)]


def get_results_repo(session: DbSession) -> RetrievalResultRepository:
    """The current request's retrieval-result repository."""
    return RetrievalResultRepository(session)


ResultsRepo = Annotated[RetrievalResultRepository, Depends(get_results_repo)]


def get_rerankings_repo(session: DbSession) -> RerankingResultRepository:
    """The current request's reranking-result repository."""
    return RerankingResultRepository(session)


RerankingsRepo = Annotated[RerankingResultRepository, Depends(get_rerankings_repo)]


def get_feedback_repo(session: DbSession) -> RetrievalFeedbackRepository:
    """The current request's retrieval-feedback repository."""
    return RetrievalFeedbackRepository(session)


FeedbackRepo = Annotated[RetrievalFeedbackRepository, Depends(get_feedback_repo)]


def get_statistics_repo(session: DbSession) -> RagStatisticRepository:
    """The current request's statistics repository."""
    return RagStatisticRepository(session)


StatisticsRepo = Annotated[RagStatisticRepository, Depends(get_statistics_repo)]


def get_reports_repo(session: DbSession) -> RagReportRepository:
    """The current request's report repository."""
    return RagReportRepository(session)


ReportsRepo = Annotated[RagReportRepository, Depends(get_reports_repo)]


def get_audit_repo(session: DbSession) -> RagAuditRepository:
    """The current request's audit repository."""
    return RagAuditRepository(session)


AuditRepo = Annotated[RagAuditRepository, Depends(get_audit_repo)]


# ---- vector store -------------------------------------------------------------


def get_vector_store(
    session: DbSession, settings: ServiceSettings, embeddings: Embeddings
) -> VectorStore:
    """The configured vector store, bound to this request's session.

    Per-request rather than process-wide because the pgvector backend
    reads and writes through a session, and a store holding a session
    from a previous request would write into a transaction that has
    already been committed or rolled back.
    """
    return build_store(
        settings.vector_store,
        session=session,
        model_name=embeddings.model,
        dimensions=embeddings.dimensions,
        embedding_provider=str(embeddings.provider),
    )


Store = Annotated[VectorStore, Depends(get_vector_store)]


# ---- services -----------------------------------------------------------------


def get_ingestion_service(
    documents: DocumentsRepo,
    versions: VersionsRepo,
    chunks: ChunksRepo,
    metadata: MetadataRepo,
    audit: AuditRepo,
    publish: EventPublisherDep,
    settings: ServiceSettings,
) -> IngestionService:
    """The document ingestion pipeline."""
    return IngestionService(
        documents,
        versions,
        chunks,
        metadata,
        audit,
        publish_event=publish,
        chunk_size=settings.default_chunk_size,
        chunk_overlap=settings.default_chunk_overlap,
        max_chunks=settings.max_chunks_per_document,
        max_bytes=settings.max_document_bytes,
        scan_enabled=settings.injection_scanning_enabled,
        block_on_injection=settings.block_ingestion_on_injection,
        redact_pii=settings.redact_pii_on_ingestion,
    )


IngestionSvc = Annotated[IngestionService, Depends(get_ingestion_service)]


def get_document_service(
    documents: DocumentsRepo,
    versions: VersionsRepo,
    chunks: ChunksRepo,
    metadata: MetadataRepo,
    vectors: VectorsRepo,
    audit: AuditRepo,
    publish: EventPublisherDep,
) -> DocumentService:
    """Document reads and lifecycle transitions."""
    return DocumentService(
        documents, versions, chunks, metadata, vectors, audit, publish_event=publish
    )


DocumentSvc = Annotated[DocumentService, Depends(get_document_service)]


def get_indexing_service(
    documents: DocumentsRepo,
    versions: VersionsRepo,
    chunks: ChunksRepo,
    vectors: VectorsRepo,
    jobs: JobsRepo,
    audit: AuditRepo,
    embeddings: Embeddings,
    store: Store,
    publish: EventPublisherDep,
    settings: ServiceSettings,
) -> IndexingService:
    """The embedding and indexing pipeline."""
    return IndexingService(
        documents,
        versions,
        chunks,
        vectors,
        jobs,
        audit,
        embeddings=embeddings,
        store=store,
        publish_event=publish,
        batch_size=settings.indexing_batch_size,
    )


IndexingSvc = Annotated[IndexingService, Depends(get_indexing_service)]


def get_retrieval_service(
    documents: DocumentsRepo,
    chunks: ChunksRepo,
    queries: QueriesRepo,
    results: ResultsRepo,
    rerankings: RerankingsRepo,
    feedback: FeedbackRepo,
    audit: AuditRepo,
    embeddings: Embeddings,
    store: Store,
    publish: EventPublisherDep,
    graph: Graph,
    settings: ServiceSettings,
) -> RetrievalService:
    """Hybrid search, reranking, and context assembly."""
    return RetrievalService(
        documents,
        chunks,
        queries,
        results,
        rerankings,
        feedback,
        audit,
        embeddings=embeddings,
        store=store,
        publish_event=publish,
        graph=graph,
        min_similarity=settings.min_similarity,
    )


RetrievalSvc = Annotated[RetrievalService, Depends(get_retrieval_service)]


def get_analytics_service(
    documents: DocumentsRepo,
    chunks: ChunksRepo,
    vectors: VectorsRepo,
    queries: QueriesRepo,
    results: ResultsRepo,
    feedback: FeedbackRepo,
    jobs: JobsRepo,
    sources: SourcesRepo,
    statistics: StatisticsRepo,
    reports: ReportsRepo,
    audit: AuditRepo,
    publish: EventPublisherDep,
    settings: ServiceSettings,
) -> AnalyticsService:
    """Statistics, reports, and evaluation."""
    return AnalyticsService(
        documents,
        chunks,
        vectors,
        queries,
        results,
        feedback,
        jobs,
        sources,
        statistics,
        reports,
        audit,
        publish_event=publish,
        embedding_dimensions=settings.embedding_dimensions,
    )


AnalyticsSvc = Annotated[AnalyticsService, Depends(get_analytics_service)]


def get_source_service(
    sources: SourcesRepo,
    documents: DocumentsRepo,
    audit: AuditRepo,
    publish: EventPublisherDep,
) -> SourceService:
    """Knowledge-source registration and sync bookkeeping."""
    return SourceService(sources, documents, audit, publish_event=publish)


SourceSvc = Annotated[SourceService, Depends(get_source_service)]


__all__ = [
    "ADMINISTRATOR_ROLES",
    "AnalyticsSvc",
    "AuditRepo",
    "Caller",
    "ChunksRepo",
    "CurrentUserId",
    "DbSession",
    "DocumentSvc",
    "DocumentsRepo",
    "Embeddings",
    "EventPublisherDep",
    "FeedbackRepo",
    "Graph",
    "HttpClientDep",
    "IndexingSvc",
    "IngestionSvc",
    "JobsRepo",
    "MetadataRepo",
    "QueriesRepo",
    "ReportsRepo",
    "RerankingsRepo",
    "ResultsRepo",
    "RetrievalSvc",
    "ServiceSettings",
    "SourceSvc",
    "SourcesRepo",
    "StatisticsRepo",
    "Store",
    "TokenClaims",
    "VectorsRepo",
    "VersionsRepo",
    "get_access_context",
    "get_current_user_id",
    "get_db_session",
    "get_event_publisher",
    "get_http_client",
    "get_service_settings",
    "get_token_claims",
    "get_vector_store",
]
