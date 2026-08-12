"""Test fixtures for the RAG service.

Everything runs against **real** PostgreSQL (with pgvector), Redis, and
RabbitMQ. Nothing here mocks infrastructure.

**This service needs no model-provider credential to be tested.** It
ships a builtin deterministic encoder -- see :mod:`app.embeddings.encoder`
-- so the whole ingestion, indexing, and retrieval path runs on a machine
with no API key and no network. That is the point: a RAG service whose
tests only run when somebody has an OpenAI key is a RAG service whose
tests do not run.

**The one thing the HTTP tests cannot tell you.** The ``app`` fixture
overrides only the request session, so a test's writes roll back. That
override changes *transaction lifetime*, which means any behaviour whose
correctness depends on transaction lifetime is untestable through it --
the same reasoning every prior AI-IOS service's own conftest documents.
Worker ticks, which manage their own sessions, are therefore exercised
against the real ``db_session_factory`` rather than through ``client``.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

_LOOPBACK = "127.0.0.1"
"""IPv4, never "localhost".

Docker Desktop's IPv6 loopback does not reach the published ports, so a
name that resolves to ``::1`` first makes every connection hang until it
times out rather than failing fast.
"""

os.environ.setdefault("AIIOS_DATABASE_HOST", _LOOPBACK)
os.environ.setdefault("AIIOS_DATABASE_PORT", "5433")
os.environ.setdefault("AIIOS_DATABASE_NAME", "aiios_rag")
os.environ.setdefault("AIIOS_DATABASE_USER", "aiios")
os.environ.setdefault("AIIOS_DATABASE_PASSWORD", "change-me")
os.environ.setdefault("AIIOS_REDIS_HOST", _LOOPBACK)
os.environ.setdefault("AIIOS_REDIS_PORT", "6379")
os.environ.setdefault("AIIOS_REDIS_PASSWORD", "change-me")
os.environ.setdefault("AIIOS_REDIS_DB", "35")
os.environ.setdefault("AIIOS_RABBITMQ_HOST", _LOOPBACK)
os.environ.setdefault("AIIOS_RABBITMQ_PORT", "5672")
os.environ.setdefault("AIIOS_RABBITMQ_USER", "aiios")
os.environ.setdefault("AIIOS_RABBITMQ_PASSWORD", "change-me")
os.environ.setdefault("AIIOS_RABBITMQ_VHOST", "/aiios")
os.environ.setdefault("AIIOS_NEO4J_HOST", _LOOPBACK)
os.environ.setdefault("AIIOS_NEO4J_PASSWORD", "change-me-min-8-chars")

_TEST_KEY_DIR = Path(tempfile.gettempdir()) / "aiios_rag_service_test_keys"
_TEST_KEY_DIR.mkdir(parents=True, exist_ok=True)
_TEST_PRIVATE_KEY_PATH = _TEST_KEY_DIR / "private.pem"
_TEST_PUBLIC_KEY_PATH = _TEST_KEY_DIR / "public.pem"

if not _TEST_PRIVATE_KEY_PATH.is_file():
    _private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _TEST_PRIVATE_KEY_PATH.write_text(
        _private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii"),
        encoding="ascii",
    )
    _TEST_PUBLIC_KEY_PATH.write_text(
        _private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii"),
        encoding="ascii",
    )

os.environ.setdefault("AIIOS_RAG_SERVICE_JWT_PUBLIC_KEY_PATH", str(_TEST_PUBLIC_KEY_PATH))
os.environ.setdefault("AIIOS_RAG_SERVICE_WORKERS_ENABLED", "false")
os.environ.setdefault("AIIOS_RAG_SERVICE_GRAPH_RAG_ENABLED", "false")
"""GraphRAG off by default in tests.

