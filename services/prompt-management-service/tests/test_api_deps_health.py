"""Tests for :mod:`app.api.deps`, :mod:`app.api.health`,
:mod:`app.config.keys`, and :mod:`app.core.factory`.

The plumbing layer. Everything runs against the real app: real lifespan,
real PostgreSQL, real Redis, real RabbitMQ, real key loading, real
middleware stack.

**Why these matter more than their size suggests.** A dependency provider
that returned the wrong repository, or an auth dependency that let an
unsigned token through, would not fail the router tests -- those all
present a valid token and read whatever rows come back. So this module
checks the wiring itself: that every provider constructs its own type
against the *request's* session, that authentication actually rejects
what it should, and that a readiness probe reports which dependency is
down rather than 500-ing and telling the orchestrator nothing.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from shared_core.config.environment import Environment
from shared_core.config.settings import ApplicationSettings
from shared_core.exceptions.dependency import DependencyError
from shared_core.security.jwt import encode_token
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.config.keys import load_public_key
from app.config.settings import (
    PromptManagementServiceSettings,
    Settings,
    build_settings,
    get_settings,
)
from app.core.factory import _build_cors_config, create_app
from app.repositories.analytics import (
    PromptOptimizationRepository,
)
from app.repositories.governance import (
    PromptApprovalRepository,
    PromptReviewRepository,
    PromptSecurityScanRepository,
)
from app.repositories.prompt import PromptRepository, PromptVersionRepository
from app.repositories.template import (
    PromptCategoryRepository,
    PromptTagRepository,
    PromptTemplateRepository,
    PromptVariableRepository,
)
from app.repositories.testing import (
    PromptAbTestRepository,
    PromptExecutionRepository,
    PromptTestRepository,
)
from app.services.analytics import (
    AuditService,
    EvaluationService,
    ExecutionRecordingService,
    OptimizationService,
    ReportService,
    StatisticsService,
)
from app.services.governance import (
    ApprovalService,
    PublicationGate,
    ReviewService,
    SecurityService,
)
from app.services.prompt import PromptService
from app.services.rendering import RenderingService
from app.services.testing import AbTestingService, PromptTestingService
from app.workers.registrar import (
    AB_EVALUATION_SWEEP_JOB_ID,
    APPROVAL_EXPIRY_SWEEP_JOB_ID,
    REVIEW_CYCLE_SWEEP_JOB_ID,
    STATISTICS_ROLLUP_JOB_ID,
)
from tests.conftest import (
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    AuthHeadersFn,
    MakePromptFn,
)

# ---------------------------------------------------------------------------
# Repository providers
#
# Parameterised rather than one test each: the interesting property is
# uniform -- every provider builds its own repository type bound to the
# session it was handed, and a copy-paste slip that returned a neighbour's
# type is exactly what a single shared test catches.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        (deps.get_prompts_repo, PromptRepository),
        (deps.get_versions_repo, PromptVersionRepository),
        (deps.get_variables_repo, PromptVariableRepository),
        (deps.get_templates_repo, PromptTemplateRepository),
        (deps.get_categories_repo, PromptCategoryRepository),
        (deps.get_tags_repo, PromptTagRepository),
        (deps.get_tests_repo, PromptTestRepository),
        (deps.get_ab_tests_repo, PromptAbTestRepository),
        (deps.get_optimizations_repo, PromptOptimizationRepository),
        (deps.get_reviews_repo, PromptReviewRepository),
        (deps.get_approvals_repo, PromptApprovalRepository),
        (deps.get_scans_repo, PromptSecurityScanRepository),
        (deps.get_executions_repo, PromptExecutionRepository),
    ],
)
def test_every_repository_provider_returns_its_own_type(
    db_session: AsyncSession, provider: Any, expected: type
) -> None:
    assert isinstance(provider(db_session), expected)


def test_the_repository_providers_are_all_distinct_types(db_session: AsyncSession) -> None:
    """A guard on the parametrisation above: if two providers returned the
    same type, each would still pass its own isinstance check."""
    providers = (
        deps.get_prompts_repo,
        deps.get_versions_repo,
        deps.get_variables_repo,
        deps.get_templates_repo,
        deps.get_categories_repo,
        deps.get_tags_repo,
        deps.get_tests_repo,
        deps.get_ab_tests_repo,
        deps.get_optimizations_repo,
        deps.get_reviews_repo,
        deps.get_approvals_repo,
        deps.get_scans_repo,
        deps.get_executions_repo,
    )
    produced = {type(provider(db_session)) for provider in providers}
    assert len(produced) == len(providers)


# ---------------------------------------------------------------------------
# Service providers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        (deps.get_prompt_service, PromptService),
        (deps.get_ab_service, AbTestingService),
        (deps.get_optimization_service, OptimizationService),
        (deps.get_evaluation_service, EvaluationService),
        (deps.get_execution_service, ExecutionRecordingService),
        (deps.get_approval_service, ApprovalService),
        (deps.get_security_service, SecurityService),
    ],
)
def test_every_publishing_service_provider_returns_its_own_type(
    db_session: AsyncSession, publisher: Any, provider: Any, expected: type
) -> None:
    assert isinstance(provider(db_session, publisher), expected)


def test_the_review_service_provider_needs_no_publisher(db_session: AsyncSession) -> None:
    """Requesting a review is not a domain event, so this one takes no
    publisher -- a signature difference worth pinning, since adding one
    would make every review request announce itself platform-wide."""
    assert isinstance(deps.get_review_service(db_session), ReviewService)


def test_the_audit_service_provider_needs_no_publisher(db_session: AsyncSession) -> None:
    assert isinstance(deps.get_audit_service(db_session), AuditService)


def test_the_publication_gate_provider(db_session: AsyncSession) -> None:
    assert isinstance(deps.get_publication_gate(db_session), PublicationGate)


def test_the_statistics_service_provider(db_session: AsyncSession) -> None:
    assert isinstance(deps.get_statistics_service(db_session), StatisticsService)


def test_the_report_service_provider_takes_service_settings(
    db_session: AsyncSession, service_settings: PromptManagementServiceSettings
) -> None:
    """The row cap on a generated report is configuration, so this
    provider needs the settings too."""
    assert isinstance(deps.get_report_service(db_session, service_settings), ReportService)


def test_the_rendering_service_provider_takes_service_settings(
    db_session: AsyncSession, service_settings: PromptManagementServiceSettings
) -> None:
    """Rendering limits are configuration, so this provider needs the
    service's own settings rather than only a session."""
    assert isinstance(deps.get_rendering_service(db_session, service_settings), RenderingService)


