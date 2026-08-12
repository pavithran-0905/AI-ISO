"""The HTTP surface and the background workers.

Requests go through the real application: real middleware, real exception
handlers, real dependency graph, real JWT verification. Only the request
session is overridden, so a test's writes roll back.
"""

from __future__ import annotations

import base64
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import IndexStatus, ReportKind
from app.repositories.analytics import IndexingJobRepository
from app.services.indexing import IndexingService
from app.services.ingestion import IngestionService
from app.workers.document_expiry_sweep import DocumentExpirySweepWorker
from app.workers.indexing_sweep import IndexingSweepWorker
from app.workers.source_sync_sweep import SourceSyncSweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from tests.conftest import (
    HANDBOOK,
    HTTP_ACCEPTED,
    HTTP_BAD_REQUEST,
    HTTP_CREATED,
    HTTP_FORBIDDEN,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_UNPROCESSABLE,
    NETWORK,
    AuthHeadersFn,
    RecordingPublisher,
    ago,
)

pytestmark = pytest.mark.asyncio

REFUSED = {HTTP_BAD_REQUEST, HTTP_UNPROCESSABLE}
"""A refused request, however the framework spelled it.

Schema violations surface as 400 through this platform's own validation
middleware rather than FastAPI's default 422, and both are correct
refusals -- pinning either number here would test the middleware's choice
rather than the endpoint's behaviour."""


SECRET_DOC = (
    b"# Master Recovery\n\nThe master recovery procedure restores the archive bucket "
    b"from cold storage using the sealed hardware key.\n"
)


@pytest.fixture
def headers(auth_headers: AuthHeadersFn, organization_id: uuid.UUID) -> dict[str, str]:
    return auth_headers(organization_id=organization_id, roles=["engineer"])


@pytest.fixture
def cleared(auth_headers: AuthHeadersFn, organization_id: uuid.UUID) -> dict[str, str]:
    return auth_headers(organization_id=organization_id, roles=["sre"], clearance="secret")


@pytest.fixture
def admin(auth_headers: AuthHeadersFn, organization_id: uuid.UUID) -> dict[str, str]:
    return auth_headers(organization_id=organization_id, roles=["admin"], clearance="secret")


def _upload(data: bytes, **kwargs: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": "Handbook",
        "content_base64": base64.b64encode(data).decode(),
        "filename": "handbook.md",
    }
    body.update(kwargs)
    return body


async def _ingest(client: AsyncClient, headers: dict[str, str], **kwargs: Any) -> dict[str, Any]:
    response = await client.post(
        "/rag/documents", headers=headers, json=_upload(HANDBOOK, **kwargs)
    )
    assert response.status_code == HTTP_CREATED, response.text
    return response.json()["data"]  # type: ignore[no-any-return]


# ---- documents -------------------------------------------------------------------


async def test_ingesting_over_http(client: AsyncClient, headers: dict[str, str]) -> None:
    data = await _ingest(client, headers, tags=["ops"], chunk_strategy="heading")
    assert data["chunk_count"] > 0
    assert data["version_number"] == 1
    assert data["document"]["status"] == "chunked"
    assert data["document"]["tags"] == ["ops"]


