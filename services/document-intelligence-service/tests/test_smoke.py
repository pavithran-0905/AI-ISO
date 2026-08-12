"""Smoke tests: the app builds, every route is registered, health answers.

These exist to catch the class of failure that makes every other test
meaningless -- a registry that never populated, a route shadowed by a
catch-all, a dependency that cannot be constructed.
"""

from __future__ import annotations

from fastapi import FastAPI
from httpx import AsyncClient
import pytest

from app.documents.parser import supported_formats
from app.models.enums import DocumentFormat
from tests.conftest import HTTP_OK, HTTP_UNAUTHORIZED

pytestmark = pytest.mark.asyncio


EXPECTED_ROUTES = {
    ("GET", "/health"),
    ("GET", "/liveness"),
    ("GET", "/readiness"),
    ("GET", "/metrics"),
    ("GET", "/documents"),
    ("POST", "/documents"),
    ("GET", "/documents/statistics"),
    ("POST", "/documents/statistics/rollup"),
    ("GET", "/documents/reports"),
    ("POST", "/documents/reports"),
    ("GET", "/documents/{document_id}"),
    ("PUT", "/documents/{document_id}"),
    ("DELETE", "/documents/{document_id}"),
    ("POST", "/documents/{document_id}/ocr"),
    ("POST", "/documents/{document_id}/classify"),
    ("POST", "/documents/{document_id}/extract"),
    ("GET", "/documents/{document_id}/extraction"),
    ("POST", "/documents/{document_id}/summarize"),
    ("POST", "/documents/{document_id}/translate"),
    ("GET", "/documents/{document_id}/language"),
    ("POST", "/documents/{document_id}/validate"),
    ("POST", "/documents/{document_id}/review"),
    ("GET", "/documents/{document_id}/reviews"),
    ("POST", "/documents/{document_id}/review/{review_id}/decision"),
}


def _routes(app: FastAPI) -> set[tuple[str, str]]:
    """Every (method, path) the app serves.

    Walks ``original_router`` on included routers: ``include_router``
    wraps children in ``_IncludedRouter``, which exposes that attribute
    rather than ``routes``, so a naive walk finds only FastAPI's own
    built-ins.
    """
    found: set[tuple[str, str]] = set()

    def walk(router: object) -> None:
        for route in getattr(router, "routes", []):
            inner = getattr(route, "original_router", None)
            if inner is not None:
                walk(inner)
                continue
            methods = getattr(route, "methods", None)
            path = getattr(route, "path", None)
            if methods and path:
                found.update((m, path) for m in methods if m not in {"HEAD", "OPTIONS"})

    walk(app.router)
    return found


async def test_every_spec_route_is_registered(app: FastAPI) -> None:
    missing = EXPECTED_ROUTES - _routes(app)
    assert not missing, f"routes missing from the app: {sorted(missing)}"


async def test_statistics_is_not_shadowed_by_the_id_catch_all(app: FastAPI) -> None:
    """``/documents/statistics`` must be declared before ``/documents/{id}``.

    Declaration order decides this in FastAPI, so the assertion is on the
    order itself rather than on a response -- a response test would pass
    for the wrong reason if the catch-all happened to 404.
    """
    paths = [
        getattr(route, "path", "")
        for included in app.router.routes
        for route in getattr(getattr(included, "original_router", included), "routes", [])
    ]
    assert "/documents/statistics" in paths
    assert "/documents/{document_id}" in paths
    assert paths.index("/documents/statistics") < paths.index("/documents/{document_id}")


async def test_health_is_open_and_reports_healthy(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == HTTP_OK
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "healthy"


async def test_liveness_answers_without_a_token(client: AsyncClient) -> None:
    response = await client.get("/liveness")
    assert response.status_code == HTTP_OK
    assert response.json()["data"]["status"] == "alive"


async def test_readiness_reports_each_dependency(client: AsyncClient) -> None:
    response = await client.get("/readiness")
    assert response.status_code == HTTP_OK
    names = {check["name"] for check in response.json()["data"]["checks"]}
    assert "database" in names


async def test_metrics_is_exposed(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert response.status_code == HTTP_OK
    assert "python_info" in response.text or "http_request" in response.text


async def test_business_routes_require_authentication(client: AsyncClient) -> None:
    for method, path in [
        ("GET", "/documents"),
        ("GET", "/documents/statistics"),
        ("GET", "/documents/reports"),
    ]:
        response = await client.request(method, path)
        assert response.status_code == HTTP_UNAUTHORIZED, f"{method} {path} was not gated"


async def test_every_declared_format_has_a_parser() -> None:
    """Every format but UNKNOWN must be parseable.

    This is the test that would have caught Prompt 062's empty package
    ``__init__``: the registry populates by import side effect, and a
    package that never imported the format modules serves a service whose
    every upload fails.
    """
    registered = set(supported_formats())
    expected = set(DocumentFormat) - {DocumentFormat.UNKNOWN}
    assert expected <= registered, f"formats with no parser: {expected - registered}"


async def test_the_openapi_schema_builds(app: FastAPI) -> None:
    """A schema that cannot be generated is a broken response model."""
    schema = app.openapi()
    assert schema["info"]["title"]
    assert "/documents" in schema["paths"]