Neo4j holds no RAG nodes, so the graph arm would contribute nothing to
every retrieval while adding a network round trip to each -- and a test
suite that is slower for no signal is a test suite people stop running.
The graph path has its own tests that enable it explicitly.
"""

from shared_core.cache.factory import create_cache_framework  # noqa: E402
from shared_core.cache.settings import CacheSettings  # noqa: E402
from shared_core.config.settings import (  # noqa: E402
    DatabaseSettings,
    RabbitMQSettings,
    RedisSettings,
)
from shared_core.database.engine import create_engine  # noqa: E402
from shared_core.security.jwt import encode_token  # noqa: E402

from app.api import deps  # noqa: E402
from app.config.settings import RagServiceSettings  # noqa: E402
from app.core.factory import create_app  # noqa: E402
from app.embeddings.encoder import HashingEncoder  # noqa: E402
from app.embeddings.service import EmbeddingService  # noqa: E402
from app.models.enums import ClassificationLevel, EmbeddingProvider  # noqa: E402
from app.repositories.analytics import (  # noqa: E402
    IndexingJobRepository,
    KnowledgeSourceRepository,
    RagAuditRepository,
    RagReportRepository,
    RagStatisticRepository,
)
from app.repositories.document import (  # noqa: E402
    DocumentChunkRepository,
    DocumentMetadataRepository,
    DocumentRepository,
    DocumentVersionRepository,
)
from app.repositories.embedding import (  # noqa: E402
    EmbeddingModelRepository,
    EmbeddingVectorRepository,
    VectorIndexRepository,
)
from app.repositories.retrieval import (  # noqa: E402
    RerankingResultRepository,
    RetrievalFeedbackRepository,
    RetrievalQueryRepository,
    RetrievalResultRepository,
)
from app.security.access import AccessContext  # noqa: E402
from app.services.analytics import AnalyticsService  # noqa: E402
from app.services.documents import DocumentService  # noqa: E402
from app.services.indexing import IndexingService  # noqa: E402
from app.services.ingestion import IngestionService  # noqa: E402
from app.services.retrieval import RetrievalService  # noqa: E402
from app.services.sources import SourceService  # noqa: E402
from app.vector_store.pgvector_store import PgVectorStore  # noqa: E402

UNREACHABLE_ERRORS = (OSError, TimeoutError, ConnectionError, RedisError)

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_ACCEPTED = 202
HTTP_NO_CONTENT = 204
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409
HTTP_UNPROCESSABLE = 422

TEST_DIMENSIONS = 1536
"""Must match the ``vector(1536)`` column the migration created. pgvector
fixes the width at the column, so a narrower test vector is not a smaller
test -- it is an insert that fails."""

TEST_MODEL = "builtin-hash-test"


def postgres_test_settings() -> DatabaseSettings:
    return DatabaseSettings(
        database_host=_LOOPBACK,
        database_port=5433,
        database_name="aiios_rag",
        database_user="aiios",
        database_password="change-me",
        _env_file=None,
    )


def redis_test_settings() -> RedisSettings:
    """Test db 35 -- distinct from every other AI-IOS service's own."""
    return RedisSettings(
        redis_host=_LOOPBACK,
        redis_port=6379,
        redis_password="change-me",
        redis_db=35,
        _env_file=None,
    )


def rabbitmq_test_settings() -> RabbitMQSettings:
    return RabbitMQSettings(
        rabbitmq_host=_LOOPBACK,
        rabbitmq_port=5672,
        rabbitmq_user="aiios",
        rabbitmq_password="change-me",
        rabbitmq_vhost="/aiios",
        _env_file=None,
    )


@pytest_asyncio.fixture
async def pg_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_engine(postgres_test_settings())
    try:
        async with engine.connect() as conn:
            await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=5)
    except UNREACHABLE_ERRORS as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL is not reachable: {exc}")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_factory(
    pg_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A session factory on one per-test SAVEPOINT-isolated connection."""
    async with pg_engine.connect() as conn:
        trans = await conn.begin()
        yield async_sessionmaker(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        await trans.rollback()


@pytest_asyncio.fixture
async def db_session(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """One SAVEPOINT-isolated session per test, always rolled back."""
    async with db_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def cache_framework() -> AsyncIterator[Any]:
    framework = await create_cache_framework(
        CacheSettings(redis=redis_test_settings()), wait_for_ready=False
    )
    try:
        await asyncio.wait_for(framework.client.ping(), timeout=5)
    except UNREACHABLE_ERRORS as exc:
        await framework.shutdown()
        pytest.skip(f"Redis is not reachable: {exc}")
    yield framework
    await framework.shutdown()


@pytest.fixture
def organization_id() -> uuid.UUID:
    """A fresh organization id per test.

    Every test works inside its own tenant, which means every test is also,
    incidentally, a tenant-isolation test: a query that forgot its
    ``organization_id`` filter would see the other tests' rows.
    """
    return uuid.uuid4()


@pytest.fixture(scope="session")
def jwt_keypair() -> tuple[str, str]:
    """The test session's fixed RSA keypair."""
    return (
        _TEST_PRIVATE_KEY_PATH.read_text(encoding="ascii"),
        _TEST_PUBLIC_KEY_PATH.read_text(encoding="ascii"),
    )


