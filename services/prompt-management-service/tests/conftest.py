"""Test fixtures for the prompt management service.

Everything runs against **real** PostgreSQL, Redis, and RabbitMQ.
Nothing here mocks infrastructure.

**This service calls no model provider**, so unlike ai-assistant-service
or ai-agent-platform-service there is no "the LLM may be unreachable"
caveat: every operation here is deterministic and every test can assert
exact outcomes.

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
os.environ.setdefault("AIIOS_DATABASE_NAME", "aiios_prompt_management")
os.environ.setdefault("AIIOS_DATABASE_USER", "aiios")
os.environ.setdefault("AIIOS_DATABASE_PASSWORD", "change-me")
os.environ.setdefault("AIIOS_REDIS_HOST", _LOOPBACK)
os.environ.setdefault("AIIOS_REDIS_PORT", "6379")
os.environ.setdefault("AIIOS_REDIS_PASSWORD", "change-me")
os.environ.setdefault("AIIOS_REDIS_DB", "34")
os.environ.setdefault("AIIOS_RABBITMQ_HOST", _LOOPBACK)
os.environ.setdefault("AIIOS_RABBITMQ_PORT", "5672")
os.environ.setdefault("AIIOS_RABBITMQ_USER", "aiios")
os.environ.setdefault("AIIOS_RABBITMQ_PASSWORD", "change-me")
os.environ.setdefault("AIIOS_RABBITMQ_VHOST", "/aiios")

_TEST_KEY_DIR = Path(tempfile.gettempdir()) / "aiios_prompt_management_service_test_keys"
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
    "AIIOS_PROMPT_MANAGEMENT_SERVICE_JWT_PUBLIC_KEY_PATH", str(_TEST_PUBLIC_KEY_PATH)
)
os.environ.setdefault("AIIOS_PROMPT_MANAGEMENT_SERVICE_WORKERS_ENABLED", "false")

from shared_core.cache.factory import create_cache_framework  # noqa: E402
from shared_core.cache.manager import CacheManager  # noqa: E402
from shared_core.cache.settings import CacheSettings  # noqa: E402
from shared_core.config.settings import (  # noqa: E402
    DatabaseSettings,
    RabbitMQSettings,
    RedisSettings,
)
from shared_core.database.engine import create_engine  # noqa: E402
from shared_core.security.jwt import encode_token  # noqa: E402

from app.api import deps  # noqa: E402
from app.config.settings import PromptManagementServiceSettings  # noqa: E402
from app.core.factory import create_app  # noqa: E402
from app.models.enums import PromptType  # noqa: E402
from app.repositories.analytics import (  # noqa: E402
    PromptAuditRepository,
    PromptOptimizationRepository,
    PromptReportRepository,
    PromptStatisticRepository,
)
from app.repositories.governance import (  # noqa: E402
    PromptApprovalRepository,
    PromptReviewRepository,
    PromptSecurityScanRepository,
)
from app.repositories.prompt import PromptRepository, PromptVersionRepository  # noqa: E402
from app.repositories.template import (  # noqa: E402
    PromptCategoryRepository,
    PromptTagRepository,
    PromptTemplateRepository,
    PromptVariableRepository,
)
from app.repositories.testing import (  # noqa: E402
    PromptAbTestRepository,
    PromptExecutionRepository,
    PromptTestRepository,
    PromptTestResultRepository,
)
from app.services.analytics import (  # noqa: E402
    AuditService,
    EvaluationService,
    ExecutionRecordingService,
    OptimizationService,
    ReportService,
    StatisticsService,
)
from app.services.governance import (  # noqa: E402
    ApprovalService,
    PublicationGate,
    ReviewService,
    SecurityService,
)
from app.services.prompt import PromptService  # noqa: E402
from app.services.rendering import RenderingService  # noqa: E402
from app.services.testing import AbTestingService, PromptTestingService  # noqa: E402

UNREACHABLE_ERRORS = (OSError, TimeoutError, ConnectionError, RedisError)

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_NO_CONTENT = 204
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409
HTTP_UNPROCESSABLE = 422


def postgres_test_settings() -> DatabaseSettings:
    return DatabaseSettings(
        database_host=_LOOPBACK,
        database_port=5433,
        database_name="aiios_prompt_management",
        database_user="aiios",
        database_password="change-me",
        _env_file=None,
    )


def redis_test_settings() -> RedisSettings:
    """Test db 34 -- distinct from every other AI-IOS service's own."""
    return RedisSettings(
        redis_host=_LOOPBACK,
        redis_port=6379,
        redis_password="change-me",
        redis_db=34,
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
def cache_manager(cache_framework: Any) -> CacheManager:
    return cache_framework.manager  # type: ignore[no-any-return]


@pytest.fixture
def organization_id() -> uuid.UUID:
    """A fresh organization id per test.

    Every test works inside its own tenant, which means every test is
    also, incidentally, a tenant-isolation test: a query that forgot its
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
    """Build ``Authorization`` headers for a given user, role, and organization."""
    private_key, _public_key = jwt_keypair

    def _headers(
        user_id: uuid.UUID,
        *,
        organization_id: uuid.UUID | None = None,
        role: str = "super_admin",
        scopes: list[str] | None = None,
    ) -> dict[str, str]:
        claims: dict[str, Any] = {"sub": str(user_id), "role": role, "scopes": scopes or []}
        if organization_id is not None:
            claims["organization_id"] = str(organization_id)
        token = encode_token(claims, private_key=private_key)
        return {"Authorization": f"Bearer {token}"}

    return _headers


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


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()


@pytest.fixture
def service_settings() -> PromptManagementServiceSettings:
    """Test-tuned settings: workers disabled, short expiries."""
    return PromptManagementServiceSettings(
        workers_enabled=False,
        http_client_timeout_seconds=5.0,
        approval_expiry_seconds=3_600.0,
        required_approvals=1,
    )


@pytest_asyncio.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        yield client


# ---- repositories -----------------------------------------------------------


@pytest.fixture
def prompts_repo(db_session: AsyncSession) -> PromptRepository:
    return PromptRepository(db_session)


@pytest.fixture
def versions_repo(db_session: AsyncSession) -> PromptVersionRepository:
    return PromptVersionRepository(db_session)


@pytest.fixture
def templates_repo(db_session: AsyncSession) -> PromptTemplateRepository:
    return PromptTemplateRepository(db_session)


@pytest.fixture
def variables_repo(db_session: AsyncSession) -> PromptVariableRepository:
    return PromptVariableRepository(db_session)


@pytest.fixture
def categories_repo(db_session: AsyncSession) -> PromptCategoryRepository:
    return PromptCategoryRepository(db_session)


@pytest.fixture
def tags_repo(db_session: AsyncSession) -> PromptTagRepository:
    return PromptTagRepository(db_session)


@pytest.fixture
def reviews_repo(db_session: AsyncSession) -> PromptReviewRepository:
    return PromptReviewRepository(db_session)


@pytest.fixture
def approvals_repo(db_session: AsyncSession) -> PromptApprovalRepository:
    return PromptApprovalRepository(db_session)


@pytest.fixture
def scans_repo(db_session: AsyncSession) -> PromptSecurityScanRepository:
    return PromptSecurityScanRepository(db_session)


@pytest.fixture
def tests_repo(db_session: AsyncSession) -> PromptTestRepository:
    return PromptTestRepository(db_session)


@pytest.fixture
def test_results_repo(db_session: AsyncSession) -> PromptTestResultRepository:
    return PromptTestResultRepository(db_session)


@pytest.fixture
def ab_tests_repo(db_session: AsyncSession) -> PromptAbTestRepository:
    return PromptAbTestRepository(db_session)


@pytest.fixture
def executions_repo(db_session: AsyncSession) -> PromptExecutionRepository:
    return PromptExecutionRepository(db_session)


@pytest.fixture
def optimizations_repo(db_session: AsyncSession) -> PromptOptimizationRepository:
    return PromptOptimizationRepository(db_session)


@pytest.fixture
def statistics_repo(db_session: AsyncSession) -> PromptStatisticRepository:
    return PromptStatisticRepository(db_session)


@pytest.fixture
def reports_repo(db_session: AsyncSession) -> PromptReportRepository:
    return PromptReportRepository(db_session)


@pytest.fixture
def audit_repo(db_session: AsyncSession) -> PromptAuditRepository:
    return PromptAuditRepository(db_session)


# ---- services -----------------------------------------------------------


@pytest.fixture
def prompt_service(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    audit_repo: PromptAuditRepository,
    variables_repo: PromptVariableRepository,
    publisher: RecordingPublisher,
) -> PromptService:
    return PromptService(
        prompts_repo,
        versions_repo,
        audit_repo,
        publish_event=publisher,
        variables=variables_repo,
    )


@pytest.fixture
def rendering_service(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    templates_repo: PromptTemplateRepository,
    variables_repo: PromptVariableRepository,
) -> RenderingService:
    return RenderingService(prompts_repo, versions_repo, templates_repo, variables_repo)


@pytest.fixture
def review_service(reviews_repo: PromptReviewRepository) -> ReviewService:
    return ReviewService(reviews_repo)


@pytest.fixture
def approval_service(
    approvals_repo: PromptApprovalRepository,
    audit_repo: PromptAuditRepository,
    publisher: RecordingPublisher,
) -> ApprovalService:
    return ApprovalService(approvals_repo, audit_repo, publish_event=publisher)


@pytest.fixture
def security_service(
    scans_repo: PromptSecurityScanRepository,
    variables_repo: PromptVariableRepository,
    publisher: RecordingPublisher,
) -> SecurityService:
    return SecurityService(scans_repo, variables_repo, publish_event=publisher)


@pytest.fixture
def publication_gate(
    reviews_repo: PromptReviewRepository,
    approvals_repo: PromptApprovalRepository,
    scans_repo: PromptSecurityScanRepository,
) -> PublicationGate:
    return PublicationGate(reviews_repo, approvals_repo, scans_repo)


@pytest.fixture
def testing_service(
    tests_repo: PromptTestRepository,
    test_results_repo: PromptTestResultRepository,
    rendering_service: RenderingService,
) -> PromptTestingService:
    return PromptTestingService(tests_repo, test_results_repo, rendering_service)


@pytest.fixture
def ab_service(
    ab_tests_repo: PromptAbTestRepository,
    executions_repo: PromptExecutionRepository,
    audit_repo: PromptAuditRepository,
    publisher: RecordingPublisher,
) -> AbTestingService:
    return AbTestingService(ab_tests_repo, executions_repo, audit_repo, publish_event=publisher)


@pytest.fixture
def optimization_service(
    optimizations_repo: PromptOptimizationRepository,
    prompt_service: PromptService,
    publisher: RecordingPublisher,
) -> OptimizationService:
    return OptimizationService(optimizations_repo, prompt_service, publish_event=publisher)


@pytest.fixture
def execution_service(
    executions_repo: PromptExecutionRepository,
    prompts_repo: PromptRepository,
    publisher: RecordingPublisher,
) -> ExecutionRecordingService:
    return ExecutionRecordingService(executions_repo, prompts_repo, publish_event=publisher)


@pytest.fixture
def evaluation_service(
    versions_repo: PromptVersionRepository, publisher: RecordingPublisher
) -> EvaluationService:
    return EvaluationService(versions_repo, publish_event=publisher)


@pytest.fixture
def statistics_service(
    statistics_repo: PromptStatisticRepository,
    prompts_repo: PromptRepository,
    executions_repo: PromptExecutionRepository,
    optimizations_repo: PromptOptimizationRepository,
    scans_repo: PromptSecurityScanRepository,
) -> StatisticsService:
    return StatisticsService(
        statistics_repo, prompts_repo, executions_repo, optimizations_repo, scans_repo
    )


@pytest.fixture
def report_service(
    reports_repo: PromptReportRepository,
    prompts_repo: PromptRepository,
    optimizations_repo: PromptOptimizationRepository,
    scans_repo: PromptSecurityScanRepository,
    audit_repo: PromptAuditRepository,
) -> ReportService:
    return ReportService(reports_repo, prompts_repo, optimizations_repo, scans_repo, audit_repo)


@pytest.fixture
def audit_service(audit_repo: PromptAuditRepository) -> AuditService:
    return AuditService(audit_repo)


# ---- composite fixtures --------------------------------------------------


MakePromptFn = Callable[..., Any]


@pytest.fixture
def make_prompt(prompt_service: PromptService, organization_id: uuid.UUID) -> MakePromptFn:
    """Create one prompt and its own first draft revision."""

    async def _make(slug: str = "test-prompt", **kwargs: Any) -> Any:
        defaults: dict[str, Any] = {
            "name": "Test Prompt",
            "prompt_type": PromptType.SYSTEM,
            "body": "Hello {{ name }}",
        }
        defaults.update(kwargs)
        return await prompt_service.create(organization_id=organization_id, slug=slug, **defaults)

    return _make


MakePublishedFn = Callable[..., Any]


@pytest.fixture
def make_published(prompt_service: PromptService, make_prompt: MakePromptFn) -> MakePublishedFn:
    """Create a prompt and publish its first revision."""

    async def _make(slug: str = "published-prompt", **kwargs: Any) -> Any:
        prompt, version = await make_prompt(slug, **kwargs)
        published = await prompt_service.publish(prompt, version)
        return published, version

    return _make


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
    "HTTP_BAD_REQUEST",
    "HTTP_CONFLICT",
    "HTTP_CREATED",
    "HTTP_FORBIDDEN",
    "HTTP_NOT_FOUND",
    "HTTP_NO_CONTENT",
    "HTTP_OK",
    "HTTP_UNAUTHORIZED",
    "HTTP_UNPROCESSABLE",
    "ago",
    "soon",
    "utcnow",
]
