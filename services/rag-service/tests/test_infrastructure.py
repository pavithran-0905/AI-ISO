"""Telemetry, notifications, the scheduler registrar, the in-memory
vector store, and the store registry."""

from __future__ import annotations

import uuid

import pytest
from opentelemetry import trace
from shared_core.enums.notification_type import NotificationType
from shared_core.exceptions.dependency import DependencyError
from shared_core.exceptions.notification import NotificationError

from app.models.enums import VectorStoreProvider
from app.notifications.rag_notifications import RagNotificationService
from app.telemetry import tracing
from app.vector_store.base import (
    VectorMatch,
    VectorQuery,
    VectorRecord,
    similarity_from_distance,
)
from app.vector_store.memory_store import MemoryVectorStore
from app.vector_store.registry import IMPLEMENTED, build_store, is_implemented
from app.workers.registrar import (
    DOCUMENT_EXPIRY_SWEEP_JOB_ID,
    INDEXING_SWEEP_JOB_ID,
    SOURCE_SYNC_SWEEP_JOB_ID,
    STATISTICS_ROLLUP_JOB_ID,
    register_document_expiry_sweep,
    register_indexing_sweep,
    register_source_sync_sweep,
    register_statistics_rollup,
)

# ---- telemetry ---------------------------------------------------------------

TRACER = trace.get_tracer("tests")

SPANS = [
    (tracing.trace_ingestion, {"source_kind": "markdown", "byte_size": 42}),
    (tracing.trace_chunking, {"strategy": "hybrid", "chunk_count": 3}),
    (tracing.trace_embedding, {"provider": "builtin", "model": "m", "batch_size": 4}),
    (tracing.trace_vector_search, {"provider": "pgvector", "top_k": 10}),
    (tracing.trace_keyword_search, {"candidates": 7}),
    (tracing.trace_fusion, {"method": "rrf", "arms": 2}),
    (tracing.trace_reranking, {"method": "hybrid", "candidates": 12}),
    (tracing.trace_context_assembly, {"budget": 4000, "included": 5}),
    (tracing.trace_retrieval, {"strategy": "hybrid", "top_k": 10}),
    (tracing.trace_indexing_job, {"kind": "full", "documents": 9}),
]


@pytest.mark.parametrize(("span_fn", "kwargs"), SPANS, ids=[fn.__name__ for fn, _ in SPANS])
def test_every_span_opens_and_closes(span_fn: object, kwargs: dict[str, object]) -> None:
    with span_fn(TRACER, **kwargs) as span:  # type: ignore[operator]
        assert span is not None


@pytest.mark.parametrize(("span_fn", "kwargs"), SPANS, ids=[fn.__name__ for fn, _ in SPANS])
def test_every_span_accepts_extra_attributes(span_fn: object, kwargs: dict[str, object]) -> None:
    """Attributes go through ``**{...}``; ``start_span`` has no parameter
    named ``attributes``, so passing one silently drops every attribute
    rather than raising."""
    with span_fn(TRACER, **kwargs, **{"rag.extra": "value"}) as span:  # type: ignore[operator]
        assert span is not None


# ---- notifications ------------------------------------------------------------


class _Manager:
    """A notification manager that records rather than sends."""

    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list[dict[str, object]] = []
        self._fail = fail

    async def send(self, **kwargs: object) -> None:
        if self._fail:
            raise NotificationError("The mail server is unreachable.")
        self.sent.append(kwargs)


def _service(*, fail: bool = False) -> tuple[RagNotificationService, _Manager]:
    manager = _Manager(fail=fail)
    return RagNotificationService(manager), manager  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_index_failure_names_the_document_and_the_reason() -> None:
    """ "Indexing failed" with neither is a notification whose only
    possible response is to go and look."""
    service, manager = _service()
    await service.send_index_failed("u1", title="Handbook", reason="provider timed out")
    body = str(manager.sent[0]["body"])
    assert "Handbook" in body
    assert "provider timed out" in body
    assert manager.sent[0]["notification_type"] is NotificationType.ERROR


@pytest.mark.asyncio
async def test_a_source_being_unreachable_is_a_warning_not_an_error() -> None:
    """The documents are fine and somebody else's system is not."""
    service, manager = _service()
    await service.send_source_unavailable("u1", source="Ops Wiki", reason="503")
    assert manager.sent[0]["notification_type"] is NotificationType.WARNING