AuthHeadersFn = Callable[..., dict[str, str]]


@pytest.fixture
def auth_headers(jwt_keypair: tuple[str, str]) -> AuthHeadersFn:
    """Build ``Authorization`` headers carrying a caller's whole access scope.

    Roles and clearance go in the token because that is the only place
    this service will read them from -- see
    :func:`app.api.deps.get_access_context`. A test that could pass them
    as parameters would be testing an API this service deliberately does
    not expose.
    """
    private_key, _public_key = jwt_keypair

    def _headers(
        user_id: uuid.UUID | None = None,
        *,
        organization_id: uuid.UUID | None = None,
        roles: list[str] | None = None,
        clearance: str = "internal",
        projects: list[uuid.UUID] | None = None,
        role: str = "super_admin",
        scopes: list[str] | None = None,
    ) -> dict[str, str]:
        claims: dict[str, Any] = {
            "sub": str(user_id or uuid.uuid4()),
            "role": role,
            "roles": roles if roles is not None else ["engineer"],
            "clearance": clearance,
            "scopes": scopes or [],
        }
        if organization_id is not None:
            claims["organization_id"] = str(organization_id)
        if projects:
            claims["projects"] = [str(project) for project in projects]
        token = encode_token(claims, private_key=private_key)
        return {"Authorization": f"Bearer {token}"}

    return _headers


@pytest.fixture
def caller(organization_id: uuid.UUID) -> AccessContext:
    """An ordinary internal-clearance caller."""
    return AccessContext.build(
        organization_id,
        user_id="tester",
        roles=["engineer"],
        clearance=ClassificationLevel.INTERNAL,
    )


@pytest.fixture
def cleared_caller(organization_id: uuid.UUID) -> AccessContext:
    """A caller cleared to ``SECRET`` and holding the ``sre`` role."""
    return AccessContext.build(
        organization_id, user_id="sre", roles=["sre"], clearance=ClassificationLevel.SECRET
    )


@pytest.fixture
def admin_caller(organization_id: uuid.UUID) -> AccessContext:
    """An administrator, cleared to ``SECRET``."""
    return AccessContext.build(
        organization_id,
        user_id="admin",
        roles=["admin"],
        clearance=ClassificationLevel.SECRET,
        is_administrator=True,
    )


class RecordingPublisher:
    """A real :data:`~app.types.EventPublisher` that records.

    Not a mock: an awaitable callable with the right signature, so the
    publish path executes for real and a test can assert exactly which
    domain events a flow announced.
    """

    def __init__(self) -> None:
        self.events: list[Any] = []

    async def __call__(self, event: Any) -> None:
        self.events.append(event)

    @property
    def names(self) -> list[str]:
        """The ``event_name`` of every event published, in order."""
        return [event.event_name for event in self.events]

    def clear(self) -> None:
        self.events.clear()


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()


@pytest.fixture
def service_settings() -> RagServiceSettings:
    """Test-tuned settings: workers off, GraphRAG off, small chunks."""
    return RagServiceSettings(
        workers_enabled=False,
        graph_rag_enabled=False,
        embedding_dimensions=TEST_DIMENSIONS,
        embedding_model=TEST_MODEL,
        default_chunk_size=200,
        default_chunk_overlap=30,
        http_client_timeout_seconds=5.0,
    )


@pytest_asyncio.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        yield client


# ---- embeddings and vector store -----------------------------------------


@pytest.fixture
def embeddings() -> EmbeddingService:
    """The builtin encoder, uncached.

    Uncached deliberately: a Redis-backed cache shared across tests would
    let one test's vectors answer another's, so a bug that returned the
    wrong vector for a given text would be invisible exactly when two
    tests happened to use the same words.
    """
    return EmbeddingService(
        provider=EmbeddingProvider.BUILTIN,
        model=TEST_MODEL,
        dimensions=TEST_DIMENSIONS,
        encoder=HashingEncoder(dimensions=TEST_DIMENSIONS),
        batch_size=4,
    )


@pytest.fixture
def vector_store(db_session: AsyncSession) -> PgVectorStore:
    return PgVectorStore(
        db_session,
        model_name=TEST_MODEL,
        dimensions=TEST_DIMENSIONS,
        embedding_provider="builtin",
    )


