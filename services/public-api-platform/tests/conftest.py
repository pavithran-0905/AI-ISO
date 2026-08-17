"""Test fixtures for the Public API & Developer Platform.

Everything runs against **real** PostgreSQL and Redis. Nothing here mocks
infrastructure. RabbitMQ/MinIO are not needed by any test: this service's
event publisher and notifier are both injected as plain callables/objects
(see ``publisher`` below), never resolved from a live broker in tests.

**Uses the service's own dedicated database** (``aiios_public_api_platform``),
matching the project-wide convention of one Postgres database per service
rather than the shared bootstrap database referenced in the root ``.env``.
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
"""IPv4, never "localhost" -- Docker Desktop's IPv6 loopback does not reach
the published ports, so a name that resolves to ``::1`` first makes every
connection hang until it times out rather than failing fast."""

os.environ.setdefault("AIIOS_DATABASE_HOST", _LOOPBACK)
os.environ.setdefault("AIIOS_DATABASE_PORT", "5433")
os.environ.setdefault("AIIOS_DATABASE_NAME", "aiios_public_api_platform")
os.environ.setdefault("AIIOS_DATABASE_USER", "aiios")
os.environ.setdefault("AIIOS_DATABASE_PASSWORD", "change-me")
os.environ.setdefault("AIIOS_REDIS_HOST", _LOOPBACK)
os.environ.setdefault("AIIOS_REDIS_PORT", "6379")
os.environ.setdefault("AIIOS_REDIS_PASSWORD", "change-me")
os.environ.setdefault("AIIOS_REDIS_DB", "46")
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
os.environ.setdefault("AIIOS_TELEMETRY_ENABLED", "false")

_TEST_KEY_DIR = Path(tempfile.gettempdir()) / "aiios_public_api_platform_test_keys"
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

os.environ.setdefault("AIIOS_PUBLIC_API_PLATFORM_JWT_PUBLIC_KEY_PATH", str(_TEST_PUBLIC_KEY_PATH))
os.environ.setdefault("AIIOS_PUBLIC_API_PLATFORM_WORKERS_ENABLED", "false")
"""Workers off by default in tests. Every worker is exercised by calling
its ``run_job``/``tick`` directly, which is both faster and deterministic."""

from shared_core.cache.factory import create_cache_framework  # noqa: E402
from shared_core.cache.settings import CacheSettings  # noqa: E402
from shared_core.config.settings import DatabaseSettings, RedisSettings  # noqa: E402
from shared_core.database.engine import create_engine  # noqa: E402
from shared_core.events.base import BaseEvent  # noqa: E402
from shared_core.security.jwt import encode_token  # noqa: E402

import app.models  # noqa: E402  (registers every table with Base.metadata)
from app.api import deps  # noqa: E402
from app.core.factory import create_app  # noqa: E402
from app.services.bundle import Repositories, build_repositories  # noqa: E402

UNREACHABLE_ERRORS = (OSError, TimeoutError, ConnectionError, RedisError)

HTTP_OK = 200
HTTP_CREATED = 201
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
        database_name="aiios_public_api_platform",
        database_user="aiios",
        database_password="change-me",
        _env_file=None,
    )


def redis_test_settings() -> RedisSettings:
    """Test db 46 -- this service's own, distinct from every other."""
    return RedisSettings(
        redis_host=_LOOPBACK,
        redis_port=6379,
        redis_password="change-me",
        redis_db=46,
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
    """Every repository over the test's session, unscoped (tenant_scope=None)."""
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


@pytest.fixture
def organization_id() -> uuid.UUID:
    """A fresh organization id per test.

    Every test works inside its own tenant, which means every test is also,
    incidentally, a tenant-isolation test.
    """
    return uuid.uuid4()


@pytest.fixture(scope="session")
def jwt_keypair() -> tuple[str, str]:
    return (
        _TEST_PRIVATE_KEY_PATH.read_text(encoding="ascii"),
        _TEST_PUBLIC_KEY_PATH.read_text(encoding="ascii"),
    )


AuthHeadersFn = Callable[..., dict[str, str]]


@pytest.fixture
def auth_headers(jwt_keypair: tuple[str, str]) -> AuthHeadersFn:
    private_key, _public_key = jwt_keypair

    def _headers(
        email: str | None = None,
        *,
        organization_id: uuid.UUID | None = None,
        roles: list[str] | None = None,
    ) -> dict[str, str]:
        claims: dict[str, Any] = {
            "sub": email or "tester@example.com",
            "roles": roles if roles is not None else ["admin"],
        }
        if organization_id is not None:
            claims["organization_id"] = str(organization_id)
        token = encode_token(claims, private_key=private_key)
        return {"Authorization": f"Bearer {token}"}

    return _headers


class RecordingPublisher:
    """A publisher that records rather than sending."""

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


class RecordingNotifier:
    """A notifier stand-in recording calls instead of sending real notifications."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __getattr__(self, name: str) -> Callable[..., Any]:
        async def _record(*args: Any, **kwargs: Any) -> None:
            self.calls.append((name, kwargs))

        return _record


@pytest.fixture
def notifier() -> RecordingNotifier:
    return RecordingNotifier()


@pytest_asyncio.fixture
async def app(db_session: AsyncSession) -> AsyncIterator[FastAPI]:
    """The real FastAPI app, started through its actual lifespan.

    PostgreSQL, Redis, RabbitMQ and key loading all run for real (workers
    are disabled via env so no scheduler races test data). The request
    session is the only override.
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
    return datetime.now(UTC)


def hours_ago(count: float) -> datetime:
    return utcnow() - timedelta(hours=count)


def hours_ahead(count: float) -> datetime:
    return utcnow() + timedelta(hours=count)


def days_ago(count: float) -> datetime:
    return utcnow() - timedelta(days=count)


def days_ahead(count: float) -> datetime:
    return utcnow() + timedelta(days=count)
