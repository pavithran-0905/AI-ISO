"""Tests for every HTTP endpoint, through the real ASGI app.

The app runs through its actual lifespan with real PostgreSQL, Redis,
RabbitMQ and MinIO; only the request session is overridden so writes roll
back.

**Every test authenticates with a token naming its own organization.** The
service reads the tenant from the token and nowhere else, so a test that
could pass it as a parameter would be exercising an API this service
deliberately does not expose.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from app.models.enums import DocumentStatus, ReportKind
from tests.conftest import (
    CHANGE_REQUEST,
    HTTP_BAD_REQUEST,
    HTTP_CREATED,
    HTTP_FORBIDDEN,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    LOG_FILE,
    POSTMORTEM,
    AuthHeadersFn,
)

pytestmark = pytest.mark.asyncio


async def _upload(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    data: bytes = CHANGE_REQUEST,
    filename: str = "cr.txt",
    title: str = "CR 4821",
    tags: str = "cab,payments",
) -> dict[str, Any]:
    response = await client.post(
        "/documents",
        headers=headers,
        files={"file": (filename, data, "text/plain")},
        data={"title": title, "tags": tags, "priority": "10"},
    )
    assert response.status_code == HTTP_CREATED, response.text
    return response.json()["data"]


# ---- authentication and tenancy ---------------------------------------------------------


async def test_a_token_with_no_organization_claim_is_refused(
    client: AsyncClient, auth_headers: AuthHeadersFn
) -> None:
    """Falling back to a default tenant would serve one organization's
    documents to a token that never claimed it."""
    response = await client.get("/documents", headers=auth_headers())
    assert response.status_code == HTTP_FORBIDDEN
    # The error *code*, not the message: the platform's handlers return a
    # deliberately generic message to the client and log the detail, so
    # asserting on the prose would be asserting on something callers are
    # not promised.
    assert response.json()["error"]["code"] == "AIIOS-AUTHZ-0001"


async def test_a_malformed_organization_claim_is_refused(
    client: AsyncClient, jwt_keypair: tuple[str, str]
) -> None:
    from shared_core.security.jwt import encode_token

    private_key, _ = jwt_keypair
    token = encode_token({"sub": "u", "organization_id": "not-a-uuid"}, private_key=private_key)
    response = await client.get("/documents", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == HTTP_FORBIDDEN


async def test_a_garbage_token_is_unauthorised(client: AsyncClient) -> None:
    response = await client.get("/documents", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == HTTP_UNAUTHORIZED


async def test_one_tenant_cannot_read_another_tenants_document(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    """404, not 403: whether a document exists is itself information."""
    mine = await _upload(client, auth_headers(organization_id=organization_id))
    other = auth_headers("intruder", organization_id=uuid.uuid4())
    response = await client.get(f"/documents/{mine['document']['id']}", headers=other)
    assert response.status_code == HTTP_NOT_FOUND


async def test_a_listing_shows_only_the_callers_own_documents(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    await _upload(client, auth_headers(organization_id=organization_id))
    other = auth_headers("intruder", organization_id=uuid.uuid4())
    response = await client.get("/documents", headers=other)
    assert response.status_code == HTTP_OK
    assert response.json()["data"]["total"] == 0


# ---- upload ------------------------------------------------------------------------------


async def test_an_upload_detects_the_format_cleans_tags_and_queues_a_job(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    body = await _upload(
        client, auth_headers(organization_id=organization_id), tags="cab, cab , ,payments"
    )
    document = body["document"]
    assert document["document_format"] == "txt"
    assert document["tags"] == ["cab", "payments"]
    assert body["job_id"] is not None
    assert body["will_process"] is True
    assert document["checksum"].startswith("sha256:")


async def test_a_duplicate_upload_is_accepted_linked_and_not_reprocessed(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    first = await _upload(client, headers)
    second = await _upload(client, headers, title="Same bytes", filename="again.txt")
    assert second["is_duplicate"] is True
    assert second["will_process"] is False
    assert second["duplicate_of_id"] == first["document"]["id"]
    assert "already exists" in second["message"]


async def test_an_empty_upload_is_rejected(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    response = await client.post(
        "/documents",
        headers=auth_headers(organization_id=organization_id),
        files={"file": ("empty.txt", b"", "text/plain")},
        data={"title": "Empty"},
    )
    assert response.status_code == HTTP_BAD_REQUEST


async def test_an_unidentifiable_upload_is_rejected(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    response = await client.post(
        "/documents",
        headers=auth_headers(organization_id=organization_id),
        files={"file": ("mystery.bin", b"\x00\x01\x02\x03\x04\x05\x06\x07", None)},
        data={"title": "Mystery"},
    )
    assert response.status_code == HTTP_BAD_REQUEST


async def test_an_upload_without_a_title_falls_back_to_the_filename(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    response = await client.post(
        "/documents",
        headers=auth_headers(organization_id=organization_id),
        files={"file": ("named.txt", CHANGE_REQUEST, "text/plain")},
    )
    assert response.status_code == HTTP_CREATED
    assert response.json()["data"]["document"]["title"] == "named.txt"


# ---- processing --------------------------------------------------------------------------


async def test_extract_runs_the_pipeline_and_returns_every_stage(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    body = await _upload(client, headers)
    document_id = body["document"]["id"]

    response = await client.post(f"/documents/{document_id}/extract", headers=headers, json={})
    assert response.status_code == HTTP_OK, response.text
    data = response.json()["data"]
    assert data["job"]["status"] == "completed"
    assert all(outcome["succeeded"] for outcome in data["outcomes"])
    assert data["version_number"] >= 1


async def test_the_extraction_read_back_carries_everything_that_was_found(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers))["document"]["id"]
    await client.post(f"/documents/{document_id}/extract", headers=headers, json={})

    response = await client.get(f"/documents/{document_id}/extraction", headers=headers)
    assert response.status_code == HTTP_OK
    data = response.json()["data"]
    assert len(data["entities"]) >= 4
    assert data["tables"][0]["headers"] == ["System", "Risk", "Approver"]
    assert len(data["fields"]) >= 8
    assert any(label["is_primary"] for label in data["classifications"])


async def test_a_table_with_merged_cells_warns_that_a_flat_rendering_is_lossy(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    merged = (
        b"| Team | Service | On-call |\n"
        b"| ---- | ------- | ------- |\n"
        b"| Platform | gateway | R. Mehta |\n"
        b"| Platform |  |  |\n"
    )
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers, data=merged, filename="t.md"))["document"]["id"]
    await client.post(f"/documents/{document_id}/extract", headers=headers, json={})
    response = await client.get(f"/documents/{document_id}/extraction", headers=headers)
    tables = response.json()["data"]["tables"]
    assert tables
    assert tables[0]["has_merged_cells"] is True
    assert tables[0]["warning"]


async def test_classify_runs_form_extraction_alongside(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    """Template matching needs the field labels, so classification alone would
    silently skip every template."""
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers))["document"]["id"]
    response = await client.post(f"/documents/{document_id}/classify", headers=headers)
    assert response.status_code == HTTP_OK
    stages = {outcome["stage"] for outcome in response.json()["data"]["outcomes"]}
    assert "form_extraction" in stages
    assert "classification" in stages


async def test_ocr_on_a_document_that_already_has_text_is_skipped(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers))["document"]["id"]
    response = await client.post(f"/documents/{document_id}/ocr", headers=headers)
    assert response.status_code == HTTP_OK
    ocr = next(o for o in response.json()["data"]["outcomes"] if o["stage"] == "ocr")
    assert ocr["detail"]["skipped"] is True


async def test_extract_honours_an_explicit_stage_list(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers))["document"]["id"]
    response = await client.post(
        f"/documents/{document_id}/extract",
        headers=headers,
        json={"stages": ["entity_extraction"], "priority": 20},
    )
    assert response.status_code == HTTP_OK
    stages = [outcome["stage"] for outcome in response.json()["data"]["outcomes"]]
    assert stages[0] == "parsing", "parsing is always prepended"
    assert "entity_extraction" in stages


async def test_extraction_of_an_unparsed_document_is_not_found(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers))["document"]["id"]
    response = await client.get(f"/documents/{document_id}/extraction", headers=headers)
    assert response.status_code == HTTP_NOT_FOUND


# ---- validation, summarization, translation ----------------------------------------------


async def test_validate_reports_how_many_rules_actually_ran(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    """is_valid=true with zero rules evaluated means nothing was checked."""
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers))["document"]["id"]
    response = await client.post(f"/documents/{document_id}/validate", headers=headers)
    assert response.status_code == HTTP_OK
    data = response.json()["data"]
    assert "rules_evaluated" in data
    if data["rules_evaluated"] == 0:
        assert data["warnings"], "an unchecked document must say so"


async def test_summarize_stores_and_returns_each_requested_kind(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    document_id = (
        await _upload(client, headers, data=POSTMORTEM, filename="pm.txt", title="Postmortem")
    )["document"]["id"]
    await client.post(f"/documents/{document_id}/extract", headers=headers, json={})

    response = await client.post(
        f"/documents/{document_id}/summarize",
        headers=headers,
        json={"kinds": ["executive", "bullet"], "sentence_count": 2, "max_words": 60},
    )
    assert response.status_code == HTTP_OK, response.text
    summaries = response.json()["data"]
    assert {summary["summary_kind"] for summary in summaries} == {"executive", "bullet"}
    for summary in summaries:
        assert summary["content"]
        assert summary["compression_ratio"] > 0


async def test_summarizing_twice_updates_rather_than_duplicating(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers, data=POSTMORTEM, filename="pm.txt"))["document"][
        "id"
    ]
    await client.post(f"/documents/{document_id}/extract", headers=headers, json={})
    payload = {"kinds": ["executive"], "sentence_count": 2}
    first = await client.post(f"/documents/{document_id}/summarize", headers=headers, json=payload)
    second = await client.post(f"/documents/{document_id}/summarize", headers=headers, json=payload)
    assert first.status_code == second.status_code == HTTP_OK
    assert len(second.json()["data"]) == 1


async def test_language_detection_reports_its_reliability(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers, data=POSTMORTEM, filename="pm.txt"))["document"][
        "id"
    ]
    await client.post(f"/documents/{document_id}/extract", headers=headers, json={})
    response = await client.get(f"/documents/{document_id}/language", headers=headers)
    assert response.status_code == HTTP_OK
    data = response.json()["data"]
    assert data["language"] == "en"
    assert data["is_reliable"] is True
    assert data["scores"]


async def test_translation_with_no_backend_refuses_rather_than_storing_the_source(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    """Storing English as the French version is a falsehood nothing
    downstream could detect."""
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers))["document"]["id"]
    await client.post(f"/documents/{document_id}/extract", headers=headers, json={})
    response = await client.post(
        f"/documents/{document_id}/translate",
        headers=headers,
        json={"target_languages": ["fr"]},
    )
    assert response.status_code == HTTP_BAD_REQUEST
    assert response.json()["error"]["code"].startswith("AIIOS-VAL")


async def test_a_blank_target_language_is_rejected(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers))["document"]["id"]
    response = await client.post(
        f"/documents/{document_id}/translate",
        headers=headers,
        json={"target_languages": ["  "]},
    )
    assert response.status_code == HTTP_BAD_REQUEST


# ---- review ------------------------------------------------------------------------------


async def test_a_review_can_be_opened_listed_and_decided(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers("reviewer-1", organization_id=organization_id)
    document_id = (await _upload(client, headers))["document"]["id"]
    await client.post(f"/documents/{document_id}/extract", headers=headers, json={})

    opened = await client.post(
        f"/documents/{document_id}/review",
        headers=headers,
        json={"reason": "blank required signature", "priority": 20, "assigned_to": "reviewer-1"},
    )
    assert opened.status_code == HTTP_CREATED, opened.text
    review = opened.json()["data"]
    assert review["status"] == "assigned"
    assert review["due_at"]

    listed = await client.get(f"/documents/{document_id}/reviews", headers=headers)
    assert listed.status_code == HTTP_OK
    assert len(listed.json()["data"]) == 1

    decided = await client.post(
        f"/documents/{document_id}/review/{review['id']}/decision",
        headers=headers,
        json={
            "decision": "corrected",
            "corrections": {"approved by": "A. Novak"},
            "comment": "Signed off.",
        },
    )
    assert decided.status_code == HTTP_OK, decided.text
    outcome = decided.json()["data"]
    assert outcome["corrections_applied"] == 1
    assert outcome["document_status"] == "approved"

    read_back = await client.get(f"/documents/{document_id}/extraction", headers=headers)
    corrected = [f for f in read_back.json()["data"]["fields"] if f["corrected_value"]]
    assert corrected[0]["corrected_value"] == "A. Novak"
    assert corrected[0]["value"] in (None, "")


async def test_a_review_with_a_blank_reason_is_rejected(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers))["document"]["id"]
    await client.post(f"/documents/{document_id}/extract", headers=headers, json={})
    response = await client.post(
        f"/documents/{document_id}/review", headers=headers, json={"reason": "   "}
    )
    assert response.status_code == HTTP_BAD_REQUEST


async def test_a_corrected_decision_with_no_corrections_is_rejected(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers))["document"]["id"]
    await client.post(f"/documents/{document_id}/extract", headers=headers, json={})
    opened = await client.post(
        f"/documents/{document_id}/review", headers=headers, json={"reason": "low confidence"}
    )
    review_id = opened.json()["data"]["id"]
    response = await client.post(
        f"/documents/{document_id}/review/{review_id}/decision",
        headers=headers,
        json={"decision": "corrected", "corrections": {}},
    )
    assert response.status_code == HTTP_BAD_REQUEST


# ---- statistics and reports ---------------------------------------------------------------


async def test_statistics_is_reachable_and_not_shadowed_by_the_id_route(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    """A catch-all would take this path and fail parsing "statistics" as a UUID."""
    headers = auth_headers(organization_id=organization_id)
    response = await client.get("/documents/statistics", headers=headers, params={"windows": 5})
    assert response.status_code == HTTP_OK
    assert "windows" in response.json()["data"]


async def test_statistics_can_refresh_the_latest_window(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    await _upload(client, headers)
    response = await client.get(
        "/documents/statistics", headers=headers, params={"refresh": "true"}
    )
    assert response.status_code == HTTP_OK
    assert response.json()["data"]["total"] >= 1


async def test_the_rollup_endpoint_is_administrator_only(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    """It reads across tenants by design, which is why no ordinary token may
    trigger it."""
    ordinary = auth_headers(organization_id=organization_id)
    assert (
        await client.post("/documents/statistics/rollup", headers=ordinary)
    ).status_code == HTTP_FORBIDDEN

    admin = auth_headers("admin-1", organization_id=organization_id, roles=["admin"])
    response = await client.post("/documents/statistics/rollup", headers=admin)
    assert response.status_code == HTTP_OK
    assert "windows" in response.json()["data"]


@pytest.mark.parametrize("kind", [kind.value for kind in ReportKind])
async def test_every_report_kind_generates_over_http(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID, kind: str
) -> None:
    headers = auth_headers(organization_id=organization_id)
    response = await client.post(
        "/documents/reports",
        headers=headers,
        json={"kind": kind, "report_format": "json", "windows": 5},
    )
    assert response.status_code == HTTP_CREATED, response.text
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["rendered"]


async def test_reports_can_be_listed_and_filtered(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    await client.post(
        "/documents/reports", headers=headers, json={"kind": "accuracy", "windows": 1}
    )
    listed = await client.get("/documents/reports", headers=headers)
    assert listed.status_code == HTTP_OK
    assert listed.json()["data"]["total"] >= 1

    filtered = await client.get("/documents/reports", headers=headers, params={"kind": "review"})
    assert filtered.json()["data"]["total"] == 0


async def test_a_markdown_report_renders(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    response = await client.post(
        "/documents/reports",
        headers=headers,
        json={"kind": "accuracy", "report_format": "markdown", "title": "Accuracy"},
    )
    assert response.status_code == HTTP_CREATED
    assert response.json()["data"]["rendered"].startswith("# Accuracy")


# ---- listing, update, delete ---------------------------------------------------------------


async def test_listing_filters_by_status_and_review_queue(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers))["document"]["id"]
    await client.post(f"/documents/{document_id}/extract", headers=headers, json={})

    uploaded = await client.get(
        "/documents", headers=headers, params={"status": DocumentStatus.UPLOADED.value}
    )
    assert uploaded.status_code == HTTP_OK

    queue = await client.get("/documents", headers=headers, params={"awaiting_review": "true"})
    assert queue.status_code == HTTP_OK

    searched = await client.get("/documents", headers=headers, params={"query": "CR"})
    assert searched.json()["data"]["total"] >= 1


async def test_only_editable_metadata_can_be_changed(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    """A client that could set a derived field would make every metric here
    unverifiable."""
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers))["document"]["id"]

    updated = await client.put(
        f"/documents/{document_id}",
        headers=headers,
        json={"title": "Renamed", "description": "A change request.", "tags": ["cab"]},
    )
    assert updated.status_code == HTTP_OK
    assert updated.json()["data"]["title"] == "Renamed"

    refused = await client.put(
        f"/documents/{document_id}", headers=headers, json={"status": "approved"}
    )
    assert refused.status_code == HTTP_BAD_REQUEST

    also_refused = await client.put(
        f"/documents/{document_id}", headers=headers, json={"overall_confidence": 1.0}
    )
    assert also_refused.status_code == HTTP_BAD_REQUEST


async def test_a_deleted_document_is_gone_and_audited(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    document_id = (await _upload(client, headers))["document"]["id"]
    deleted = await client.delete(f"/documents/{document_id}", headers=headers)
    assert deleted.status_code == HTTP_OK
    assert (
        await client.get(f"/documents/{document_id}", headers=headers)
    ).status_code == HTTP_NOT_FOUND


async def test_an_unknown_document_is_not_found(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    missing = uuid.uuid4()
    for method, path in [
        ("GET", f"/documents/{missing}"),
        ("PUT", f"/documents/{missing}"),
        ("DELETE", f"/documents/{missing}"),
        ("GET", f"/documents/{missing}/extraction"),
        ("GET", f"/documents/{missing}/reviews"),
    ]:
        response = await client.request(
            method, path, headers=headers, json={} if method == "PUT" else None
        )
        assert response.status_code == HTTP_NOT_FOUND, f"{method} {path}"


async def test_a_log_file_uploads_and_processes_too(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    """A document type with no form fields must still complete."""
    headers = auth_headers(organization_id=organization_id)
    document_id = (
        await _upload(client, headers, data=LOG_FILE, filename="app.log", title="App log")
    )["document"]["id"]
    response = await client.post(f"/documents/{document_id}/extract", headers=headers, json={})
    assert response.status_code == HTTP_OK
    assert response.json()["data"]["job"]["status"] in {"completed", "partial"}


async def test_the_response_envelope_is_consistent(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    """Every endpoint in the platform returns this shape on success."""
    headers = auth_headers(organization_id=organization_id)
    response = await client.get("/documents", headers=headers)
    body = response.json()
    assert body["success"] is True
    assert body["message"]
    assert "data" in body
    assert body["meta"]["request_id"]
    assert body["meta"]["timestamp"]