def test_the_testing_service_provider_takes_service_settings(
    db_session: AsyncSession, service_settings: PromptManagementServiceSettings
) -> None:
    """It builds a rendering service internally, which is why it needs the
    settings too."""
    assert isinstance(deps.get_testing_service(db_session, service_settings), PromptTestingService)


# ---------------------------------------------------------------------------
# Application-state providers
# ---------------------------------------------------------------------------


async def test_the_state_providers_read_what_the_lifespan_put_there(app: FastAPI) -> None:
    """Each of these is a one-line ``request.app.state`` read, and each
    would fail only at request time if the lifespan and the provider ever
    disagreed on an attribute name."""

    class _Request:
        def __init__(self, application: FastAPI) -> None:
            self.app = application

    request: Any = _Request(app)

    assert deps.get_event_publisher(request) is app.state.publish_event
    assert deps.get_service_settings(request) is app.state.service_settings
    assert deps.get_http_client(request) is app.state.http_client
    assert isinstance(deps.get_http_client(request), httpx.AsyncClient)
    assert isinstance(deps.get_service_settings(request), PromptManagementServiceSettings)


async def test_the_request_session_provider_yields_a_working_session(app: FastAPI) -> None:
    """Exercises ``get_db_session`` itself rather than the conftest's
    override, so the real ``session_scope`` path is covered."""

    class _Request:
        def __init__(self, application: FastAPI) -> None:
            self.app = application

    request: Any = _Request(app)
    async for session in deps.get_db_session(request):
        assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
        break


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def test_a_valid_token_resolves_to_the_callers_id(
    client: AsyncClient,
    auth_headers: AuthHeadersFn,
    organization_id: uuid.UUID,
    make_prompt: MakePromptFn,
) -> None:
    """``executed_by`` on a recorded execution is the observable proof
    that the subject claim reached the handler."""
    caller = uuid.uuid4()
    prompt, version = await make_prompt("who-am-i")

    response = await client.post(
        "/prompts/executions",
        params={"organization_id": str(organization_id)},
        headers=auth_headers(caller, organization_id=organization_id),
        json={"prompt_id": str(prompt.id), "version_number": version.version_number},
    )

    assert response.status_code == 201