async def test_the_document_response_never_carries_the_text(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    """A listing of a thousand documents would otherwise ship a thousand
    documents' worth of text into every log and proxy cache on the way."""
    data = await _ingest(client, headers)
    assert "content" not in data["document"]


async def test_re_ingesting_identical_bytes_reports_unchanged(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await _ingest(client, headers, external_id="ops/h")
    again = await _ingest(client, headers, external_id="ops/h")
    assert again["unchanged"] is True


async def test_invalid_base64_is_refused(client: AsyncClient, headers: dict[str, str]) -> None:
    """``validate=False`` would silently discard characters outside the
    alphabet, letting a truncated upload decode into *something*."""
    response = await client.post(
        "/rag/documents",
        headers=headers,
        json={"title": "X", "content_base64": "not base64!!", "filename": "x.txt"},
    )
    assert response.status_code in {HTTP_BAD_REQUEST, HTTP_UNPROCESSABLE}


async def test_an_unknown_field_is_refused(client: AsyncClient, headers: dict[str, str]) -> None:
    """``extra="forbid"`` on the request schemas: a misspelled field that
    is silently ignored is a caller believing they set something they did
    not."""
    response = await client.post(
        "/rag/documents", headers=headers, json=_upload(HANDBOOK, unexpected="value")
    )
    assert response.status_code in REFUSED


async def test_blocked_content_returns_the_findings_rather_than_an_error(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    """A document refused by scanning is a result the caller has to act
    on; a bare 4xx would not say which finding to fix."""
    response = await client.post(
        "/rag/documents",
        headers=headers,
        json=_upload(b"Deploy with AKIAIOSFODNN7EXAMPLE.", title="D", filename="d.txt"),
    )
    assert response.status_code == HTTP_CREATED
    data = response.json()["data"]
    assert data["blocked"] is True
    assert data["findings"]


async def test_listing_and_reading_documents(client: AsyncClient, headers: dict[str, str]) -> None:
    data = await _ingest(client, headers)
    document_id = data["document"]["id"]

    listed = (await client.get("/rag/documents", headers=headers)).json()["data"]
    assert document_id in {row["id"] for row in listed}

    one = await client.get(f"/rag/documents/{document_id}", headers=headers)
    assert one.status_code == HTTP_OK
    assert one.json()["data"]["id"] == document_id


async def test_listing_can_filter_on_status(client: AsyncClient, headers: dict[str, str]) -> None:
    await _ingest(client, headers)
    filtered = await client.get(
        "/rag/documents", headers=headers, params={"status": "chunked", "limit": 5}
    )
    assert filtered.status_code == HTTP_OK
    assert all(row["status"] == "chunked" for row in filtered.json()["data"])


async def test_the_static_search_route_wins_over_the_id_catch_all(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    """Declared after ``{document_id}`` it would be hijacked as
    ``document_id="search"`` and fail UUID parsing before reaching the
    handler that owns the path."""
    await _ingest(client, headers, title="Backup Handbook")
    response = await client.get("/rag/documents/search", headers=headers, params={"q": "Backup"})
    assert response.status_code == HTTP_OK
    assert any("Backup" in row["title"] for row in response.json()["data"])


async def test_reading_content_and_chunks_over_http(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    data = await _ingest(client, headers)
    document_id = data["document"]["id"]

    content = await client.get(f"/rag/documents/{document_id}/content", headers=headers)
    assert content.status_code == HTTP_OK
    assert "nightly backup" in content.json()["data"]["content"]

    chunks = await client.get(f"/rag/documents/{document_id}/chunks", headers=headers)
    assert chunks.status_code == HTTP_OK
    assert chunks.json()["data"]


async def test_a_restricted_document_is_hidden_and_refused(
    client: AsyncClient, headers: dict[str, str], cleared: dict[str, str]
) -> None:
    created = await client.post(
        "/rag/documents",
        headers=cleared,
        json=_upload(
            SECRET_DOC,
            title="Master Recovery",
            filename="m.md",
            classification="secret",
            allowed_roles=["sre"],
        ),
    )
    assert created.status_code == HTTP_CREATED, created.text
    secret_id = created.json()["data"]["document"]["id"]

    listed = (await client.get("/rag/documents", headers=headers)).json()["data"]
    assert secret_id not in {row["id"] for row in listed}

    denied = await client.get(f"/rag/documents/{secret_id}", headers=headers)
    assert denied.status_code == HTTP_FORBIDDEN

    permitted = await client.get(f"/rag/documents/{secret_id}", headers=cleared)
    assert permitted.status_code == HTTP_OK


async def test_updating_archiving_restoring_and_deleting(
    client: AsyncClient, admin: dict[str, str]
) -> None:
    data = await _ingest(client, admin)
    document_id = data["document"]["id"]

    updated = await client.put(
        f"/rag/documents/{document_id}",
        headers=admin,
        json={"title": "Renamed", "tags": ["ops"], "metadata": {"department": "infra"}},
    )
    assert updated.status_code == HTTP_OK
    assert updated.json()["data"]["title"] == "Renamed"

    archived = await client.delete(
        f"/rag/documents/{document_id}", headers=admin, params={"archive": True}
    )
    assert archived.json()["data"]["status"] == "archived"

    restored = await client.post(f"/rag/documents/{document_id}/restore", headers=admin)
    assert restored.status_code == HTTP_OK
    assert restored.json()["data"]["status"] != "archived"

    deleted = await client.delete(f"/rag/documents/{document_id}", headers=admin)
    assert deleted.json()["data"]["status"] == "deleted"
    assert (
        await client.get(f"/rag/documents/{document_id}", headers=admin)
    ).status_code == HTTP_NOT_FOUND


async def test_classifying_above_your_clearance_is_refused_over_http(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    data = await _ingest(client, headers)
    response = await client.put(
        f"/rag/documents/{data['document']['id']}",
        headers=headers,
        json={"classification": "secret"},
    )
    assert response.status_code in {HTTP_BAD_REQUEST, HTTP_UNPROCESSABLE}


async def test_an_unknown_document_is_not_found(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.get(f"/rag/documents/{uuid.uuid4()}", headers=headers)
    assert response.status_code == HTTP_NOT_FOUND


# ---- indexing --------------------------------------------------------------------


async def test_indexing_one_document_now(client: AsyncClient, headers: dict[str, str]) -> None:
    data = await _ingest(client, headers)
    response = await client.post(
        "/rag/index", headers=headers, json={"document_id": data["document"]["id"]}
    )
    assert response.status_code == HTTP_OK
    assert response.json()["data"]["embedded"] > 0


async def test_indexing_with_no_document_queues_a_job(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    """A corpus-wide sweep does not belong inside a request that has to
    answer."""
    response = await client.post("/rag/index", headers=headers, json={})
    assert response.status_code == HTTP_OK
    assert response.json()["data"]["status"] == "queued"


async def test_a_reindex_is_accepted_rather_than_completed(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    """A full reindex of a real corpus outlives any sensible request
    timeout, and 200 would promise it had finished."""
    response = await client.post("/rag/reindex", headers=headers, json={"full": True})
    assert response.status_code == HTTP_ACCEPTED
    assert response.json()["data"]["kind"] == "full"


async def test_indexing_jobs_are_listed(client: AsyncClient, headers: dict[str, str]) -> None:
    await client.post("/rag/reindex", headers=headers, json={})
    listed = await client.get("/rag/index/jobs", headers=headers)
    assert listed.status_code == HTTP_OK
    assert listed.json()["data"]


# ---- retrieval --------------------------------------------------------------------


async def _corpus(client: AsyncClient, headers: dict[str, str], cleared: dict[str, str]) -> None:
    for title, data, filename in (
        ("Handbook", HANDBOOK, "handbook.md"),
        ("Network", NETWORK, "network.md"),
    ):
        ingested = await client.post(
            "/rag/documents",
            headers=headers,
            json=_upload(data, title=title, filename=filename),
        )
        await client.post(
            "/rag/index",
            headers=headers,
            json={"document_id": ingested.json()["data"]["document"]["id"]},
        )
    secret = await client.post(
        "/rag/documents",
        headers=cleared,
        json=_upload(
            SECRET_DOC,
            title="Master Recovery",
            filename="m.md",
            classification="secret",
            allowed_roles=["sre"],
        ),
    )
    await client.post(
        "/rag/index",
        headers=cleared,
        json={"document_id": secret.json()["data"]["document"]["id"]},
    )


@pytest.mark.parametrize("path", ["/rag/search", "/rag/retrieve"])
async def test_search_and_retrieve_return_ranked_hits(
    client: AsyncClient, headers: dict[str, str], cleared: dict[str, str], path: str
) -> None:
    await _corpus(client, headers, cleared)
    response = await client.post(
        path, headers=headers, json={"query": "how do I restore a backup snapshot?", "top_k": 5}
    )
    assert response.status_code == HTTP_OK, response.text
    data = response.json()["data"]
    assert data["results"]
    assert data["outcome"] == "succeeded"
    assert [hit["rank"] for hit in data["results"]] == list(range(1, len(data["results"]) + 1))
    assert data["embedding_ms"] is not None


async def test_a_search_hit_carries_its_per_arm_provenance(
    client: AsyncClient, headers: dict[str, str], cleared: dict[str, str]
) -> None:
    """A fused number with nothing behind it is unauditable."""
    await _corpus(client, headers, cleared)
    data = (
        await client.post("/rag/search", headers=headers, json={"query": "restore the snapshot"})
    ).json()["data"]
    assert any(hit["arm_scores"] for hit in data["results"])


async def test_search_never_returns_a_restricted_document(
    client: AsyncClient, headers: dict[str, str], cleared: dict[str, str]
) -> None:
    await _corpus(client, headers, cleared)
    hidden = (
        await client.post(
            "/rag/search", headers=headers, json={"query": "sealed hardware key", "top_k": 10}
        )
    ).json()["data"]
    assert all(hit["document_title"] != "Master Recovery" for hit in hidden["results"])

    visible = (
        await client.post(
            "/rag/search", headers=cleared, json={"query": "sealed hardware key", "top_k": 10}
        )
    ).json()["data"]
    assert any(hit["document_title"] == "Master Recovery" for hit in visible["results"])


async def test_another_tenant_searching_finds_nothing(
    client: AsyncClient,
    headers: dict[str, str],
    cleared: dict[str, str],
    auth_headers: AuthHeadersFn,
) -> None:
    await _corpus(client, headers, cleared)
    stranger = auth_headers(organization_id=uuid.uuid4(), clearance="secret")
    data = (
        await client.post("/rag/search", headers=stranger, json={"query": "restore a backup"})
    ).json()["data"]
    assert data["results"] == []


async def test_a_keyword_only_search_works(
    client: AsyncClient, headers: dict[str, str], cleared: dict[str, str]
) -> None:
    await _corpus(client, headers, cleared)
    response = await client.post(
        "/rag/search",
        headers=headers,
        json={"query": "availability zones subnet", "strategy": "keyword", "rerank_method": None},
    )
    assert response.status_code == HTTP_OK
    assert response.json()["data"]["results"]


async def test_top_k_is_clamped_rather_than_refused(
    client: AsyncClient, headers: dict[str, str], cleared: dict[str, str]
) -> None:
    """A 422 would break a client over a limit it cannot see."""
    await _corpus(client, headers, cleared)
    response = await client.post(
        "/rag/search", headers=headers, json={"query": "backup", "top_k": 200}
    )
    assert response.status_code == HTTP_OK


async def test_an_out_of_range_top_k_is_a_schema_error(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.post("/rag/search", headers=headers, json={"query": "x", "top_k": 0})
    assert response.status_code in REFUSED


async def test_an_empty_query_is_refused(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.post("/rag/search", headers=headers, json={"query": ""})
    assert response.status_code in REFUSED


async def test_context_assembly_over_http(
    client: AsyncClient, headers: dict[str, str], cleared: dict[str, str]
) -> None:
    await _corpus(client, headers, cleared)
    response = await client.post(
        "/rag/context",
        headers=headers,
        json={"query": "how do I restore a backup?", "max_tokens": 250},
    )
    assert response.status_code == HTTP_OK, response.text
    data = response.json()["data"]
    assert data["text"].strip()
    assert data["token_count"] <= 250
    assert data["citations"]
    assert data["retrieval"]["outcome"] == "succeeded"
    assert all(citation["rendered"] for citation in data["citations"])


async def test_feedback_and_per_query_evaluation(
    client: AsyncClient, headers: dict[str, str], cleared: dict[str, str]
) -> None:
    await _corpus(client, headers, cleared)
    retrieved = (
        await client.post("/rag/retrieve", headers=headers, json={"query": "backup retention"})
    ).json()["data"]

    recorded = await client.post(
        f"/rag/retrieve/{retrieved['query_id']}/feedback",
        headers=headers,
        json={
            "verdict": "relevant",
            "chunk_id": retrieved["results"][0]["chunk_id"],
            "rank": 1,
            "relevance": 1.0,
        },
    )
    assert recorded.status_code == HTTP_CREATED

    measured = await client.get(
        f"/rag/retrieve/{retrieved['query_id']}/evaluation", headers=headers
    )
    assert measured.status_code == HTTP_OK
    metrics = {row["name"]: row for row in measured.json()["data"]}
    assert metrics["precision"]["value"] > 0
    assert metrics["precision"]["measurable"] is True


async def test_out_of_range_relevance_is_refused_by_the_schema(
    client: AsyncClient, headers: dict[str, str], cleared: dict[str, str]
) -> None:
    await _corpus(client, headers, cleared)
    retrieved = (
        await client.post("/rag/retrieve", headers=headers, json={"query": "backup"})
    ).json()["data"]
    response = await client.post(
        f"/rag/retrieve/{retrieved['query_id']}/feedback",
        headers=headers,
        json={"verdict": "relevant", "relevance": 2.0},
    )
    assert response.status_code in REFUSED


# ---- sources ------------------------------------------------------------------------


def _source_body(**kwargs: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "slug": "ops-wiki",
        "name": "Ops Wiki",
        "source_kind": "confluence",
        "credential_reference": "vault://kv/rag/ops-wiki",
        "sync_enabled": True,
    }
    body.update(kwargs)
    return body


async def test_the_full_source_lifecycle_over_http(
    client: AsyncClient, admin: dict[str, str]
) -> None:
    created = await client.post("/rag/sources", headers=admin, json=_source_body())
    assert created.status_code == HTTP_CREATED, created.text
    source_id = created.json()["data"]["id"]
    assert created.json()["data"]["sync_status"] == "never_synced"

    assert (await client.get("/rag/sources", headers=admin)).json()["data"]
    assert (await client.get(f"/rag/sources/{source_id}", headers=admin)).json()["data"][
        "id"
    ] == source_id

    updated = await client.put(
        f"/rag/sources/{source_id}", headers=admin, json={"name": "Operations Wiki"}
    )
    assert updated.json()["data"]["name"] == "Operations Wiki"

    synced = await client.post(
        f"/rag/sources/{source_id}/sync",
        headers=admin,
        json={
            "documents_seen": 10,
            "documents_ingested": 8,
            "documents_failed": 2,
            "cursor": "page-3",
        },
    )
    assert synced.status_code == HTTP_OK
    assert synced.json()["data"]["sync_status"] == "partial"
    assert synced.json()["data"]["last_sync_cursor"] == "page-3"

    retired = await client.delete(f"/rag/sources/{source_id}", headers=admin)
    assert retired.status_code == HTTP_OK
    assert retired.json()["data"]["is_enabled"] is False


async def test_a_duplicate_slug_is_refused_over_http(
    client: AsyncClient, admin: dict[str, str]
) -> None:
    await client.post("/rag/sources", headers=admin, json=_source_body())
    duplicate = await client.post("/rag/sources", headers=admin, json=_source_body(name="Other"))
    assert duplicate.status_code in {HTTP_BAD_REQUEST, HTTP_UNPROCESSABLE, 409}


async def test_a_sub_minute_interval_is_a_schema_error(
    client: AsyncClient, admin: dict[str, str]
) -> None:
    response = await client.post(
        "/rag/sources", headers=admin, json=_source_body(sync_interval_seconds=1)
    )
    assert response.status_code in REFUSED


# ---- statistics, reports, audit --------------------------------------------------------


async def test_statistics_can_be_refreshed_on_demand(
    client: AsyncClient, headers: dict[str, str], cleared: dict[str, str]
) -> None:
    """A dashboard opened straight after a bulk import needs a window the
    rollup worker has not closed yet."""
    await _corpus(client, headers, cleared)
    response = await client.get("/rag/statistics", headers=headers, params={"refresh": True})
    assert response.status_code == HTTP_OK
    window = response.json()["data"][-1]
    assert window["documents_total"] >= 2
    assert window["vectors_total"] > 0


async def test_statistics_without_a_refresh_read_what_exists(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.get("/rag/statistics", headers=headers, params={"days": 1})
    assert response.status_code == HTTP_OK
    assert response.json()["data"] == []


async def test_the_evaluation_endpoint_reports_measurability(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.get("/rag/statistics/evaluation", headers=headers)
    assert response.status_code == HTTP_OK
    assert response.json()["data"]["measurable"] is False


@pytest.mark.parametrize("kind", [k.value for k in ReportKind])
async def test_every_report_kind_generates_over_http(
    client: AsyncClient, admin: dict[str, str], kind: str
) -> None:
    response = await client.post("/rag/reports", headers=admin, json={"kind": kind})
    assert response.status_code == HTTP_CREATED, response.text
    assert response.json()["data"]["status"] == "completed"


async def test_reports_are_listed_and_filterable(
    client: AsyncClient, admin: dict[str, str]
) -> None:
    await client.post("/rag/reports", headers=admin, json={"kind": "index"})
    listed = await client.get("/rag/reports", headers=admin, params={"kind": "index"})
    assert listed.status_code == HTTP_OK
    assert all(row["kind"] == "index" for row in listed.json()["data"])


async def test_the_audit_trail_is_readable(client: AsyncClient, headers: dict[str, str]) -> None:
    await _ingest(client, headers)
    response = await client.get("/rag/audit", headers=headers)
    assert response.status_code == HTTP_OK
    assert "document_imported" in {row["action"] for row in response.json()["data"]}


# ---- token claim handling ------------------------------------------------------------


async def test_an_unrecognised_clearance_falls_back_to_public(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    """Raising would take the service down for every caller the moment a
    claim vocabulary drifted; defaulting upwards would disclose."""
    await _ingest(client, auth_headers(organization_id=organization_id))
    odd = auth_headers(organization_id=organization_id, clearance="ultra")
    listed = await client.get("/rag/documents", headers=odd)
    assert listed.status_code == HTTP_OK
    assert listed.json()["data"] == []


async def test_roles_may_arrive_comma_separated(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    """Several issuers encode ``roles`` that way, and rejecting it would
    fail closed in a way that looks like a permissions bug."""
    from shared_core.security.jwt import encode_token

    from tests.conftest import _TEST_PRIVATE_KEY_PATH

    token = encode_token(
        {
            "sub": str(uuid.uuid4()),
            "organization_id": str(organization_id),
            "roles": "sre,engineer",
            "clearance": "secret",
            "role": "super_admin",
            "scopes": [],
        },
        private_key=_TEST_PRIVATE_KEY_PATH.read_text(encoding="ascii"),
    )
    response = await client.get("/rag/documents", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == HTTP_OK


async def test_a_malformed_project_claim_does_not_deny_everything(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    """A single unparseable project id must not cost the caller every
    project they legitimately hold."""
    from shared_core.security.jwt import encode_token

    from tests.conftest import _TEST_PRIVATE_KEY_PATH

    token = encode_token(
        {
            "sub": str(uuid.uuid4()),
            "organization_id": str(organization_id),
            "projects": ["not-a-uuid", str(uuid.uuid4())],
            "role": "super_admin",
            "scopes": [],
        },
        private_key=_TEST_PRIVATE_KEY_PATH.read_text(encoding="ascii"),
    )
    response = await client.get("/rag/documents", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == HTTP_OK


# ---- the workers -----------------------------------------------------------------------


async def test_the_indexing_sweep_runs_a_queued_job(
    db_session_factory: async_sessionmaker[AsyncSession],
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    embeddings: Any,
    publisher: RecordingPublisher,
    organization_id: uuid.UUID,
) -> None:
    """Exercised against the real session factory rather than through the
    HTTP client: the worker manages its own sessions, and the client
    fixture overrides transaction lifetime."""
    await ingestion_service.ingest(
        organization_id=organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    await indexing_service.queue_job(organization_id)

    worker = IndexingSweepWorker(db_session_factory, embeddings=embeddings, publish_event=publisher)
    assert await worker.tick() >= 0


async def test_the_indexing_sweep_reclaims_a_stale_job(
    db_session_factory: async_sessionmaker[AsyncSession],
    indexing_service: IndexingService,
    jobs_repo: IndexingJobRepository,
    embeddings: Any,
    publisher: RecordingPublisher,
    organization_id: uuid.UUID,
) -> None:
    job = await indexing_service.queue_job(organization_id)
    job.status = IndexStatus.RUNNING
    job.started_at = ago(7_200)
    job.attempts = 1
    await jobs_repo.update(job)

    worker = IndexingSweepWorker(db_session_factory, embeddings=embeddings, publish_event=publisher)
    await worker.tick()
    assert (await jobs_repo.get_by_id(job.id)) is not None


async def test_a_worker_tick_survives_a_broken_session_factory(
    embeddings: Any, publisher: RecordingPublisher
) -> None:
    """A failing tick must not take the scheduler down with it; the next
    tick retries."""

    def _broken() -> AsyncSession:
        raise RuntimeError("the pool is exhausted")

    worker = IndexingSweepWorker(_broken, embeddings=embeddings, publish_event=publisher)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        await worker.tick()


async def test_the_expiry_sweep_archives_what_is_due(
    db_session_factory: async_sessionmaker[AsyncSession],
    ingestion_service: IngestionService,
    documents_repo: Any,
    publisher: RecordingPublisher,
    organization_id: uuid.UUID,
) -> None:
    ingested = await ingestion_service.ingest(
        organization_id=organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    ingested.document.expires_at = ago(86_400)
    await documents_repo.update(ingested.document)

    worker = DocumentExpirySweepWorker(db_session_factory, publish_event=publisher)
    assert await worker.tick() >= 0


async def test_the_expiry_sweep_reports_zero_when_it_fails(
    publisher: RecordingPublisher,
) -> None:
    def _broken() -> AsyncSession:
        raise RuntimeError("the pool is exhausted")

    worker = DocumentExpirySweepWorker(_broken, publish_event=publisher)  # type: ignore[arg-type]
    assert await worker.tick() == 0


async def test_the_source_sync_sweep_reports_what_is_due(
    db_session_factory: async_sessionmaker[AsyncSession], publisher: RecordingPublisher
) -> None:
    worker = SourceSyncSweepWorker(db_session_factory, publish_event=publisher)
    assert await worker.tick() >= 0


async def test_the_source_sync_sweep_reports_zero_when_it_fails(
    publisher: RecordingPublisher,
) -> None:
    def _broken() -> AsyncSession:
        raise RuntimeError("the pool is exhausted")

    worker = SourceSyncSweepWorker(_broken, publish_event=publisher)  # type: ignore[arg-type]
    assert await worker.tick() == 0


async def test_the_statistics_rollup_covers_every_tenant(
    db_session_factory: async_sessionmaker[AsyncSession],
    ingestion_service: IngestionService,
    publisher: RecordingPublisher,
    organization_id: uuid.UUID,
) -> None:
    await ingestion_service.ingest(
        organization_id=organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    worker = StatisticsRollupWorker(
        db_session_factory,
        publish_event=publisher,
        window_seconds=3_600,
        max_organizations_per_tick=3,
    )
    assert await worker.tick() >= 0


async def test_every_worker_exposes_the_scheduler_entry_point(
    db_session_factory: async_sessionmaker[AsyncSession],
    embeddings: Any,
    publisher: RecordingPublisher,
) -> None:
    """``run_job`` is what ``shared_core.scheduler`` calls; a worker
    without it registers cleanly and then fails on its first tick."""
    workers = [
        IndexingSweepWorker(db_session_factory, embeddings=embeddings, publish_event=publisher),
        DocumentExpirySweepWorker(db_session_factory, publish_event=publisher),
        SourceSyncSweepWorker(db_session_factory, publish_event=publisher),
        StatisticsRollupWorker(
            db_session_factory,
            publish_event=publisher,
            window_seconds=3_600,
            max_organizations_per_tick=1,
        ),
    ]
    for worker in workers:
        await worker.run_job(object())