@pytest.mark.asyncio
async def test_embedding_failure_names_the_provider() -> None:
    service, manager = _service()
    await service.send_embedding_failed("u1", provider="openai", reason="quota")
    assert "openai" in str(manager.sent[0]["body"])


@pytest.mark.asyncio
async def test_a_reindex_reports_both_counts() -> None:
    """ "Reindex completed" alone reads as success even when half the
    corpus failed."""
    service, manager = _service()
    await service.send_reindex_completed("u1", succeeded=8, failed=2)
    body = str(manager.sent[0]["body"])
    assert "8" in body
    assert "2" in body
    assert manager.sent[0]["notification_type"] is NotificationType.WARNING


@pytest.mark.asyncio
async def test_a_clean_reindex_is_informational() -> None:
    service, manager = _service()
    await service.send_reindex_completed("u1", succeeded=8, failed=0)
    assert manager.sent[0]["notification_type"] is NotificationType.INFORMATION


@pytest.mark.asyncio
async def test_the_storage_threshold_notification_carries_both_numbers() -> None:
    service, manager = _service()
    await service.send_storage_threshold("u1", used_bytes=200, threshold_bytes=100)
    body = str(manager.sent[0]["body"])
    assert "200" in body
    assert "100" in body


@pytest.mark.asyncio
async def test_an_unmeasured_evaluation_says_so_rather_than_reporting_zero() -> None:
    """Printing 0.00 for an unjudged corpus reads as a retriever returning
    nothing useful, which is a different and much more alarming fact."""
    service, manager = _service()
    await service.send_evaluation_completed("u1", queries=0, precision=None)
    assert "not measured" in str(manager.sent[0]["body"])

    await service.send_evaluation_completed("u1", queries=4, precision=0.75)
    assert "0.75" in str(manager.sent[1]["body"])


@pytest.mark.asyncio
async def test_a_failed_notification_never_propagates() -> None:
    """An indexing job that succeeded but could not tell anyone still
    indexed the documents."""
    service, manager = _service(fail=True)
    await service.send_index_failed("u1", title="x", reason="y")
    await service.send_source_unavailable("u1", source="x", reason="y")
    await service.send_embedding_failed("u1", provider="x", reason="y")
    await service.send_reindex_completed("u1", succeeded=1, failed=0)
    await service.send_storage_threshold("u1", used_bytes=1, threshold_bytes=2)
    await service.send_evaluation_completed("u1", queries=1, precision=1.0)
    assert manager.sent == []


# ---- the scheduler registrar ---------------------------------------------------


class _Scheduler:
    """A scheduler manager that records registrations."""

    def __init__(self) -> None:
        self.jobs: list[object] = []

    def register_job(self, job: object) -> object:
        self.jobs.append(job)
        return job


REGISTRARS = [
    (register_indexing_sweep, INDEXING_SWEEP_JOB_ID),
    (register_source_sync_sweep, SOURCE_SYNC_SWEEP_JOB_ID),
    (register_document_expiry_sweep, DOCUMENT_EXPIRY_SWEEP_JOB_ID),
    (register_statistics_rollup, STATISTICS_ROLLUP_JOB_ID),
]


async def _noop(_job: object) -> None:
    return None


@pytest.mark.parametrize(("register", "job_id"), REGISTRARS, ids=[j for _, j in REGISTRARS])
def test_every_job_registers_under_a_deterministic_id(register: object, job_id: str) -> None:
    """Deterministic, so re-registering replaces rather than leaks."""
    manager = _Scheduler()
    job = register(manager, _noop, interval_seconds=30)  # type: ignore[operator]
    assert job.job_id == job_id
    assert job.metadata["component"] == job_id
    assert manager.jobs == [job]


@pytest.mark.parametrize(("register", "_job_id"), REGISTRARS, ids=[j for _, j in REGISTRARS])
@pytest.mark.parametrize("interval", [0, -1])
def test_a_non_positive_interval_is_refused(register: object, _job_id: str, interval: int) -> None:
    """Zero would busy-loop the scheduler; negative is meaningless."""
    with pytest.raises(ValueError, match="interval must be positive"):
        register(_Scheduler(), _noop, interval_seconds=interval)  # type: ignore[operator]