# ---- repositories -----------------------------------------------------------


@pytest.fixture
def documents_repo(db_session: AsyncSession) -> DocumentRepository:
    return DocumentRepository(db_session)


@pytest.fixture
def versions_repo(db_session: AsyncSession) -> DocumentVersionRepository:
    return DocumentVersionRepository(db_session)


@pytest.fixture
def chunks_repo(db_session: AsyncSession) -> DocumentChunkRepository:
    return DocumentChunkRepository(db_session)


@pytest.fixture
def metadata_repo(db_session: AsyncSession) -> DocumentMetadataRepository:
    return DocumentMetadataRepository(db_session)


@pytest.fixture
def vectors_repo(db_session: AsyncSession) -> EmbeddingVectorRepository:
    return EmbeddingVectorRepository(db_session)


@pytest.fixture
def models_repo(db_session: AsyncSession) -> EmbeddingModelRepository:
    return EmbeddingModelRepository(db_session)


@pytest.fixture
def indexes_repo(db_session: AsyncSession) -> VectorIndexRepository:
    return VectorIndexRepository(db_session)


@pytest.fixture
def jobs_repo(db_session: AsyncSession) -> IndexingJobRepository:
    return IndexingJobRepository(db_session)


@pytest.fixture
def sources_repo(db_session: AsyncSession) -> KnowledgeSourceRepository:
    return KnowledgeSourceRepository(db_session)


@pytest.fixture
def statistics_repo(db_session: AsyncSession) -> RagStatisticRepository:
    return RagStatisticRepository(db_session)


@pytest.fixture
def reports_repo(db_session: AsyncSession) -> RagReportRepository:
    return RagReportRepository(db_session)


@pytest.fixture
def audit_repo(db_session: AsyncSession) -> RagAuditRepository:
    return RagAuditRepository(db_session)


@pytest.fixture
def queries_repo(db_session: AsyncSession) -> RetrievalQueryRepository:
    return RetrievalQueryRepository(db_session)


@pytest.fixture
def results_repo(db_session: AsyncSession) -> RetrievalResultRepository:
    return RetrievalResultRepository(db_session)


@pytest.fixture
def rerankings_repo(db_session: AsyncSession) -> RerankingResultRepository:
    return RerankingResultRepository(db_session)


@pytest.fixture
def feedback_repo(db_session: AsyncSession) -> RetrievalFeedbackRepository:
    return RetrievalFeedbackRepository(db_session)


# ---- services -----------------------------------------------------------------


@pytest.fixture
def ingestion_service(
    documents_repo: DocumentRepository,
    versions_repo: DocumentVersionRepository,
    chunks_repo: DocumentChunkRepository,
    metadata_repo: DocumentMetadataRepository,
    audit_repo: RagAuditRepository,
    publisher: RecordingPublisher,
) -> IngestionService:
    return IngestionService(
        documents_repo,
        versions_repo,
        chunks_repo,
        metadata_repo,
        audit_repo,
        publish_event=publisher,
        chunk_size=200,
        chunk_overlap=30,
    )


@pytest.fixture
def document_service(
    documents_repo: DocumentRepository,
    versions_repo: DocumentVersionRepository,
    chunks_repo: DocumentChunkRepository,
    metadata_repo: DocumentMetadataRepository,
    vectors_repo: EmbeddingVectorRepository,
    audit_repo: RagAuditRepository,
    publisher: RecordingPublisher,
) -> DocumentService:
    return DocumentService(
        documents_repo,
        versions_repo,
        chunks_repo,
        metadata_repo,
        vectors_repo,
        audit_repo,
        publish_event=publisher,
    )


@pytest.fixture
def indexing_service(
    documents_repo: DocumentRepository,
    versions_repo: DocumentVersionRepository,
    chunks_repo: DocumentChunkRepository,
    vectors_repo: EmbeddingVectorRepository,
    jobs_repo: IndexingJobRepository,
    audit_repo: RagAuditRepository,
    embeddings: EmbeddingService,
    vector_store: PgVectorStore,
    publisher: RecordingPublisher,
) -> IndexingService:
    return IndexingService(
        documents_repo,
        versions_repo,
        chunks_repo,
        vectors_repo,
        jobs_repo,
        audit_repo,
        embeddings=embeddings,
        store=vector_store,
        publish_event=publisher,
        batch_size=4,
    )