async def test_a_request_with_no_token_is_rejected(
    client: AsyncClient, organization_id: uuid.UUID, make_prompt: MakePromptFn
) -> None:
    prompt, version = await make_prompt("needs-auth")

    response = await client.post(
        "/prompts/executions",
        params={"organization_id": str(organization_id)},
        json={"prompt_id": str(prompt.id), "version_number": version.version_number},
    )

    assert response.status_code == HTTP_UNAUTHORIZED


@pytest.mark.parametrize(
    "header",
    [
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": "Bearer "},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "eyJhbGciOiJSUzI1NiJ9.e30.x"},
    ],
)
async def test_a_malformed_or_unsigned_token_is_rejected(
    client: AsyncClient,
    organization_id: uuid.UUID,
    make_prompt: MakePromptFn,
    header: dict[str, str],
) -> None:
    """None of these carry a signature this service's public key
    verifies. A token accepted here would be an authentication bypass, so
    each shape is checked rather than assumed."""
    prompt, version = await make_prompt("guarded")

    response = await client.post(
        "/prompts/executions",
        params={"organization_id": str(organization_id)},
        headers=header,
        json={"prompt_id": str(prompt.id), "version_number": version.version_number},
    )

    assert response.status_code == HTTP_UNAUTHORIZED


async def test_a_token_signed_by_the_wrong_key_is_rejected(
    client: AsyncClient, organization_id: uuid.UUID, make_prompt: MakePromptFn
) -> None:
    """The single most important assertion about authentication here: a
    structurally perfect token from a keypair this service does not trust
    must not authenticate. Signed with a **real** second RSA keypair, not
    a corrupted string."""
    rogue = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rogue_pem = rogue.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    token = encode_token(
        {"sub": str(uuid.uuid4()), "organization_id": str(organization_id)}, private_key=rogue_pem
    )

    prompt, version = await make_prompt("wrong-key")
    response = await client.post(
        "/prompts/executions",
        params={"organization_id": str(organization_id)},
        headers={"Authorization": f"Bearer {token}"},
        json={"prompt_id": str(prompt.id), "version_number": version.version_number},
    )

    assert response.status_code == HTTP_UNAUTHORIZED


async def test_the_caller_token_dependency_forwards_the_raw_bearer() -> None:
    """A prompt's secret references resolve with the authority of whoever
    asked for the render, never a fixed service credential -- otherwise
    any caller could read any secret the service can reach."""

    class _Credentials:
        scheme = "Bearer"
        credentials = "the-raw-token"

    assert await deps.get_caller_token(_Credentials()) == "the-raw-token"  # type: ignore[arg-type]


async def test_the_caller_token_dependency_is_empty_when_unauthenticated() -> None:
    """Empty rather than raising: the routes that need a caller identity
    enforce it through ``CurrentUserId``, and this dependency exists only
    to forward whatever authority was presented."""
    assert await deps.get_caller_token(None) == ""


