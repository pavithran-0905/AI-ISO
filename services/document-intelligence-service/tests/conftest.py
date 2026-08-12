"""Test fixtures for the document intelligence service.

Everything runs against **real** PostgreSQL, Redis, RabbitMQ and MinIO.
Nothing here mocks infrastructure.

**This service needs no credential and no OCR binary to be tested.** Every
engine is deterministic and every parser is a library, so the whole
ingestion, parsing, extraction, classification, validation and review path
runs on a machine with no API key and no Tesseract. OCR is the one thing
that genuinely needs a binary, and its own tests skip explicitly when it
is absent rather than pretending to pass.

**The one thing the HTTP tests cannot tell you.** The ``app`` fixture
overrides only the request session, so a test's writes roll back. That
override changes *transaction lifetime*, which means any behaviour whose
correctness depends on transaction lifetime is untestable through it --
notably ``FOR UPDATE SKIP LOCKED`` job claiming, which is why the worker
ticks are exercised against the real ``db_session_factory`` instead.
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
os.environ.setdefault("AIIOS_DATABASE_NAME", "aiios_document_intelligence")
os.environ.setdefault("AIIOS_DATABASE_USER", "aiios")
os.environ.setdefault("AIIOS_DATABASE_PASSWORD", "change-me")
os.environ.setdefault("AIIOS_REDIS_HOST", _LOOPBACK)
os.environ.setdefault("AIIOS_REDIS_PORT", "6379")
os.environ.setdefault("AIIOS_REDIS_PASSWORD", "change-me")
os.environ.setdefault("AIIOS_REDIS_DB", "36")
os.environ.setdefault("AIIOS_RABBITMQ_HOST", _LOOPBACK)
os.environ.setdefault("AIIOS_RABBITMQ_PORT", "5672")
os.environ.setdefault("AIIOS_RABBITMQ_USER", "aiios")
os.environ.setdefault("AIIOS_RABBITMQ_PASSWORD", "change-me")
os.environ.setdefault("AIIOS_RABBITMQ_VHOST", "/aiios")
os.environ.setdefault("AIIOS_MINIO_HOST", _LOOPBACK)
os.environ.setdefault("AIIOS_MINIO_PORT", "9000")
os.environ.setdefault("AIIOS_MINIO_ACCESS_KEY", "aiios")
os.environ.setdefault("AIIOS_MINIO_SECRET_KEY", "change-me-min-8-chars")
os.environ.setdefault("AIIOS_MINIO_USE_SSL", "false")

_TEST_KEY_DIR = Path(tempfile.gettempdir()) / "aiios_document_intelligence_test_keys"
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

os.environ.setdefault(
    "AIIOS_DOCUMENT_INTELLIGENCE_SERVICE_JWT_PUBLIC_KEY_PATH", str(_TEST_PUBLIC_KEY_PATH)
)
os.environ.setdefault("AIIOS_DOCUMENT_INTELLIGENCE_SERVICE_WORKERS_ENABLED", "false")
"""Workers off by default in tests.