@pytest.fixture
def retrieval_service(
    documents_repo: DocumentRepository,
    chunks_repo: DocumentChunkRepository,
    queries_repo: RetrievalQueryRepository,
    results_repo: RetrievalResultRepository,
    rerankings_repo: RerankingResultRepository,
    feedback_repo: RetrievalFeedbackRepository,
    audit_repo: RagAuditRepository,
    embeddings: EmbeddingService,
    vector_store: PgVectorStore,
    publisher: RecordingPublisher,
) -> RetrievalService:
    return RetrievalService(
        documents_repo,
        chunks_repo,
        queries_repo,
        results_repo,
        rerankings_repo,
        feedback_repo,
        audit_repo,
        embeddings=embeddings,
        store=vector_store,
        publish_event=publisher,
    )


@pytest.fixture
def analytics_service(
    documents_repo: DocumentRepository,
    chunks_repo: DocumentChunkRepository,
    vectors_repo: EmbeddingVectorRepository,
    queries_repo: RetrievalQueryRepository,
    results_repo: RetrievalResultRepository,
    feedback_repo: RetrievalFeedbackRepository,
    jobs_repo: IndexingJobRepository,
    sources_repo: KnowledgeSourceRepository,
    statistics_repo: RagStatisticRepository,
    reports_repo: RagReportRepository,
    audit_repo: RagAuditRepository,
    publisher: RecordingPublisher,
) -> AnalyticsService:
    return AnalyticsService(
        documents_repo,
        chunks_repo,
        vectors_repo,
        queries_repo,
        results_repo,
        feedback_repo,
        jobs_repo,
        sources_repo,
        statistics_repo,
        reports_repo,
        audit_repo,
        publish_event=publisher,
        embedding_dimensions=TEST_DIMENSIONS,
    )


@pytest.fixture
def source_service(
    sources_repo: KnowledgeSourceRepository,
    documents_repo: DocumentRepository,
    audit_repo: RagAuditRepository,
    publisher: RecordingPublisher,
) -> SourceService:
    return SourceService(sources_repo, documents_repo, audit_repo, publish_event=publisher)


# ---- the application -----------------------------------------------------------


@pytest_asyncio.fixture
async def app(db_session: AsyncSession) -> AsyncIterator[FastAPI]:
    """The real FastAPI app, started through its actual lifespan.

    PostgreSQL, Redis, RabbitMQ, and key loading all run for real. The
    request session is the only override -- see this module's docstring
    for the one thing that makes untestable.
    """
    application = create_app()
    async with application.router.lifespan_context(application):

        async def _override_db_session() -> AsyncIterator[AsyncSession]:
            yield db_session

        application.dependency_overrides[deps.get_db_session] = _override_db_session
        yield application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


HANDBOOK = (
    b"# Operations Handbook\n\n"
    b"## Backups\n\n"
    b"The nightly backup runs at 02:00 UTC and writes to the archive bucket. "
    b"Retention is thirty days for daily snapshots.\n\n"
    b"## Restore\n\n"
    b"To restore a snapshot, select it in the console and run the restore job. "
    b"Verify the checksum before promoting the restored instance to primary.\n"
)

NETWORK = (
    b"# Network Topology\n\n"
    b"The production VPC spans three availability zones. Each zone holds a private "
    b"subnet for workloads and a public subnet for load balancers.\n"
)


def utcnow() -> datetime:
    """The current moment, timezone-aware."""
    return datetime.now(UTC)


def soon(seconds: int = 3600) -> datetime:
    """A moment *seconds* in the future."""
    return datetime.now(UTC) + timedelta(seconds=seconds)


def ago(seconds: int = 3600) -> datetime:
    """A moment *seconds* in the past."""
    return datetime.now(UTC) - timedelta(seconds=seconds)


__all__ = [
    "HANDBOOK",
    "HTTP_ACCEPTED",
    "HTTP_BAD_REQUEST",
    "HTTP_CONFLICT",
    "HTTP_CREATED",
    "HTTP_FORBIDDEN",
    "HTTP_NOT_FOUND",
    "HTTP_NO_CONTENT",
    "HTTP_OK",
    "HTTP_UNAUTHORIZED",
    "HTTP_UNPROCESSABLE",
    "NETWORK",
    "TEST_DIMENSIONS",
    "TEST_MODEL",
    "ago",
    "soon",
    "utcnow",
]
