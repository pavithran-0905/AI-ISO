"""A minimal end-to-end smoke test, run once before the full test pass.

Confirms the real app boots through its actual lifespan against real
PostgreSQL/Redis/RabbitMQ, and that the core prompt lifecycle --
create, draft, scan, approve, publish, render, roll back -- works end
to end through genuine HTTP requests.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from tests.conftest import HTTP_CONFLICT, HTTP_CREATED, HTTP_OK, AuthHeadersFn


async def test_health_and_readiness(client: AsyncClient) -> None:
    health = await client.get("/health")
    assert health.status_code == HTTP_OK
    assert health.json()["data"]["status"] == "healthy"

    readiness = await client.get("/readiness")
    assert readiness.status_code == HTTP_OK
    assert readiness.json()["data"]["status"] in {"ready", "not_ready"}

    liveness = await client.get("/liveness")
    assert liveness.status_code == HTTP_OK
    assert liveness.json()["data"]["status"] == "alive"


async def test_full_prompt_lifecycle_end_to_end(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(uuid.uuid4())
    params = {"organization_id": str(organization_id)}

    created = await client.post(
        "/prompts",
        params=params,
        json={
            "slug": "smoke-prompt",
            "name": "Smoke Prompt",
            "prompt_type": "system",
            "body": "Summarize {{ topic }} in {{ count }} points.",
            "variables": [
                {"name": "topic", "value_type": "string"},
                {"name": "count", "value_type": "integer", "default_value": "3"},
            ],
        },
        headers=headers,
    )
    assert created.status_code == HTTP_CREATED, created.text
    prompt = created.json()["data"]
    prompt_id = prompt["id"]
    assert prompt["status"] == "draft"
    assert prompt["current_version_number"] is None

    listed = await client.get("/prompts", params=params, headers=headers)
    assert listed.status_code == HTTP_OK
    assert any(row["id"] == prompt_id for row in listed.json()["data"])

    variables = await client.get(f"/prompts/{prompt_id}/variables", params=params, headers=headers)
    assert variables.status_code == HTTP_OK, variables.text
    assert {v["name"] for v in variables.json()["data"]} == {"topic", "count"}

    # The publication gate must refuse before anything has been done.
    gate = await client.get(
        f"/prompts/{prompt_id}/gate",
        params={**params, "version_number": "1.0.0"},
        headers=headers,
    )
    assert gate.status_code == HTTP_OK, gate.text
    assert gate.json()["data"]["allowed"] is False
    assert gate.json()["data"]["blockers"]

    blocked = await client.post(
        f"/prompts/{prompt_id}/publish",
        params=params,
        json={"version_number": "1.0.0"},
        headers=headers,
    )
    assert blocked.status_code == HTTP_CONFLICT, blocked.text

    scanned = await client.post(
        f"/prompts/{prompt_id}/scan",
        params={**params, "version_number": "1.0.0"},
        headers=headers,
    )
    assert scanned.status_code == HTTP_CREATED, scanned.text
    assert scanned.json()["data"]["status"] == "clean"

    approval = await client.post(
        f"/prompts/{prompt_id}/approvals",
        params=params,
        json={"version_number": "1.0.0", "required_approvals": 1},
        headers=headers,
    )
    assert approval.status_code == HTTP_CREATED, approval.text
    approval_id = approval.json()["data"]["id"]

    decided = await client.post(
        f"/prompts/approvals/{approval_id}", params=params, json={"approve": True}, headers=headers
    )
    assert decided.status_code == HTTP_OK, decided.text
    assert decided.json()["data"]["status"] == "approved"

    published = await client.post(
        f"/prompts/{prompt_id}/publish",
        params=params,
        json={"version_number": "1.0.0"},
        headers=headers,
    )
    assert published.status_code == HTTP_OK, published.text
    assert published.json()["data"]["status"] == "published"
    assert published.json()["data"]["current_version_number"] == "1.0.0"

    rendered = await client.post(
        f"/prompts/{prompt_id}/render",
        params=params,
        json={"variables": {"topic": "AI safety", "count": 5}},
        headers=headers,
    )
    assert rendered.status_code == HTTP_OK, rendered.text
    assert rendered.json()["data"]["body"] == "Summarize AI safety in 5 points."

    await _assert_second_revision_and_rollback(client, headers, params, prompt_id)
    await _assert_analytics_and_archive(client, headers, params, prompt_id)


async def _assert_second_revision_and_rollback(client, headers, params, prompt_id) -> None:
    """Draft 1.1.0, force past its own gate, then roll back to 1.0.0.

    Split out of the lifecycle test purely to keep one function under
    the statement ceiling; every assertion is unchanged.
    """
    drafted = await client.post(
        f"/prompts/{prompt_id}/versions",
        params=params,
        json={"body": "Give {{ count }} points on {{ topic }}.", "component": "minor"},
        headers=headers,
    )
    assert drafted.status_code == HTTP_CREATED, drafted.text
    assert drafted.json()["data"]["version_number"] == "1.1.0"

    versions = await client.get(f"/prompts/{prompt_id}/versions", params=params, headers=headers)
    assert versions.status_code == HTTP_OK
    assert len(versions.json()["data"]) == 2

    # 1.1.0 has no approval of its own, so the gate must still refuse it.
    gate2 = await client.get(
        f"/prompts/{prompt_id}/gate",
        params={**params, "version_number": "1.1.0"},
        headers=headers,
    )
    assert gate2.json()["data"]["allowed"] is False

    forced = await client.post(
        f"/prompts/{prompt_id}/publish",
        params=params,
        json={"version_number": "1.1.0", "force": True},
        headers=headers,
    )
    assert forced.status_code == HTTP_OK, forced.text
    assert forced.json()["data"]["current_version_number"] == "1.1.0"

    rolled = await client.post(
        f"/prompts/{prompt_id}/rollback",
        params=params,
        json={"version_number": "1.0.0"},
        headers=headers,
    )
    assert rolled.status_code == HTTP_OK, rolled.text
    assert rolled.json()["data"]["current_version_number"] == "1.0.0"


async def _assert_analytics_and_archive(client, headers, params, prompt_id) -> None:
    """Statistics, reporting, and archival -- split out of the lifecycle
    test purely to keep one function under the statement ceiling."""
    statistics = await client.get("/prompts/statistics", params=params, headers=headers)
    assert statistics.status_code == HTTP_OK

    report = await client.post(
        "/prompts/reports", params={**params, "kind": "usage"}, headers=headers
    )
    assert report.status_code == HTTP_CREATED, report.text
    assert report.json()["data"]["status"] == "completed"

    archived = await client.delete(f"/prompts/{prompt_id}", params=params, headers=headers)
    assert archived.status_code == HTTP_OK, archived.text
    assert archived.json()["data"]["status"] == "archived"


async def test_static_routes_are_not_hijacked_by_the_catch_all(
    client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
) -> None:
    """``/prompts/test`` must not resolve as ``prompt_id="test"``.

    The router-ordering bug class this platform has hit three times.
    A 422 here would mean the catch-all won and UUID parsing failed.

    Sent authenticated, because every read route requires a token -- an
    unauthenticated 401 would be indistinguishable from a shadowed route
    for the purpose of this check.
    """
    params = {"organization_id": str(organization_id)}
    headers = auth_headers(uuid.uuid4(), organization_id=organization_id)
    for path in ("/prompts/test", "/prompts/ab-test", "/prompts/statistics", "/prompts/reports"):
        response = await client.get(path, params=params, headers=headers)
        assert response.status_code == HTTP_OK, f"{path} -> {response.status_code}"