# ---- the in-memory vector store -------------------------------------------------


ORG = uuid.uuid4()


def _record(key: str, vector: list[float], **kwargs: object) -> VectorRecord:
    defaults: dict[str, object] = {
        "chunk_id": uuid.uuid5(uuid.NAMESPACE_DNS, key),
        "document_id": uuid.uuid5(uuid.NAMESPACE_DNS, f"doc-{key}"),
        "organization_id": ORG,
        "vector": vector,
        "content": f"chunk {key}",
    }
    defaults.update(kwargs)
    return VectorRecord(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_the_memory_store_round_trips_a_vector() -> None:
    store = MemoryVectorStore(dimensions=3)
    assert await store.upsert([_record("a", [1.0, 0.0, 0.0])]) == 1
    matches = await store.search(VectorQuery(organization_id=ORG, vector=[1.0, 0.0, 0.0]))
    assert matches
    assert matches[0].score == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_upserting_the_same_chunk_replaces_rather_than_duplicates() -> None:
    store = MemoryVectorStore(dimensions=3)
    await store.upsert([_record("a", [1.0, 0.0, 0.0])])
    await store.upsert([_record("a", [0.0, 1.0, 0.0])])
    assert await store.count(ORG) == 1


@pytest.mark.asyncio
async def test_the_memory_store_refuses_a_wrong_width_vector() -> None:
    store = MemoryVectorStore(dimensions=3)
    with pytest.raises(Exception, match="dimension"):
        await store.upsert([_record("a", [1.0, 0.0])])


@pytest.mark.asyncio
async def test_the_memory_store_refuses_a_wrong_width_query() -> None:
    store = MemoryVectorStore(dimensions=3)
    await store.upsert([_record("a", [1.0, 0.0, 0.0])])
    with pytest.raises(Exception, match="dimension"):
        await store.search(VectorQuery(organization_id=ORG, vector=[1.0, 0.0]))


@pytest.mark.asyncio
async def test_the_memory_store_never_crosses_tenants() -> None:
    store = MemoryVectorStore(dimensions=3)
    await store.upsert([_record("a", [1.0, 0.0, 0.0])])
    assert (
        await store.search(VectorQuery(organization_id=uuid.uuid4(), vector=[1.0, 0.0, 0.0])) == []
    )
    assert await store.count(uuid.uuid4()) == 0


@pytest.mark.asyncio
async def test_the_role_filter_applies_even_to_a_caller_with_no_roles() -> None:
    """Skipping it fails open: a caller with no roles would see every
    role-restricted document in the organization."""
    store = MemoryVectorStore(dimensions=3)
    await store.upsert([_record("restricted", [1.0, 0.0, 0.0], allowed_roles=("sre",))])
    assert await store.search(VectorQuery(organization_id=ORG, vector=[1.0, 0.0, 0.0])) == []
    permitted = await store.search(
        VectorQuery(organization_id=ORG, vector=[1.0, 0.0, 0.0], caller_roles=("sre",))
    )
    assert permitted


@pytest.mark.asyncio
async def test_the_classification_ceiling_is_enforced() -> None:
    store = MemoryVectorStore(dimensions=3)
    await store.upsert([_record("secret", [1.0, 0.0, 0.0], classification="secret")])
    assert (
        await store.search(
            VectorQuery(organization_id=ORG, vector=[1.0, 0.0, 0.0], max_classification="internal")
        )
        == []
    )


@pytest.mark.asyncio
async def test_a_similarity_floor_filters() -> None:
    store = MemoryVectorStore(dimensions=3)
    await store.upsert([_record("a", [0.0, 1.0, 0.0])])
    assert (
        await store.search(
            VectorQuery(organization_id=ORG, vector=[1.0, 0.0, 0.0], min_similarity=0.9)
        )
        == []
    )


@pytest.mark.asyncio
async def test_deleting_a_document_removes_its_vectors() -> None:
    store = MemoryVectorStore(dimensions=3)
    record = _record("a", [1.0, 0.0, 0.0])
    await store.upsert([record])
    assert await store.delete_document(ORG, record.document_id) == 1
    assert await store.count(ORG) == 0


@pytest.mark.asyncio
async def test_the_memory_store_describes_itself_honestly() -> None:
    info = await MemoryVectorStore(dimensions=3).describe()
    assert info.provider is VectorStoreProvider.MEMORY


@pytest.mark.asyncio
async def test_upserting_nothing_is_a_no_op() -> None:
    assert await MemoryVectorStore(dimensions=3).upsert([]) == 0


@pytest.mark.asyncio
async def test_clearing_empties_the_store() -> None:
    store = MemoryVectorStore(dimensions=3)
    await store.upsert([_record("a", [1.0, 0.0, 0.0])])
    store.clear()
    assert await store.count(ORG) == 0


@pytest.mark.asyncio
async def test_a_document_id_filter_narrows_the_search() -> None:
    store = MemoryVectorStore(dimensions=3)
    wanted = _record("a", [1.0, 0.0, 0.0])
    await store.upsert([wanted, _record("b", [1.0, 0.0, 0.0])])
    matches = await store.search(
        VectorQuery(organization_id=ORG, vector=[1.0, 0.0, 0.0], document_ids=(wanted.document_id,))
    )
    assert {match.document_id for match in matches} == {wanted.document_id}


# ---- the query and match contracts ------------------------------------------------


def test_a_query_needs_a_vector() -> None:
    with pytest.raises(ValueError, match="empty query vector"):
        VectorQuery(organization_id=ORG, vector=[])


@pytest.mark.parametrize("top_k", [0, -1])
def test_a_query_needs_a_positive_top_k(top_k: int) -> None:
    with pytest.raises(ValueError, match="top_k"):
        VectorQuery(organization_id=ORG, vector=[1.0], top_k=top_k)


@pytest.mark.parametrize("floor", [-0.1, 1.1])
def test_a_similarity_floor_outside_zero_to_one_is_refused(floor: float) -> None:
    with pytest.raises(ValueError, match="min_similarity"):
        VectorQuery(organization_id=ORG, vector=[1.0], min_similarity=floor)


def test_distance_converts_to_similarity_the_same_way_for_every_backend() -> None:
    """pgvector returns distance and an in-memory store computes
    similarity; a caller comparing the two directly would rank everything
    backwards."""
    assert similarity_from_distance(0.0) == pytest.approx(1.0)
    assert similarity_from_distance(1.0) == pytest.approx(0.0)
    assert 0.0 <= similarity_from_distance(2.0) <= 1.0


def test_a_match_carries_both_score_and_distance() -> None:
    match = VectorMatch(chunk_id=uuid.uuid4(), document_id=uuid.uuid4(), score=0.9, distance=0.1)
    assert pytest.approx(match.score) == 0.9
    assert match.distance == 0.1


# ---- the store registry ------------------------------------------------------------


def test_only_the_two_real_backends_are_implemented() -> None:
    """The other six are declared and unimplemented on purpose: no
    instance of any of them exists in this platform's infrastructure, so a
    client for one would be code that has never executed against the thing
    it claims to talk to."""
    assert set(IMPLEMENTED) == {VectorStoreProvider.PGVECTOR, VectorStoreProvider.MEMORY}


@pytest.mark.parametrize("provider", sorted(IMPLEMENTED, key=str))
def test_an_implemented_provider_reports_itself(provider: VectorStoreProvider) -> None:
    assert is_implemented(provider)


@pytest.mark.parametrize("provider", sorted(set(VectorStoreProvider) - IMPLEMENTED, key=str))
def test_an_unimplemented_provider_is_refused_by_name(provider: VectorStoreProvider) -> None:
    """Refused explicitly rather than silently falling back: a service
    that quietly used a different store than it was configured for is
    worse than one that will not start."""
    assert not is_implemented(provider)
    with pytest.raises(DependencyError, match=str(provider)):
        build_store(provider, dimensions=8)


def test_an_unknown_provider_name_is_refused() -> None:
    assert not is_implemented("not-a-store")


def test_the_memory_store_needs_no_session() -> None:
    assert isinstance(build_store(VectorStoreProvider.MEMORY, dimensions=8), MemoryVectorStore)


def test_pgvector_without_a_session_is_refused() -> None:
    with pytest.raises(DependencyError, match="session"):
        build_store(VectorStoreProvider.PGVECTOR, dimensions=8)
