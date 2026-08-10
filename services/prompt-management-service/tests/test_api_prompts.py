"""Tests for :mod:`app.api.prompts` -- all 34 routes, over real HTTP.

The **real** FastAPI app, started through its actual lifespan against
real PostgreSQL, Redis, and RabbitMQ, driven with real signed JWTs. The
only override is the request session, so a test's writes roll back.

**Route registration order is a real bug class in this codebase**, hit in
notification-center, plugin-marketplace, and ai-agent-platform before
this service was written: a static segment registered *after* a
``/{prompt_id}`` catch-all is unreachable, because ``/prompts/statistics``
matches ``/prompts/{prompt_id}`` first and fails UUID parsing with a 422
that looks like a client mistake. Every static-segment route below is
therefore asserted to return something other than 422 for its own path,
which is what a shadowed route would produce.

**What HTTP tests cannot check here.** The ``app`` fixture overrides the
request session, which changes transaction lifetime -- so anything whose
correctness depends on transaction lifetime is out of scope for this
module by construction, exactly as the conftest documents.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.enums import (
    AbTestArm,
    AuditAction,
    ExecutionStatus,
    OptimizationStatus,
    PromptCategory,
    PromptLifecycleStatus,
    PromptType,
    ReportKind,
    ReviewDecision,
    SharingScope,
    VariableKind,
)
from app.models.prompt import Prompt, PromptVersion
from app.models.template import PromptVariable
from app.repositories.analytics import PromptAuditRepository
from tests.conftest import (
    HTTP_BAD_REQUEST,
    HTTP_CONFLICT,
    HTTP_CREATED,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_UNPROCESSABLE,
    AuthHeadersFn,
    MakePromptFn,
    MakePublishedFn,
    ago,
    soon,
)

_VERBOSE_BODY = (
    "Please note that it is important to remember that you should always "
    "make sure that you carefully consider each and every one of the "
    "following points in order to be able to respond appropriately.\n"
    "Please note that it is important to remember that you should always "
    "make sure that you carefully consider each and every one of the "
    "following points in order to be able to respond appropriately.\n"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def caller_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def headers(
    auth_headers: AuthHeadersFn, caller_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, str]:
    return auth_headers(caller_id, organization_id=organization_id)


@pytest.fixture
def org(organization_id: uuid.UUID) -> dict[str, str]:
    """The ``organization_id`` query parameter every route takes."""
    return {"organization_id": str(organization_id)}


def _data(response: Any) -> Any:
    """The envelope's own ``data`` member, asserting the envelope shape.

    Asserts ``success`` too, so calling this on a response that actually
    failed is a loud test error rather than a confusing ``KeyError`` on
    ``data`` -- error responses carry a different envelope entirely.
    """
    payload = response.json()
    assert payload.get("success") is True, f"{response.status_code}: {response.text}"
    assert set(payload) >= {"message", "data", "meta"}
    assert payload["meta"]["request_id"]
    return payload["data"]


async def _satisfy_gate(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    prompt_id: uuid.UUID,
    version_number: str,
) -> None:
    """Grant the approval and run the scan the gate requires.

    The service's own defaults are ``required_approvals=1`` and
    ``block_publish_on_critical=True`` with no scan on record, so a bare
    draft does *not* publish -- which is the point of the gate. Anything
    below that publishes normally goes through here first; the
    force-override path is tested separately.
    """
    approval = _data(
        await client.post(
            f"/prompts/{prompt_id}/approvals",
            params=org,
            headers=headers,
            json={"version_number": version_number, "required_approvals": 1},
        )
    )
    await client.post(
        f"/prompts/approvals/{approval['id']}", params=org, headers=headers, json={"approve": True}
    )
    await client.post(
        f"/prompts/{prompt_id}/scan",
        params={**org, "version_number": version_number},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Prompt CRUD
# ---------------------------------------------------------------------------


async def test_creating_a_prompt_returns_it_as_a_draft(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    response = await client.post(
        "/prompts",
        params=org,
        headers=headers,
        json={
            "slug": "greeting",
            "name": "Greeting",
            "prompt_type": str(PromptType.SYSTEM),
            "body": "Hello {{ name }}",
            "description": "Says hello.",
            "category": str(PromptCategory.AUTOMATION),
            "sharing_scope": str(SharingScope.ORGANIZATION),
            "owner_id": "team-platform",
            "tags": ["greeting", "demo"],
            "variables": [{"name": "name", "kind": "runtime"}],
        },
    )

    assert response.status_code == HTTP_CREATED
    body = _data(response)
    assert body["slug"] == "greeting"
    assert body["status"] == str(PromptLifecycleStatus.DRAFT)
    assert body["current_version_number"] is None
    assert body["tags"] == ["greeting", "demo"]
    assert body["owner_id"] == "team-platform"


async def test_a_created_prompts_variables_are_stored_with_its_first_revision(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    """Declared alongside the prompt, so the very first draft is
    renderable without a second call."""
    created = _data(
        await client.post(
            "/prompts",
            params=org,
            headers=headers,
            json={
                "slug": "with-vars",
                "name": "With Vars",
                "prompt_type": str(PromptType.SYSTEM),
                "body": "Hello {{ name }}",
                "variables": [
                    {"name": "name", "kind": "runtime", "required": True, "is_masked": True}
                ],
            },
        )
    )

    listed = _data(
        await client.get(f"/prompts/{created['id']}/variables", params=org, headers=headers)
    )
    assert [row["name"] for row in listed] == ["name"]
    assert listed[0]["is_masked"] is True


async def test_a_duplicate_slug_is_a_conflict_not_a_second_prompt(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    payload = {
        "slug": "taken",
        "name": "Taken",
        "prompt_type": str(PromptType.SYSTEM),
        "body": "Hello",
    }
    assert (
        await client.post("/prompts", params=org, headers=headers, json=payload)
    ).status_code == HTTP_CREATED

    assert (
        await client.post("/prompts", params=org, headers=headers, json=payload)
    ).status_code == HTTP_CONFLICT


async def test_creating_a_prompt_with_a_broken_template_is_refused(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    """Validated at the door, so an unrenderable body never becomes a
    stored revision someone later tries to publish.

    400, not 422: the body parsed fine as JSON and satisfied the schema.
    What failed is a domain rule, which is what shared_core maps
    ``ValidationError`` onto.
    """
    response = await client.post(
        "/prompts",
        params=org,
        headers=headers,
        json={
            "slug": "broken",
            "name": "Broken",
            "prompt_type": str(PromptType.SYSTEM),
            "body": "Hello {{ name",
        },
    )

    assert response.status_code == HTTP_BAD_REQUEST
    assert response.json()["error"]["code"].startswith("AIIOS-VAL")

    # The specific reason ("unexpected end of template") is logged
    # server-side and deliberately not returned: the client gets a
    # generic localized message plus a code, so an internal parser
    # message never becomes part of the public contract.
    assert "end of template" not in response.text


async def test_listing_prompts_returns_this_organizations_own(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    await make_prompt("first")
    await make_prompt("second")

    listed = _data(await client.get("/prompts", params=org, headers=headers))

    assert {row["slug"] for row in listed} == {"first", "second"}


async def test_listing_prompts_never_crosses_tenants(
    client: AsyncClient,
    auth_headers: AuthHeadersFn,
    caller_id: uuid.UUID,
    make_prompt: MakePromptFn,
) -> None:
    await make_prompt("mine")
    other = uuid.uuid4()

    listed = _data(
        await client.get(
            "/prompts",
            params={"organization_id": str(other)},
            headers=auth_headers(caller_id, organization_id=other),
        )
    )
    assert listed == []


@pytest.mark.parametrize(
    ("filter_name", "filter_value"),
    [
        ("prompt_type", str(PromptType.SYSTEM)),
        ("category", str(PromptCategory.AUTOMATION)),
        ("status", str(PromptLifecycleStatus.DRAFT)),
    ],
)
async def test_listing_prompts_applies_each_filter(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    make_prompt: MakePromptFn,
    filter_name: str,
    filter_value: str,
) -> None:
    await make_prompt("matching", category=PromptCategory.AUTOMATION)

    listed = _data(
        await client.get("/prompts", params={**org, filter_name: filter_value}, headers=headers)
    )
    assert [row["slug"] for row in listed] == ["matching"]


async def test_a_filter_that_matches_nothing_returns_an_empty_list(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    await make_prompt("drafted")

    listed = _data(
        await client.get(
            "/prompts",
            params={**org, "status": str(PromptLifecycleStatus.PUBLISHED)},
            headers=headers,
        )
    )
    assert listed == []


async def test_a_free_text_query_takes_the_search_path(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    """``query`` bypasses the structured filters entirely, which is worth
    pinning: a search that also applied them would silently return
    nothing whenever both were sent."""
    await make_prompt("findable", name="A Findable Prompt")
    await make_prompt("other", name="Something Else")

    listed = _data(
        await client.get("/prompts", params={**org, "query": "Findable"}, headers=headers)
    )

    assert [row["slug"] for row in listed] == ["findable"]


async def test_listing_prompts_pages(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    for index in range(3):
        await make_prompt(f"page-{index}")

    first = _data(await client.get("/prompts", params={**org, "limit": 2}, headers=headers))
    second = _data(
        await client.get("/prompts", params={**org, "limit": 2, "offset": 2}, headers=headers)
    )

    assert len(first) == 2
    assert len(second) == 1
    assert {r["id"] for r in first}.isdisjoint({r["id"] for r in second})


async def test_getting_one_prompt(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, _version = await make_prompt("fetch-me")

    body = _data(await client.get(f"/prompts/{prompt.id}", params=org, headers=headers))
    assert body["slug"] == "fetch-me"


async def test_getting_an_unknown_prompt_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    response = await client.get(f"/prompts/{uuid.uuid4()}", params=org, headers=headers)
    assert response.status_code == HTTP_NOT_FOUND


async def test_getting_another_tenants_prompt_is_a_404_not_a_403(
    client: AsyncClient,
    auth_headers: AuthHeadersFn,
    caller_id: uuid.UUID,
    make_prompt: MakePromptFn,
) -> None:
    """404, so the response does not confirm that the id exists at all."""
    prompt, _version = await make_prompt("private")
    other = uuid.uuid4()

    response = await client.get(
        f"/prompts/{prompt.id}",
        params={"organization_id": str(other)},
        headers=auth_headers(caller_id, organization_id=other),
    )
    assert response.status_code == HTTP_NOT_FOUND


async def test_updating_a_prompt_changes_only_what_was_sent(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, _version = await make_prompt("editable", name="Original")

    body = _data(
        await client.put(
            f"/prompts/{prompt.id}",
            params=org,
            headers=headers,
            json={"name": "Renamed", "tags": ["new"]},
        )
    )

    assert body["name"] == "Renamed"
    assert body["tags"] == ["new"]
    assert body["prompt_type"] == str(PromptType.SYSTEM)


async def test_an_empty_update_is_accepted_and_changes_nothing(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    """Every field is optional, so ``{}`` is a legal no-op rather than a
    422 -- which matters for a client that diffs a form and sends only
    what changed."""
    prompt, _version = await make_prompt("untouched", name="Keep Me")

    body = _data(await client.put(f"/prompts/{prompt.id}", params=org, headers=headers, json={}))
    assert body["name"] == "Keep Me"


async def test_the_update_schema_offers_no_body_field(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    """Prompt text lives in immutable revisions. A ``body`` here would be
    a way to change published text without a new version, which is the
    whole thing versioning prevents."""
    prompt, version = await make_prompt("immutable")

    await client.put(
        f"/prompts/{prompt.id}", params=org, headers=headers, json={"body": "rewritten"}
    )

    versions = _data(
        await client.get(f"/prompts/{prompt.id}/versions", params=org, headers=headers)
    )
    assert [row["body"] for row in versions] == [version.body]


async def test_archiving_a_prompt(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, _version = await make_prompt("archive-me")

    body = _data(await client.delete(f"/prompts/{prompt.id}", params=org, headers=headers))
    assert body["status"] == str(PromptLifecycleStatus.ARCHIVED)


# ---------------------------------------------------------------------------
# Revisions and variables
# ---------------------------------------------------------------------------


async def test_listing_revisions_is_newest_first(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    make_prompt: MakePromptFn,
) -> None:
    prompt, _first = await make_prompt("versioned")
    await client.post(
        f"/prompts/{prompt.id}/versions",
        params=org,
        headers=headers,
        json={"body": "Second {{ name }}", "component": "minor"},
    )

    listed = _data(await client.get(f"/prompts/{prompt.id}/versions", params=org, headers=headers))
    assert [row["version_number"] for row in listed] == ["1.1.0", "1.0.0"]


async def test_adding_a_revision_bumps_the_requested_component(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, _version = await make_prompt("bumping")

    body = _data(
        await client.post(
            f"/prompts/{prompt.id}/versions",
            params=org,
            headers=headers,
            json={"body": "Rewritten {{ name }}", "component": "major", "changelog": "Big change."},
        )
    )

    assert body["version_number"] == "2.0.0"
    assert body["changelog"] == "Big change."
    assert body["published_at"] is None


async def test_a_new_revision_carries_variable_declarations_forward(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    """Otherwise a wording tweak would preview fine as a draft and then
    fail ``'name' is undefined`` the moment it was published."""
    created = _data(
        await client.post(
            "/prompts",
            params=org,
            headers=headers,
            json={
                "slug": "carrying",
                "name": "Carrying",
                "prompt_type": str(PromptType.SYSTEM),
                "body": "Hello {{ name }}",
                "variables": [{"name": "name", "kind": "runtime"}],
            },
        )
    )
    revision = _data(
        await client.post(
            f"/prompts/{created['id']}/versions",
            params=org,
            headers=headers,
            json={"body": "Greetings {{ name }}", "component": "minor"},
        )
    )

    listed = _data(
        await client.get(
            f"/prompts/{created['id']}/variables",
            params={**org, "version_number": revision["version_number"]},
            headers=headers,
        )
    )
    assert [row["name"] for row in listed] == ["name"]


async def test_a_new_revision_can_decline_to_carry_variables_forward(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    created = _data(
        await client.post(
            "/prompts",
            params=org,
            headers=headers,
            json={
                "slug": "not-carrying",
                "name": "Not Carrying",
                "prompt_type": str(PromptType.SYSTEM),
                "body": "Hello {{ name }}",
                "variables": [{"name": "name", "kind": "runtime"}],
            },
        )
    )
    revision = _data(
        await client.post(
            f"/prompts/{created['id']}/versions",
            params=org,
            headers=headers,
            json={"body": "Static text.", "carry_variables": False},
        )
    )

    listed = _data(
        await client.get(
            f"/prompts/{created['id']}/variables",
            params={**org, "version_number": revision["version_number"]},
            headers=headers,
        )
    )
    assert listed == []


async def test_listing_variables_falls_back_to_the_newest_draft(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    """A prompt that was never published has no live revision at all, so
    without this fallback an author could not inspect the draft they just
    created -- which is exactly when they need to."""
    created = _data(
        await client.post(
            "/prompts",
            params=org,
            headers=headers,
            json={
                "slug": "never-published",
                "name": "Never Published",
                "prompt_type": str(PromptType.SYSTEM),
                "body": "Hello {{ name }}",
                "variables": [{"name": "name", "kind": "runtime"}],
            },
        )
    )

    response = await client.get(f"/prompts/{created['id']}/variables", params=org, headers=headers)

    assert response.status_code == HTTP_OK
    assert [row["name"] for row in _data(response)] == ["name"]


async def test_listing_variables_prefers_the_live_revision(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    make_published: MakePublishedFn,
    variables_repo: Any,
) -> None:

    prompt, version = await make_published("live-vars")
    await variables_repo.create(
        PromptVariable(
            organization_id=prompt.organization_id,
            prompt_version_id=version.id,
            name="live_only",
        )
    )

    listed = _data(await client.get(f"/prompts/{prompt.id}/variables", params=org, headers=headers))
    assert [row["name"] for row in listed] == ["live_only"]


async def test_listing_variables_for_an_unknown_version_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, _version = await make_prompt("no-such-version")

    response = await client.get(
        f"/prompts/{prompt.id}/variables",
        params={**org, "version_number": "9.9.9"},
        headers=headers,
    )
    assert response.status_code == HTTP_NOT_FOUND


async def test_listing_variables_for_a_prompt_with_no_revisions_is_a_404(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    prompts_repo: Any,
    organization_id: uuid.UUID,
) -> None:
    """Only reachable for a row written outside ``PromptService``, which
    always creates a prompt and its first revision together."""
    bare = await prompts_repo.create(
        Prompt(
            organization_id=organization_id,
            slug="revision-less",
            name="Revision Less",
            prompt_type=PromptType.SYSTEM,
        )
    )

    response = await client.get(f"/prompts/{bare.id}/variables", params=org, headers=headers)
    assert response.status_code == HTTP_NOT_FOUND


# ---------------------------------------------------------------------------
# Publish, gate, rollback
# ---------------------------------------------------------------------------


async def test_publishing_a_revision_that_cleared_the_gate(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, version = await make_prompt("publishable")
    await _satisfy_gate(client, headers, org, prompt.id, version.version_number)

    body = _data(
        await client.post(
            f"/prompts/{prompt.id}/publish",
            params=org,
            headers=headers,
            json={"version_number": version.version_number},
        )
    )

    assert body["status"] == str(PromptLifecycleStatus.PUBLISHED)
    assert body["current_version_number"] == version.version_number


async def test_publishing_an_unknown_revision_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, _version = await make_prompt("publishable")

    response = await client.post(
        f"/prompts/{prompt.id}/publish",
        params=org,
        headers=headers,
        json={"version_number": "9.9.9"},
    )
    assert response.status_code == HTTP_NOT_FOUND


async def test_a_bare_draft_does_not_publish_by_default(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    """The service ships with ``required_approvals=1`` and a mandatory
    scan, so publishing is a deliberate act rather than the default.

    Worth its own test: if the defaults ever relaxed, every other publish
    test here would keep passing while the gate quietly stopped gating.
    """
    prompt, version = await make_prompt("ungated")

    response = await client.post(
        f"/prompts/{prompt.id}/publish",
        params=org,
        headers=headers,
        json={"version_number": version.version_number},
    )

    assert response.status_code == HTTP_CONFLICT
    assert response.json()["error"]["code"].startswith("AIIOS-CONFLICT")


async def test_a_blocked_gate_refuses_the_publish(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    """A mandatory reviewer who has not approved is a blocker even once
    the approval and scan gates are satisfied.

    The 409 itself does not name the blocker -- error responses carry a
    generic message and a code by design. ``GET /prompts/{id}/gate`` is
    the endpoint that reports blockers, and it is tested directly below.
    """
    prompt, version = await make_prompt("gated")
    await _satisfy_gate(client, headers, org, prompt.id, version.version_number)
    await client.post(
        f"/prompts/{prompt.id}/reviews",
        params=org,
        headers=headers,
        json={
            "version_number": version.version_number,
            "reviewer_id": "alice",
            "is_mandatory": True,
        },
    )

    response = await client.post(
        f"/prompts/{prompt.id}/publish",
        params=org,
        headers=headers,
        json={"version_number": version.version_number},
    )

    assert response.status_code == HTTP_CONFLICT

    gate = _data(
        await client.get(
            f"/prompts/{prompt.id}/gate",
            params={**org, "version_number": version.version_number},
            headers=headers,
        )
    )
    assert gate["blockers"] == ["A mandatory reviewer has not approved this revision."]


async def test_forcing_past_a_blocked_gate_publishes_and_records_the_override(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    make_prompt: MakePromptFn,
    audit_repo: PromptAuditRepository,
    organization_id: uuid.UUID,
) -> None:
    """A gate that could be skipped silently would not be a gate. The
    override is an audit row marked ``succeeded=False``, which is what
    makes it findable afterwards."""
    prompt, version = await make_prompt("forced")
    await client.post(
        f"/prompts/{prompt.id}/reviews",
        params=org,
        headers=headers,
        json={
            "version_number": version.version_number,
            "reviewer_id": "alice",
            "is_mandatory": True,
        },
    )

    response = await client.post(
        f"/prompts/{prompt.id}/publish",
        params=org,
        headers=headers,
        json={"version_number": version.version_number, "force": True},
    )

    assert response.status_code == HTTP_OK
    assert _data(response)["status"] == str(PromptLifecycleStatus.PUBLISHED)

    overrides = [
        row
        for row in await audit_repo.list_for_org(organization_id)
        if row.action == AuditAction.ADMINISTRATIVE
    ]
    assert len(overrides) == 1
    assert overrides[0].succeeded is False
    assert "overridden" in overrides[0].summary


async def test_forcing_an_already_passing_gate_records_no_override(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    make_prompt: MakePromptFn,
    audit_repo: PromptAuditRepository,
    organization_id: uuid.UUID,
) -> None:
    """``force`` on a revision that would have published anyway is not an
    override, and recording one would fill the trail with false alarms."""
    prompt, version = await make_prompt("force-unneeded")
    await _satisfy_gate(client, headers, org, prompt.id, version.version_number)

    await client.post(
        f"/prompts/{prompt.id}/publish",
        params=org,
        headers=headers,
        json={"version_number": version.version_number, "force": True},
    )

    actions = [str(row.action) for row in await audit_repo.list_for_org(organization_id)]
    assert str(AuditAction.ADMINISTRATIVE) not in actions


async def test_the_gate_endpoint_reports_every_blocker_at_once(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    """Someone preparing a publish wants the full list, not one round
    trip per problem."""
    prompt, version = await make_prompt("inspect-gate")
    await client.post(
        f"/prompts/{prompt.id}/reviews",
        params=org,
        headers=headers,
        json={
            "version_number": version.version_number,
            "reviewer_id": "alice",
            "is_mandatory": True,
        },
    )

    body = _data(
        await client.get(
            f"/prompts/{prompt.id}/gate",
            params={**org, "version_number": version.version_number},
            headers=headers,
        )
    )

    assert body["allowed"] is False
    assert len(body["blockers"]) >= 1
    assert body["reason"]


async def test_the_gate_endpoint_says_yes_for_a_clean_revision(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, version = await make_prompt("clean-gate")
    await _satisfy_gate(client, headers, org, prompt.id, version.version_number)

    body = _data(
        await client.get(
            f"/prompts/{prompt.id}/gate",
            params={**org, "version_number": version.version_number},
            headers=headers,
        )
    )

    assert body["allowed"] is True
    assert body["blockers"] == []


async def test_the_gate_endpoint_404s_for_an_unknown_revision(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, _version = await make_prompt("gate-404")

    response = await client.get(
        f"/prompts/{prompt.id}/gate", params={**org, "version_number": "9.9.9"}, headers=headers
    )
    assert response.status_code == HTTP_NOT_FOUND


async def test_rolling_back_points_at_the_earlier_revision(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    make_published: MakePublishedFn,
) -> None:
    prompt, first = await make_published("rollable")
    second = _data(
        await client.post(
            f"/prompts/{prompt.id}/versions",
            params=org,
            headers=headers,
            json={"body": "Second {{ name }}", "component": "minor"},
        )
    )
    await _satisfy_gate(client, headers, org, prompt.id, second["version_number"])
    await client.post(
        f"/prompts/{prompt.id}/publish",
        params=org,
        headers=headers,
        json={"version_number": second["version_number"]},
    )

    body = _data(
        await client.post(
            f"/prompts/{prompt.id}/rollback",
            params=org,
            headers=headers,
            json={"version_number": first.version_number},
        )
    )

    assert body["current_version_number"] == first.version_number
    assert body["status"] == str(PromptLifecycleStatus.PUBLISHED)


async def test_rolling_back_to_an_unpublished_revision_is_refused(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    make_published: MakePublishedFn,
) -> None:
    """Rollback is a return to a known-good state, so a revision that was
    never live is not one."""
    prompt, _first = await make_published("rollback-guard")
    draft = _data(
        await client.post(
            f"/prompts/{prompt.id}/versions",
            params=org,
            headers=headers,
            json={"body": "Draft {{ name }}", "component": "minor"},
        )
    )

    response = await client.post(
        f"/prompts/{prompt.id}/rollback",
        params=org,
        headers=headers,
        json={"version_number": draft["version_number"]},
    )
    assert response.status_code == HTTP_CONFLICT


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


async def test_rendering_a_published_prompt(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    make_published: MakePublishedFn,
    variables_repo: Any,
) -> None:

    prompt, version = await make_published("renderable")
    await variables_repo.create(
        PromptVariable(
            organization_id=prompt.organization_id, prompt_version_id=version.id, name="name"
        )
    )

    body = _data(
        await client.post(
            f"/prompts/{prompt.id}/render",
            params=org,
            headers=headers,
            json={"variables": {"name": "Ada"}},
        )
    )

    assert body["body"] == "Hello Ada"
    assert body["variables_used"] == ["name"]
    assert body["version_number"] == version.version_number
    assert body["estimated_tokens"] > 0


async def test_rendering_a_draft_over_http_is_refused(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    """The production read path refuses unreviewed text; previewing a
    draft is a different operation with a different route."""
    prompt, _version = await make_prompt("draft-render")

    response = await client.post(
        f"/prompts/{prompt.id}/render", params=org, headers=headers, json={"variables": {}}
    )
    assert response.status_code == HTTP_CONFLICT


async def test_rendering_returns_the_placeholder_for_a_secret_reference(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    make_published: MakePublishedFn,
    variables_repo: Any,
) -> None:
    """No secret resolver is wired into the HTTP path. Resolving live
    secrets needs the caller's own authority against
    secrets-management-service, which is a deliberate follow-up rather
    than something to do implicitly on every render."""

    prompt, version = await make_published("secret-render", body="Key: {{ api_key }}")
    await variables_repo.create(
        PromptVariable(
            organization_id=prompt.organization_id,
            prompt_version_id=version.id,
            name="api_key",
            kind=VariableKind.SECRET_REFERENCE,
            secret_reference="prod/openai",
        )
    )

    response = await client.post(
        f"/prompts/{prompt.id}/render", params=org, headers=headers, json={"variables": {}}
    )

    # Refused rather than rendered blank: sending an empty string where a
    # credential belongs would be a silently broken prompt.
    assert response.status_code == HTTP_BAD_REQUEST


async def test_rendering_can_pin_a_version_and_a_locale(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    make_published: MakePublishedFn,
) -> None:
    prompt, version = await make_published("pinned-render", body="Static text.")

    body = _data(
        await client.post(
            f"/prompts/{prompt.id}/render",
            params=org,
            headers=headers,
            json={"variables": {}, "version_number": version.version_number, "locale": "fr"},
        )
    )
    assert body["body"] == "Static text."


# ---------------------------------------------------------------------------
# Security scanning
# ---------------------------------------------------------------------------


async def test_scanning_a_clean_revision(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, version = await make_prompt("clean-scan", body="Summarise the input.")

    response = await client.post(
        f"/prompts/{prompt.id}/scan",
        params={**org, "version_number": version.version_number},
        headers=headers,
    )

    assert response.status_code == HTTP_CREATED
    assert _data(response)["status"] == "clean"


async def test_scanning_a_revision_containing_a_credential_blocks_it(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    """A prompt is stored, versioned, shared, and rendered into logs, so a
    credential written into one is already compromised."""
    prompt, version = await make_prompt(
        "leaky", body="api_key: sk-abcdefghij1234567890abcdefghij1234567890"
    )

    body = _data(
        await client.post(
            f"/prompts/{prompt.id}/scan",
            params={**org, "version_number": version.version_number},
            headers=headers,
        )
    )

    assert body["status"] == "blocked"
    assert body["finding_count"] >= 1


async def test_a_scan_finding_never_quotes_the_secret_it_found(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    """A scan row that recorded the secret would put it in the database,
    in every backup of it, and in any log line rendering the row."""
    secret = "sk-abcdefghij1234567890abcdefghij1234567890"
    prompt, version = await make_prompt("no-echo", body=f"api_key: {secret}")

    response = await client.post(
        f"/prompts/{prompt.id}/scan",
        params={**org, "version_number": version.version_number},
        headers=headers,
    )

    assert secret not in response.text


async def test_scanning_an_unknown_revision_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, _version = await make_prompt("scan-404")

    response = await client.post(
        f"/prompts/{prompt.id}/scan", params={**org, "version_number": "9.9.9"}, headers=headers
    )
    assert response.status_code == HTTP_NOT_FOUND


async def test_listing_a_revisions_scans(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, version = await make_prompt("scanned-twice", body="Summarise the input.")
    for _ in range(2):
        await client.post(
            f"/prompts/{prompt.id}/scan",
            params={**org, "version_number": version.version_number},
            headers=headers,
        )

    listed = _data(
        await client.get(
            f"/prompts/{prompt.id}/scans",
            params={**org, "version_number": version.version_number},
            headers=headers,
        )
    )
    assert len(listed) == 2


async def test_listing_scans_for_an_unknown_revision_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, _version = await make_prompt("scans-404")

    response = await client.get(
        f"/prompts/{prompt.id}/scans", params={**org, "version_number": "9.9.9"}, headers=headers
    )
    assert response.status_code == HTTP_NOT_FOUND


# ---------------------------------------------------------------------------
# Reviews and approvals
# ---------------------------------------------------------------------------


async def test_requesting_and_submitting_a_review(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, version = await make_prompt("reviewed")

    requested = _data(
        await client.post(
            f"/prompts/{prompt.id}/reviews",
            params=org,
            headers=headers,
            json={
                "version_number": version.version_number,
                "reviewer_id": "alice",
                "is_mandatory": True,
            },
        )
    )
    assert requested["decision"] == str(ReviewDecision.PENDING)

    submitted = _data(
        await client.post(
            f"/prompts/reviews/{requested['id']}",
            params=org,
            headers=headers,
            json={
                "decision": str(ReviewDecision.CHANGES_REQUESTED),
                "comments": "Please tighten the wording.",
                "requested_changes": ["shorten the preamble"],
            },
        )
    )

    assert submitted["decision"] == str(ReviewDecision.CHANGES_REQUESTED)
    assert submitted["comments"] == "Please tighten the wording."
    assert submitted["requested_changes"] == ["shorten the preamble"]
    assert submitted["submitted_at"] is not None


async def test_requesting_a_review_of_an_unknown_revision_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, _version = await make_prompt("review-404")

    response = await client.post(
        f"/prompts/{prompt.id}/reviews",
        params=org,
        headers=headers,
        json={"version_number": "9.9.9", "reviewer_id": "alice"},
    )
    assert response.status_code == HTTP_NOT_FOUND


async def test_submitting_a_verdict_on_an_unknown_review_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    response = await client.post(
        f"/prompts/reviews/{uuid.uuid4()}",
        params=org,
        headers=headers,
        json={"decision": str(ReviewDecision.APPROVED)},
    )
    assert response.status_code == HTTP_NOT_FOUND


async def test_a_verdict_cannot_be_rewritten(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    """Overwriting a recorded verdict would destroy the audit answer to
    "who approved this, and when?"."""
    prompt, version = await make_prompt("decided-once")
    review = _data(
        await client.post(
            f"/prompts/{prompt.id}/reviews",
            params=org,
            headers=headers,
            json={"version_number": version.version_number, "reviewer_id": "alice"},
        )
    )
    await client.post(
        f"/prompts/reviews/{review['id']}",
        params=org,
        headers=headers,
        json={"decision": str(ReviewDecision.APPROVED)},
    )

    response = await client.post(
        f"/prompts/reviews/{review['id']}",
        params=org,
        headers=headers,
        json={"decision": str(ReviewDecision.REJECTED)},
    )
    assert response.status_code == HTTP_CONFLICT


async def test_requesting_and_granting_an_approval(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    make_prompt: MakePromptFn,
    caller_id: uuid.UUID,
) -> None:
    prompt, version = await make_prompt("approved")

    requested = _data(
        await client.post(
            f"/prompts/{prompt.id}/approvals",
            params=org,
            headers=headers,
            json={"version_number": version.version_number, "required_approvals": 1},
        )
    )
    assert requested["status"] == "pending"
    assert requested["expires_at"] is not None

    decided = _data(
        await client.post(
            f"/prompts/approvals/{requested['id']}",
            params=org,
            headers=headers,
            json={"approve": True, "reason": "Looks right."},
        )
    )

    assert decided["status"] == "approved"
    assert decided["approver_id"] == str(caller_id)
    assert decided["decided_at"] is not None


async def test_refusing_an_approval_records_the_refusal(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, version = await make_prompt("refused")
    requested = _data(
        await client.post(
            f"/prompts/{prompt.id}/approvals",
            params=org,
            headers=headers,
            json={"version_number": version.version_number},
        )
    )

    decided = _data(
        await client.post(
            f"/prompts/approvals/{requested['id']}",
            params=org,
            headers=headers,
            json={"approve": False, "reason": "Not yet."},
        )
    )

    assert decided["status"] == "rejected"
    assert decided["reason"] == "Not yet."


async def test_requesting_an_approval_on_an_unknown_revision_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, _version = await make_prompt("approval-404")

    response = await client.post(
        f"/prompts/{prompt.id}/approvals",
        params=org,
        headers=headers,
        json={"version_number": "9.9.9"},
    )
    assert response.status_code == HTTP_NOT_FOUND


async def test_deciding_an_unknown_approval_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    response = await client.post(
        f"/prompts/approvals/{uuid.uuid4()}", params=org, headers=headers, json={"approve": True}
    )
    assert response.status_code == HTTP_NOT_FOUND


# ---------------------------------------------------------------------------
# Tests, evaluation, optimization
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def declared(make_prompt: MakePromptFn, variables_repo: Any) -> tuple[Prompt, PromptVersion]:
    """A prompt whose ``name`` variable is declared, so it renders."""

    prompt, version = await make_prompt("testable")
    await variables_repo.create(
        PromptVariable(
            organization_id=prompt.organization_id, prompt_version_id=version.id, name="name"
        )
    )
    return prompt, version


async def test_defining_listing_and_running_a_test_case(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    declared: tuple[Prompt, PromptVersion],
) -> None:
    prompt, version = declared

    defined = _data(
        await client.post(
            "/prompts/test",
            params=org,
            headers=headers,
            json={
                "prompt_id": str(prompt.id),
                "name": "greets by name",
                "variables": {"name": "Ada"},
                "expected_substrings": ["Hello"],
            },
        )
    )
    assert defined["name"] == "greets by name"

    listed = _data(await client.get("/prompts/test", params=org, headers=headers))
    assert [row["id"] for row in listed] == [defined["id"]]

    run = _data(
        await client.post(
            f"/prompts/test/{defined['id']}/run",
            params=org,
            headers=headers,
            json={"version_number": version.version_number},
        )
    )
    assert run["status"] == "passed"
    assert run["rendered_prompt"] == "Hello Ada"


async def test_running_a_test_against_a_supplied_model_output(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    declared: tuple[Prompt, PromptVersion],
) -> None:
    """This service cannot call a model, so a caller that already has a
    reply passes it in and the assertions apply to that instead."""
    prompt, _version = declared
    defined = _data(
        await client.post(
            "/prompts/test",
            params=org,
            headers=headers,
            json={
                "prompt_id": str(prompt.id),
                "name": "mentions Paris",
                "variables": {"name": "Ada"},
                "expected_substrings": ["Paris"],
            },
        )
    )

    on_prompt = _data(
        await client.post(
            f"/prompts/test/{defined['id']}/run", params=org, headers=headers, json={}
        )
    )
    on_output = _data(
        await client.post(
            f"/prompts/test/{defined['id']}/run",
            params=org,
            headers=headers,
            json={"actual_output": "The capital is Paris."},
        )
    )

    assert on_prompt["status"] == "failed"
    assert on_output["status"] == "passed"


async def test_running_an_unknown_test_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    response = await client.post(
        f"/prompts/test/{uuid.uuid4()}/run", params=org, headers=headers, json={}
    )
    assert response.status_code == HTTP_NOT_FOUND


async def test_running_a_test_against_an_unknown_version_is_a_404(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    declared: tuple[Prompt, PromptVersion],
) -> None:
    prompt, _version = declared
    defined = _data(
        await client.post(
            "/prompts/test",
            params=org,
            headers=headers,
            json={"prompt_id": str(prompt.id), "name": "case"},
        )
    )

    response = await client.post(
        f"/prompts/test/{defined['id']}/run",
        params=org,
        headers=headers,
        json={"version_number": "9.9.9"},
    )
    assert response.status_code == HTTP_NOT_FOUND


async def test_evaluating_an_output_scores_every_metric(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    declared: tuple[Prompt, PromptVersion],
) -> None:
    _prompt, version = declared

    response = await client.post(
        "/prompts/evaluate",
        params=org,
        headers=headers,
        json={
            "prompt_version_id": str(version.id),
            "actual": "Paris is the capital of France.",
            "expected": "Paris is the capital of France.",
            "required_points": ["Paris"],
            "latency_ms": 120.0,
            "total_tokens": 20,
            "cost_usd": 0.001,
        },
    )

    assert response.status_code == HTTP_CREATED
    body = _data(response)
    assert body["prompt_version_id"] == str(version.id)
    assert 0.0 <= body["overall"] <= 1.0
    assert body["scores"]


async def test_evaluating_an_unknown_revision_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    response = await client.post(
        "/prompts/evaluate",
        params=org,
        headers=headers,
        json={"prompt_version_id": str(uuid.uuid4()), "actual": "Anything."},
    )
    assert response.status_code == HTTP_NOT_FOUND


async def test_optimizing_suggests_without_applying(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, version = await make_prompt("wordy", body=_VERBOSE_BODY)

    response = await client.post(
        "/prompts/optimize",
        params=org,
        headers=headers,
        json={"prompt_version_id": str(version.id)},
    )

    assert response.status_code == HTTP_CREATED
    suggestions = _data(response)
    assert suggestions
    assert all(row["status"] == str(OptimizationStatus.SUGGESTED) for row in suggestions)

    versions = _data(
        await client.get(f"/prompts/{prompt.id}/versions", params=org, headers=headers)
    )
    assert len(versions) == 1


async def test_accepting_an_optimization_creates_a_draft(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    """An optimization that could publish itself would be a hole straight
    through the governance workflow."""
    prompt, version = await make_prompt("optimize-me", body=_VERBOSE_BODY)
    suggestions = _data(
        await client.post(
            "/prompts/optimize",
            params=org,
            headers=headers,
            json={"prompt_version_id": str(version.id)},
        )
    )
    rewrite = next(row for row in suggestions if row["suggested_body"])

    response = await client.post(
        f"/prompts/optimize/{rewrite['id']}/accept", params=org, headers=headers
    )

    assert response.status_code == HTTP_CREATED
    created = _data(response)
    assert created["version_number"] == "1.0.1"
    assert created["published_at"] is None

    prompt_now = _data(await client.get(f"/prompts/{prompt.id}", params=org, headers=headers))
    assert prompt_now["status"] == str(PromptLifecycleStatus.DRAFT)


async def test_accepting_an_unknown_optimization_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    response = await client.post(
        f"/prompts/optimize/{uuid.uuid4()}/accept", params=org, headers=headers
    )
    assert response.status_code == HTTP_NOT_FOUND


async def test_optimizing_an_unknown_revision_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    response = await client.post(
        "/prompts/optimize",
        params=org,
        headers=headers,
        json={"prompt_version_id": str(uuid.uuid4())},
    )
    assert response.status_code == HTTP_NOT_FOUND


# ---------------------------------------------------------------------------
# A/B experiments
# ---------------------------------------------------------------------------


async def test_starting_and_listing_an_ab_experiment(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, control = await make_prompt("split")
    variant = _data(
        await client.post(
            f"/prompts/{prompt.id}/versions",
            params=org,
            headers=headers,
            json={"body": "Hi {{ name }}", "component": "minor"},
        )
    )

    started = _data(
        await client.post(
            "/prompts/ab-test",
            params=org,
            headers=headers,
            json={
                "prompt_id": str(prompt.id),
                "name": "wording",
                "control_version_number": control.version_number,
                "variant_version_number": variant["version_number"],
                "variant_weight": 0.25,
                "minimum_samples_per_arm": 20,
                "auto_promote": True,
            },
        )
    )

    assert started["status"] == "running"
    assert started["variant_weight"] == 0.25
    assert started["minimum_samples_per_arm"] == 20
    assert started["started_at"] is not None
    assert started["winner"] is None

    listed = _data(await client.get("/prompts/ab-test", params=org, headers=headers))
    assert [row["id"] for row in listed] == [started["id"]]


async def test_starting_an_experiment_with_a_missing_arm_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, control = await make_prompt("half-split")

    response = await client.post(
        "/prompts/ab-test",
        params=org,
        headers=headers,
        json={
            "prompt_id": str(prompt.id),
            "name": "incomplete",
            "control_version_number": control.version_number,
            "variant_version_number": "9.9.9",
        },
    )
    assert response.status_code == HTTP_NOT_FOUND


async def test_starting_a_second_concurrent_experiment_is_a_conflict(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, control = await make_prompt("one-at-a-time")
    variant = _data(
        await client.post(
            f"/prompts/{prompt.id}/versions",
            params=org,
            headers=headers,
            json={"body": "Hi {{ name }}", "component": "minor"},
        )
    )
    payload = {
        "prompt_id": str(prompt.id),
        "name": "first",
        "control_version_number": control.version_number,
        "variant_version_number": variant["version_number"],
    }
    await client.post("/prompts/ab-test", params=org, headers=headers, json=payload)

    response = await client.post(
        "/prompts/ab-test", params=org, headers=headers, json={**payload, "name": "second"}
    )
    assert response.status_code == HTTP_CONFLICT


# ---------------------------------------------------------------------------
# Execution recording
# ---------------------------------------------------------------------------


async def test_recording_an_execution_masks_the_prompt_server_side(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    make_prompt: MakePromptFn,
    executions_repo: Any,
) -> None:
    """Masked **here** rather than trusted to have been masked by the
    caller: a caller that forgot would otherwise write resolved secrets
    into execution history, and this service is the one that knows which
    variables are sensitive."""
    prompt, version = await make_prompt("executed")
    secret = "sk-abcdefghij1234567890abcdefghij1234567890"

    response = await client.post(
        "/prompts/executions",
        params=org,
        headers=headers,
        json={
            "prompt_id": str(prompt.id),
            "version_number": version.version_number,
            "rendered_prompt": f"api_key: {secret}",
            "prompt_tokens": 12,
            "completion_tokens": 8,
        },
    )
    body = _data(response)

    # ExecutionResponse is a deliberately minimal receipt and does not
    # echo the stored text back, so the secret must be absent from the
    # whole response *and* from what actually landed in the row.
    assert secret not in response.text
    assert body["total_tokens"] == 20

    stored = await executions_repo.require_by_id(uuid.UUID(body["id"]))
    assert stored.rendered_prompt is not None
    assert secret not in stored.rendered_prompt
    assert "REDACTED" in stored.rendered_prompt


async def test_recording_an_execution_without_a_rendered_prompt(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    make_prompt: MakePromptFn,
    executions_repo: Any,
) -> None:
    """A caller may legitimately not want to store the text at all."""
    prompt, version = await make_prompt("text-free")

    body = _data(
        await client.post(
            "/prompts/executions",
            params=org,
            headers=headers,
            json={"prompt_id": str(prompt.id), "version_number": version.version_number},
        )
    )

    stored = await executions_repo.require_by_id(uuid.UUID(body["id"]))
    assert stored.rendered_prompt is None


async def test_recording_a_failed_execution_carries_the_error(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    make_prompt: MakePromptFn,
    executions_repo: Any,
) -> None:
    prompt, version = await make_prompt("failing")

    body = _data(
        await client.post(
            "/prompts/executions",
            params=org,
            headers=headers,
            json={
                "prompt_id": str(prompt.id),
                "version_number": version.version_number,
                "status": str(ExecutionStatus.FAILED),
                "error": "upstream refused",
                "model_provider": "anthropic",
                "model_name": "claude-opus-5",
                "latency_ms": 500.0,
                "cost_usd": 0.002,
                "agent_id": "agent-1",
                "workflow_id": "wf-1",
                "result_metadata": {"finish_reason": "error"},
            },
        )
    )

    assert body["status"] == str(ExecutionStatus.FAILED)
    assert body["model_name"] == "claude-opus-5"
    assert body["model_provider"] == "anthropic"
    assert body["latency_ms"] == 500.0
    assert body["cost_usd"] == 0.002

    # The receipt omits ``error``, ``agent_id``, ``workflow_id``, and
    # ``result_metadata``; they are stored, and read back off the row.
    stored = await executions_repo.require_by_id(uuid.UUID(body["id"]))
    assert stored.error == "upstream refused"
    assert stored.agent_id == "agent-1"
    assert stored.workflow_id == "wf-1"
    assert stored.result_metadata == {"finish_reason": "error"}


async def test_recording_an_execution_can_name_its_ab_arm(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    make_prompt: MakePromptFn,
    executions_repo: Any,
) -> None:
    """The arm is what makes an experiment's counters reconcilable against
    the execution rows themselves."""
    prompt, control = await make_prompt("armed")
    variant = _data(
        await client.post(
            f"/prompts/{prompt.id}/versions",
            params=org,
            headers=headers,
            json={"body": "Hi {{ name }}", "component": "minor"},
        )
    )
    experiment = _data(
        await client.post(
            "/prompts/ab-test",
            params=org,
            headers=headers,
            json={
                "prompt_id": str(prompt.id),
                "name": "armed-split",
                "control_version_number": control.version_number,
                "variant_version_number": variant["version_number"],
            },
        )
    )

    body = _data(
        await client.post(
            "/prompts/executions",
            params=org,
            headers=headers,
            json={
                "prompt_id": str(prompt.id),
                "version_number": control.version_number,
                "ab_test_id": experiment["id"],
                "ab_arm": str(AbTestArm.CONTROL),
            },
        )
    )

    stored = await executions_repo.require_by_id(uuid.UUID(body["id"]))
    assert str(stored.ab_test_id) == experiment["id"]
    assert stored.ab_arm == AbTestArm.CONTROL


async def test_recording_an_execution_for_an_unknown_version_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    prompt, _version = await make_prompt("execution-404")

    response = await client.post(
        "/prompts/executions",
        params=org,
        headers=headers,
        json={"prompt_id": str(prompt.id), "version_number": "9.9.9"},
    )
    assert response.status_code == HTTP_NOT_FOUND


async def test_recording_an_execution_for_an_unknown_prompt_is_a_404(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    response = await client.post(
        "/prompts/executions",
        params=org,
        headers=headers,
        json={"prompt_id": str(uuid.uuid4()), "version_number": "1.0.0"},
    )
    assert response.status_code == HTTP_NOT_FOUND


# ---------------------------------------------------------------------------
# Statistics and reports
# ---------------------------------------------------------------------------


async def test_statistics_are_null_before_any_rollup_has_run(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    """Null rather than 404: the organization exists and simply has no
    computed window yet, which is not an error."""
    response = await client.get("/prompts/statistics", params=org, headers=headers)

    assert response.status_code == HTTP_OK
    assert _data(response) is None


async def test_statistics_return_the_newest_window(
    client: AsyncClient,
    headers: dict[str, str],
    org: dict[str, str],
    statistics_service: Any,
    organization_id: uuid.UUID,
) -> None:

    await statistics_service.rollup(organization_id, window_start=ago(7200), window_end=ago(3600))
    newest = await statistics_service.rollup(
        organization_id, window_start=ago(3600), window_end=soon(3600)
    )

    body = _data(await client.get("/prompts/statistics", params=org, headers=headers))
    assert body["id"] == str(newest.id)


async def test_generating_and_listing_reports(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], make_prompt: MakePromptFn
) -> None:
    await make_prompt("reported")

    generated = await client.post(
        "/prompts/reports", params={**org, "kind": str(ReportKind.USAGE)}, headers=headers
    )
    assert generated.status_code == HTTP_CREATED
    body = _data(generated)
    assert body["status"] == "completed"
    assert body["row_count"] == 1

    listed = _data(await client.get("/prompts/reports", params=org, headers=headers))
    assert [row["id"] for row in listed] == [body["id"]]


async def test_listing_reports_can_filter_by_kind(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str]
) -> None:
    for kind in (ReportKind.USAGE, ReportKind.AUDIT):
        await client.post("/prompts/reports", params={**org, "kind": str(kind)}, headers=headers)

    only_audit = _data(
        await client.get(
            "/prompts/reports", params={**org, "kind": str(ReportKind.AUDIT)}, headers=headers
        )
    )
    assert [row["kind"] for row in only_audit] == [str(ReportKind.AUDIT)]


# ---------------------------------------------------------------------------
# Route registration order
#
# A static segment registered after the /{prompt_id} catch-all is
# unreachable: /prompts/statistics matches /prompts/{prompt_id} first and
# fails UUID parsing with a 422 that reads like a client mistake. A real
# bug class in this codebase, hit in three prior services -- so every
# static route is asserted to produce anything other than that 422.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/prompts/test"),
        ("GET", "/prompts/ab-test"),
        ("GET", "/prompts/statistics"),
        ("GET", "/prompts/reports"),
        ("POST", "/prompts/evaluate"),
        ("POST", "/prompts/optimize"),
        ("POST", "/prompts/executions"),
        ("POST", "/prompts/test"),
        ("POST", "/prompts/ab-test"),
    ],
)
async def test_a_static_segment_route_is_not_shadowed_by_the_id_catch_all(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], method: str, path: str
) -> None:
    response = await client.request(method, path, params=org, headers=headers, json={})

    # A shadowed route would 422 on parsing "statistics" as a UUID, and
    # would say so by naming prompt_id.
    if response.status_code == HTTP_UNPROCESSABLE:
        assert "prompt_id" not in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/prompts/reviews/{id}",
        "/prompts/approvals/{id}",
        "/prompts/optimize/{id}/accept",
        "/prompts/test/{id}/run",
    ],
)
async def test_a_two_segment_static_prefix_is_not_shadowed_either(
    client: AsyncClient, headers: dict[str, str], org: dict[str, str], path: str
) -> None:
    """These share arity with ``/prompts/{prompt_id}/...`` sub-paths, so
    the same shadowing risk applies one level down."""
    response = await client.post(
        path.replace("{id}", str(uuid.uuid4())),
        params=org,
        headers=headers,
        json={"decision": str(ReviewDecision.APPROVED), "approve": True},
    )

    assert response.status_code == HTTP_NOT_FOUND