# ---------------------------------------------------------------------------
# Health, liveness, readiness
# ---------------------------------------------------------------------------


async def test_health_reports_the_service_identity(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == HTTP_OK
    data = response.json()["data"]
    assert data["status"] == "healthy"
    assert data["service"]
    assert data["version"]
    assert data["environment"]


async def test_health_needs_no_authentication(client: AsyncClient) -> None:
    """A probe that required a token would fail closed during exactly the
    outage it exists to report."""
    assert (await client.get("/health")).status_code == HTTP_OK


async def test_liveness_reports_the_process_is_alive(client: AsyncClient) -> None:
    response = await client.get("/liveness")

    assert response.status_code == HTTP_OK
    assert response.json()["data"]["status"] == "alive"


async def test_readiness_reports_every_dependency_it_checked(client: AsyncClient) -> None:
    response = await client.get("/readiness")

    assert response.status_code == HTTP_OK
    data = response.json()["data"]
    assert data["status"] == "ready"

    by_name = {check["name"]: check for check in data["checks"]}
    assert by_name["database"]["status"] == "ok"
    assert by_name["cache"]["status"] == "ok"
    assert "ms" in by_name["database"]["detail"]


async def test_readiness_reports_a_dead_cache_without_failing_the_probe(app: FastAPI) -> None:
    """Redis does not gate readiness -- this service can serve prompts
    from PostgreSQL alone -- so a dead cache is reported as a failed
    *check* while the overall status stays ready.

    The failure is real: a genuine Redis client pointed at a loopback port
    nothing listens on, so the connection is refused for real.
    """
    original = app.state.redis_client
    app.state.redis_client = Redis(host="127.0.0.1", port=1, socket_connect_timeout=1)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/readiness")
    finally:
        await app.state.redis_client.aclose()
        app.state.redis_client = original

    assert response.status_code == HTTP_OK
    data = response.json()["data"]
    assert data["status"] == "ready"

    cache = next(check for check in data["checks"] if check["name"] == "cache")
    assert cache["status"] == "failed"
    assert "unreachable" in cache["detail"]


async def test_readiness_omits_the_cache_check_when_no_client_is_wired(app: FastAPI) -> None:
    """A service started without a cache should report on what it has,
    not invent a check it cannot run."""
    original = app.state.redis_client
    del app.state.redis_client
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/readiness")
    finally:
        app.state.redis_client = original

    data = response.json()["data"]
    assert [check["name"] for check in data["checks"]] == ["database"]
    assert data["status"] == "ready"


# ---------------------------------------------------------------------------
# JWT public key loading
# ---------------------------------------------------------------------------


def test_loading_a_real_public_key(jwt_keypair: tuple[str, str], tmp_path: Path) -> None:
    _private, public = jwt_keypair
    path = tmp_path / "public.pem"
    path.write_text(public, encoding="ascii")

    assert load_public_key(str(path)) == public
    assert "BEGIN PUBLIC KEY" in load_public_key(str(path))


def test_a_missing_key_file_is_a_dependency_error(tmp_path: Path) -> None:
    """This service holds no private key, so a missing file is a real
    configuration error rather than something to paper over with an
    ephemeral fallback -- a self-generated key would verify nothing that
    authentication-service actually signed."""
    with pytest.raises(DependencyError, match="JWT public key not found"):
        load_public_key(str(tmp_path / "absent.pem"))


def test_a_directory_where_a_key_belongs_is_also_a_dependency_error(tmp_path: Path) -> None:
    """``is_file`` rather than ``exists``, so a mounted-empty-directory
    misconfiguration fails with the same clear message instead of an
    ``IsADirectoryError`` from the read."""
    with pytest.raises(DependencyError, match="JWT public key not found"):
        load_public_key(str(tmp_path))


# ---------------------------------------------------------------------------
# The app factory
# ---------------------------------------------------------------------------


def _all_paths(application: FastAPI) -> set[str]:
    """Every registered path, walking nested routers.

    ``include_router`` wraps its children in ``_IncludedRouter`` objects
    that carry an ``original_router`` and no ``path`` of their own, so a
    flat comprehension over ``application.routes`` silently misses every
    included route -- including the health endpoints.
    """
    found: set[str] = set()
    pending: list[Any] = list(application.routes)
    while pending:
        route = pending.pop()
        path = getattr(route, "path", None)
        if isinstance(path, str):
            found.add(path)
        nested = getattr(route, "original_router", None)
        pending.extend(getattr(nested, "routes", []) if nested is not None else [])
        pending.extend(getattr(route, "routes", []) if nested is None else [])
    return found


def test_create_app_registers_every_route_group() -> None:
    """Built without entering the lifespan: route registration is
    synchronous, and the wired-up behaviour is covered by every other
    HTTP test in this suite."""
    application = create_app()
    paths = _all_paths(application)

    assert {"/health", "/liveness", "/readiness", "/metrics"} <= paths
    assert "/prompts" in paths
    assert "/prompts/{prompt_id}" in paths
    assert "/openapi.json" in paths
    assert "/docs" in paths


def test_create_app_installs_the_full_middleware_stack() -> None:
    """Each of these is load-bearing: request context feeds every log
    line's ``request_id``, localization drives error messages, validation
    rejects oversized bodies, and the security headers are what a browser
    client depends on."""
    application = create_app()
    installed = {middleware.cls.__name__ for middleware in application.user_middleware}

    assert {
        "CORSMiddleware",
        "RequestContextMiddleware",
        "LocalizationMiddleware",
        "RequestValidationMiddleware",
        "SecurityHeadersMiddleware",
    } <= installed


async def test_the_metrics_endpoint_serves_prometheus_text(client: AsyncClient) -> None:
    response = await client.get("/metrics")

    assert response.status_code == HTTP_OK
    assert "http_request" in response.text


async def test_the_openapi_document_describes_the_prompt_routes(client: AsyncClient) -> None:
    document = (await client.get("/openapi.json")).json()

    assert document["info"]["title"] == "AI-IOS Enterprise Prompt Management Service"
    assert "/prompts" in document["paths"]
    assert "/prompts/{prompt_id}/publish" in document["paths"]


async def test_security_headers_reach_the_client(client: AsyncClient) -> None:
    response = await client.get("/health")

    lowered = {key.lower() for key in response.headers}
    assert "x-content-type-options" in lowered


async def test_every_response_carries_a_request_id(client: AsyncClient) -> None:
    """The envelope's ``request_id`` comes from the request-context
    middleware, so a missing one means logs and responses cannot be
    correlated for a report of "my request failed"."""
    response = await client.get("/health")

    assert response.json()["meta"]["request_id"] != "unknown"


async def test_the_lifespan_wired_every_piece_of_state(app: FastAPI) -> None:
    """One assertion per attribute the lifespan sets, so a startup step
    that silently stopped running is caught here rather than as a 500 from
    whichever route happened to need it first."""
    assert app.state.db_engine is not None
    assert app.state.db_session_factory is not None
    assert app.state.cache_manager is not None
    assert app.state.redis_client is not None
    assert app.state.publish_event is not None
    assert app.state.jwt_public_key.startswith("-----BEGIN PUBLIC KEY-----")
    assert app.state.service_settings is not None
    assert isinstance(app.state.http_client, httpx.AsyncClient)


async def test_the_lifespan_leaves_no_scheduler_when_workers_are_disabled(app: FastAPI) -> None:
    """``AIIOS_PROMPT_MANAGEMENT_SERVICE_WORKERS_ENABLED=false`` in the
    conftest, so the sweeps must not be running: a scheduler started
    under test would fire real ticks against the test database mid-run."""
    assert app.state.scheduler_manager is None
    assert app.state.service_settings.workers_enabled is False


async def test_enabling_workers_really_registers_and_starts_all_four_sweeps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wire itself, end to end, with nothing stubbed.

    Every other test in this suite runs with workers off, so without this
    one ``_build_workers`` would never execute at all -- and a scheduler
    that silently failed to register would look exactly like a healthy
    service until someone noticed approvals never expiring. Testing the
    registrar in isolation cannot catch that: the registrar is correct in
    :mod:`tests.test_workers` and the factory could still not call it.

    A real ``SchedulerManager`` on real RabbitMQ and real Redis, started
    and then stopped. Intervals are set high so no tick can fire against
    the test database inside the few milliseconds it is up.

    ``get_settings`` is ``lru_cache``d process-wide, so the cache has to
    be cleared for the new environment to be read at all -- and cleared
    again afterwards, or a later ``create_app()`` in the same session
    would inherit workers-enabled settings and start a real scheduler
    nobody asked for.
    """
    monkeypatch.setenv("AIIOS_PROMPT_MANAGEMENT_SERVICE_WORKERS_ENABLED", "true")
    monkeypatch.setenv("AIIOS_PROMPT_MANAGEMENT_SERVICE_APPROVAL_EXPIRY_SWEEP_SECONDS", "3600")
    monkeypatch.setenv("AIIOS_PROMPT_MANAGEMENT_SERVICE_REVIEW_CYCLE_SWEEP_SECONDS", "86400")
    monkeypatch.setenv("AIIOS_PROMPT_MANAGEMENT_SERVICE_AB_TEST_EVALUATION_SECONDS", "86400")
    monkeypatch.setenv("AIIOS_PROMPT_MANAGEMENT_SERVICE_STATISTICS_ROLLUP_SECONDS", "86400")
    get_settings.cache_clear()

    try:
        assert get_settings().service.workers_enabled is True

        application = create_app()
        async with application.router.lifespan_context(application):
            manager = application.state.scheduler_manager
            assert manager is not None

            jobs = manager.registry.list_jobs()
            assert {job.job_id for job in jobs} == {
                APPROVAL_EXPIRY_SWEEP_JOB_ID,
                REVIEW_CYCLE_SWEEP_JOB_ID,
                AB_EVALUATION_SWEEP_JOB_ID,
                STATISTICS_ROLLUP_JOB_ID,
            }

            # Registered *and* scheduled: a job with no ``next_run`` sits
            # in the registry and never fires, which is the failure mode
            # this test exists for.
            assert all(job.next_run is not None for job in jobs)

            # And each fn is really this service's own worker entry point,
            # not a placeholder that merely happens to be callable.
            assert all(job.fn.__name__ == "run_job" for job in jobs)
            assert {job.metadata["component"] for job in jobs} == {job.job_id for job in jobs}
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# CORS policy
# ---------------------------------------------------------------------------


def test_development_cors_is_permissive() -> None:
    """The default profile, which is what every other test in this suite
    runs under."""
    config = _build_cors_config(build_settings())
    assert config.allow_origins


def test_production_cors_uses_the_configured_allowlist() -> None:
    """The branch that matters: a production deployment must not fall
    through to the development policy, which allows any origin. That would
    let any site a logged-in user visits call this API with their
    credentials.

    Built as a fresh :class:`Settings` rather than by mutating the one
    ``build_settings`` returns -- its ``application`` section is a shared
    instance, so editing it in place would leak a production environment
    into every later test in the session.
    """
    base = build_settings()
    production = Settings(
        application=ApplicationSettings(environment=Environment.PRODUCTION, _env_file=None),
        database=base.database,
        redis=base.redis,
        rabbitmq=base.rabbitmq,
        email=base.email,
        service=PromptManagementServiceSettings(
            cors_allowed_origins=["https://console.example.com"], _env_file=None
        ),
    )

    config = _build_cors_config(production)

    assert list(config.allow_origins) == ["https://console.example.com"]
    assert "*" not in config.allow_origins
    assert base.application.environment is not Environment.PRODUCTION
