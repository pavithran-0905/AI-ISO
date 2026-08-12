"""Smoke tests: the app builds, its routes exist, and health answers."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from tests.conftest import HTTP_OK, HTTP_UNAUTHORIZED, AuthHeadersFn


def _paths(application: FastAPI) -> set[tuple[str, str]]:
    """Every (method, path) the app serves, through the include wrapper.

    ``include_router`` wraps children in a ``_IncludedRouter`` that exposes
    ``original_router`` rather than ``routes``, so walking ``app.routes``
    naively finds only the four FastAPI built-ins and reports a fully wired
    service as empty.
    """
    found: set[tuple[str, str]] = set()

    def walk(routes: object) -> None:
        for route in routes:  # type: ignore[attr-defined]
            inner = getattr(route, "original_router", None)
            if inner is not None:
                walk(inner.routes)
            elif hasattr(route, "methods"):
                for method in route.methods:
                    found.add((method, route.path))

    walk(application.routes)
    return found


SPEC_ROUTES = [
    ("POST", "/rag/documents"),
    ("GET", "/rag/documents"),
    ("PUT", "/rag/documents/{document_id}"),
    ("DELETE", "/rag/documents/{document_id}"),
    ("POST", "/rag/index"),
    ("POST", "/rag/reindex"),
    ("POST", "/rag/search"),
    ("POST", "/rag/retrieve"),
    ("POST", "/rag/context"),
    ("GET", "/rag/sources"),
    ("POST", "/rag/sources"),
    ("GET", "/rag/statistics"),
    ("GET", "/rag/reports"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path"), SPEC_ROUTES)
async def test_every_spec_route_is_served(app: FastAPI, method: str, path: str) -> None:
    assert (method, path) in _paths(app)


@pytest.mark.asyncio
async def test_health_endpoints_answer(client: AsyncClient) -> None:
    for path in ("/health", "/liveness", "/readiness"):
        response = await client.get(path)
        assert response.status_code == HTTP_OK, path
        assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_readiness_reports_postgres(client: AsyncClient) -> None:
    body = (await client.get("/readiness")).json()["data"]
    assert "database" in {check["name"] for check in body["checks"]}


@pytest.mark.asyncio
async def test_metrics_and_openapi_are_served(client: AsyncClient) -> None:
    assert (await client.get("/metrics")).status_code == HTTP_OK
    schema = (await client.get("/openapi.json")).json()
    assert "/rag/search" in schema["paths"]


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path"), SPEC_ROUTES)
async def test_no_spec_route_is_anonymous(client: AsyncClient, method: str, path: str) -> None:
    """Every route refuses a caller with no token.

    Parameterised over the spec routes rather than spot-checked, because
    the failure mode is one route being forgotten -- and an enumeration is
    the only assertion that catches the one nobody thought about.
    """
    concrete = path.replace("{document_id}", str(uuid.uuid4()))
    response = await client.request(method, concrete, json={"query": "x"})
    assert response.status_code in {HTTP_UNAUTHORIZED, 403}, f"{method} {path}"


@pytest.mark.asyncio
async def test_a_token_without_an_organization_is_refused(
    client: AsyncClient, auth_headers: AuthHeadersFn
) -> None:
    """No organization claim means no tenant to scope to, so no access.

    Guessing a tenant would either disclose another one's corpus or
    silently return nothing; both are worse than refusing.
    """
    response = await client.get("/rag/documents", headers=auth_headers())
    assert response.status_code in {HTTP_UNAUTHORIZED, 403}