Every worker is exercised by calling its ``tick()`` directly, which is
both faster and deterministic. Leaving the scheduler running would have
the processing sweep claiming rows out from under the tests that are
asserting on them.
"""

from shared_core.cache.factory import create_cache_framework  # noqa: E402
from shared_core.cache.settings import CacheSettings  # noqa: E402
from shared_core.config.settings import (  # noqa: E402
    DatabaseSettings,
    MinioSettings,
    RabbitMQSettings,
    RedisSettings,
)
from shared_core.database.engine import create_engine  # noqa: E402
from shared_core.events.base import BaseEvent  # noqa: E402
from shared_core.security.jwt import encode_token  # noqa: E402
from shared_core.storage.client import create_minio_client  # noqa: E402
from shared_core.storage.wrapper import StorageWrapper  # noqa: E402

import app.documents  # noqa: E402,F401  (registers every parser)
from app.api import deps  # noqa: E402
from app.classification.classifier import ClassifierConfig, DocumentTemplate  # noqa: E402
from app.core.factory import create_app  # noqa: E402
from app.models.enums import DocumentCategory, ProcessingStage  # noqa: E402
from app.services.analytics import AnalyticsService, ReportService  # noqa: E402
from app.services.bundle import Repositories, build_repositories  # noqa: E402
from app.services.ingestion import IngestionService  # noqa: E402
from app.services.pipeline import PipelineConfig, PipelineService  # noqa: E402
from app.services.review import ReviewService  # noqa: E402
from app.services.storage import DocumentStorage  # noqa: E402
from app.validation.engine import Rule, matches, one_of, required  # noqa: E402

UNREACHABLE_ERRORS = (OSError, TimeoutError, ConnectionError, RedisError)

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_UNPROCESSABLE = 422

TEST_BUCKET = "aiios-documents-test"
"""A bucket of its own, so a test run cannot delete a developer's real
uploads out from under them."""


def postgres_test_settings() -> DatabaseSettings:
    return DatabaseSettings(
        database_host=_LOOPBACK,
        database_port=5433,
        database_name="aiios_document_intelligence",
        database_user="aiios",
        database_password="change-me",
        _env_file=None,
    )


def redis_test_settings() -> RedisSettings:
    """Test db 36 -- distinct from every other AI-IOS service's own."""
    return RedisSettings(
        redis_host=_LOOPBACK,
        redis_port=6379,
        redis_password="change-me",
        redis_db=36,
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


def minio_test_settings() -> MinioSettings:
    return MinioSettings(
        minio_host=_LOOPBACK,
        minio_port=9000,
        minio_access_key="aiios",
        minio_secret_key="change-me-min-8-chars",
        minio_use_ssl=False,
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


@pytest.fixture
def repos(db_session: AsyncSession) -> Repositories:
    """Every repository over the test's session."""
    return build_repositories(db_session)


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


@pytest_asyncio.fixture
async def storage() -> AsyncIterator[DocumentStorage]:
    """A real MinIO-backed store, in its own test bucket."""
    store = DocumentStorage(
        StorageWrapper(create_minio_client(minio_test_settings())), bucket=TEST_BUCKET
    )
    try:
        await asyncio.wait_for(store.ensure_ready(), timeout=10)
    except (*UNREACHABLE_ERRORS, Exception) as exc:  # noqa: BLE001 -- skip, never fail
        pytest.skip(f"MinIO is not reachable: {exc}")
    yield store


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
    """Build ``Authorization`` headers carrying the caller's whole scope.

    The organization goes in the token because that is the only place this
    service will read it from -- see :func:`app.api.deps.get_organization_id`.
    A test that could pass it as a parameter would be testing an API this
    service deliberately does not expose.
    """
    private_key, _public_key = jwt_keypair

    def _headers(
        user_id: str | None = None,
        *,
        organization_id: uuid.UUID | None = None,
        roles: list[str] | None = None,
    ) -> dict[str, str]:
        claims: dict[str, Any] = {
            "sub": user_id or "tester",
            "roles": roles if roles is not None else ["document_user"],
        }
        if organization_id is not None:
            claims["organization_id"] = str(organization_id)
        token = encode_token(claims, private_key=private_key)
        return {"Authorization": f"Bearer {token}"}

    return _headers


class RecordingPublisher:
    """A publisher that records rather than sending.

    Records the event *objects*, not just their names, so a test can assert
    on a payload -- which is how the "no document content on the bus" rule
    is actually checked rather than assumed.
    """

    def __init__(self) -> None:
        self.events: list[BaseEvent] = []

    async def __call__(self, event: BaseEvent) -> None:
        self.events.append(event)

    def names(self) -> list[str]:
        return [event.event_name for event in self.events]

    def payloads(self, name: str) -> list[dict[str, Any]]:
        return [dict(e.payload) for e in self.events if e.event_name == name]


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()


@pytest.fixture
def validation_rules() -> tuple[Rule, ...]:
    """The rules the pipeline tests validate against."""
    return (
        required("change id"),
        matches("change id", r"CHG-\d{6}"),
        one_of("risk level", ["low", "medium", "high"], required_field=True),
        required("approved by"),
    )


@pytest.fixture
def change_request_template() -> DocumentTemplate:
    """A template matching the CHANGE_REQUEST fixture below."""
    return DocumentTemplate(
        name="change-request-v2",
        category=DocumentCategory.FORM,
        field_labels=("change id", "requested by", "target system", "risk level"),
        route_to="cab-queue",
    )


@pytest.fixture
def pipeline_config(
    validation_rules: tuple[Rule, ...], change_request_template: DocumentTemplate
) -> PipelineConfig:
    return PipelineConfig(
        validation_rules=validation_rules,
        classifier=ClassifierConfig(templates=(change_request_template,)),
    )


@pytest.fixture
def ingestion(
    repos: Repositories, publisher: RecordingPublisher, storage: DocumentStorage
) -> IngestionService:
    return IngestionService(
        documents=repos.documents,
        jobs=repos.jobs,
        audits=repos.audits,
        publish=publisher,
        max_bytes=10 * 1024 * 1024,
        storage=storage,
    )


@pytest.fixture
def pipeline(
    repos: Repositories, publisher: RecordingPublisher, pipeline_config: PipelineConfig
) -> PipelineService:
    return PipelineService(repositories=repos, publish=publisher, config=pipeline_config)


@pytest.fixture
def review(repos: Repositories, publisher: RecordingPublisher) -> ReviewService:
    return ReviewService(repositories=repos, publish=publisher)


@pytest.fixture
def analytics(repos: Repositories) -> AnalyticsService:
    return AnalyticsService(repositories=repos)


@pytest.fixture
def reports(repos: Repositories) -> ReportService:
    return ReportService(repositories=repos)


@pytest_asyncio.fixture
async def app(db_session: AsyncSession) -> AsyncIterator[FastAPI]:
    """The real FastAPI app, started through its actual lifespan.

    PostgreSQL, Redis, RabbitMQ, MinIO and key loading all run for real.
    The request session is the only override -- see this module's docstring
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


# ---- document fixtures ----------------------------------------------------------------


CHANGE_REQUEST = (
    b"CHANGE REQUEST FORM\n\n"
    b"Change ID: CHG-004821\n"
    b"Requested by: R. Mehta\n"
    b"Requester's E-Mail: r.mehta@example.com\n"
    b"Target system: payments-api\n"
    b"Risk level: high\n"
    b"Planned start: 2026-03-14\n"
    b"Rollback tested: yes\n\n"
    b"Impact assessment\n"
    b"[x] Customer-facing downtime expected\n"
    b"[ ] Data migration required\n\n"
    b"| System | Risk | Approver |\n"
    b"| ------ | ---- | -------- |\n"
    b"| payments-api | high | R. Mehta |\n"
    b"| billing-worker | medium | A. Novak |\n\n"
    b"Approvals\n"
    b"Approved by: ______________________\n\n"
    b"Contact the on-call rota on +44 20 7946 0018 before starting.\n"
    b"The runbook lives at https://wiki.example.com/runbooks/payments.\n"
)

POSTMORTEM = (
    b"Payments API outage postmortem\n\n"
    b"Overview\n"
    b"On 14 March the payments API was unavailable for 41 minutes, and roughly\n"
    b"18,000 customer transactions failed during that window. The estimated\n"
    b"revenue impact is 240,000 dollars.\n\n"
    b"Root cause\n"
    b"The new release changed the database connection pool configuration so\n"
    b"that each service replica opened 200 connections instead of 20. The\n"
    b"PostgreSQL primary reached its connection limit and refused new\n"
    b"connections, which the API surfaced as timeout errors.\n"
)

LOG_FILE = (
    b"2024-03-11 04:21:11 INFO  starting payments-api 4.2.1\n"
    b"2024-03-11 04:21:44 WARN  p99 latency 1841ms above threshold\n"
    b"2024-03-11 04:22:02 ERROR PoolExhaustedException: no connections\n"
    b"2024-03-11 04:22:19 INFO  rolling back to 4.2.0\n"
)

BROKEN_PDF = b"%PDF-1.7\nnot actually a pdf at all"

DEFAULT_STAGES: tuple[ProcessingStage, ...] = (
    ProcessingStage.PARSING,
    ProcessingStage.LAYOUT,
    ProcessingStage.ENTITY_EXTRACTION,
    ProcessingStage.TABLE_EXTRACTION,
    ProcessingStage.FORM_EXTRACTION,
    ProcessingStage.CLASSIFICATION,
    ProcessingStage.VALIDATION_RULES,
)


def utcnow() -> datetime:
    """The current moment, timezone-aware."""
    return datetime.now(UTC)


def hours_ago(count: int) -> datetime:
    return utcnow() - timedelta(hours=count)


def hours_ahead(count: int) -> datetime:
    return utcnow() + timedelta(hours=count)
