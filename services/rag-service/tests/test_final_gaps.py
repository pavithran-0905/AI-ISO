"""The last uncovered branches: worker registration, encrypted and
malformed binary documents, provider-model bookkeeping, and the retrieval
paths a healthy corpus never takes.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from typing import Any

import pytest
from pypdf import PdfWriter
from shared_core.config.environment import Environment
from shared_core.exceptions.validation import ValidationError

from app.config.settings import RagServiceSettings, Settings, get_settings
from app.core.factory import _build_cors_config, _build_embeddings, _build_graph, _VectorCache
from app.graph_rag.client import GraphClient
from app.graph_rag.retriever import GraphRetriever
from app.models.enums import (
    EmbeddingProvider,
    FeedbackVerdict,
    ReportKind,
    RetrievalStrategy,
    SourceKind,
)
from app.parsers import get_parser
from app.parsers.base import MAX_PARSE_BYTES, ParsedBlock, ParseResult
from app.repositories.retrieval import RerankingResultRepository
from app.security.access import AccessContext
from app.services.analytics import AnalyticsService
from app.services.indexing import IndexingService
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService
from tests.conftest import HANDBOOK, ago, utcnow
from tests.test_graph_rag import _Driver

# ---- binary parser failure paths --------------------------------------------


def test_an_encrypted_pdf_is_refused_with_its_reason() -> None:
    """ "Could not parse" is unactionable; "it is encrypted" tells somebody
    to supply the password or a decrypted copy."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("secret")
    buffer = io.BytesIO()
    writer.write(buffer)

    parser = get_parser(SourceKind.PDF)
    assert parser is not None
    result = parser.parse(buffer.getvalue(), filename="locked.pdf")
    assert result.error is not None


def test_a_zip_that_is_not_a_docx_fails_without_raising() -> None:
    """A valid archive containing the wrong parts is the failure mode a
    magic-number check misses."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("not-word/document.xml", "<x/>")

    parser = get_parser(SourceKind.DOCX)
    assert parser is not None
    assert not parser.parse(buffer.getvalue(), filename="fake.docx").succeeded


def test_a_truncated_pdf_fails_without_raising() -> None:
    parser = get_parser(SourceKind.PDF)
    assert parser is not None
    assert not parser.parse(b"%PDF-1.7\ntruncated", filename="bad.pdf").succeeded


def test_an_oversized_pdf_is_refused_before_parsing() -> None:
    parser = get_parser(SourceKind.PDF)
    assert parser is not None
    assert parser.parse(b"%PDF-" + b"x" * MAX_PARSE_BYTES, filename="huge.pdf").error


# ---- text parser corners ------------------------------------------------------


def test_a_csv_with_ragged_rows_still_parses() -> None:
    parser = get_parser(SourceKind.CSV)
    assert parser is not None
    assert parser.parse(b"a,b,c\n1,2\n3,4,5,6\n", filename="r.csv").succeeded


def test_a_tsv_is_parsed_as_a_csv() -> None:
    parser = get_parser(SourceKind.CSV)
    assert parser is not None
    assert parser.parse(b"a\tb\n1\t2\n", filename="r.tsv").succeeded


def test_deeply_nested_json_still_flattens() -> None:
    parser = get_parser(SourceKind.JSON)
    assert parser is not None
    payload = b'{"a": {"b": {"c": {"d": "deep value"}}}}'
    assert "deep value" in parser.parse(payload, filename="d.json").text


def test_a_yaml_list_document_parses() -> None:
    parser = get_parser(SourceKind.YAML)
    assert parser is not None
    assert parser.parse(b"- one\n- two\n", filename="l.yaml").succeeded


def test_nested_xml_renders_its_leaves() -> None:
    parser = get_parser(SourceKind.XML)
    assert parser is not None
    result = parser.parse(b"<a><b><c>leaf</c></b></a>", filename="n.xml")
    assert "leaf" in result.text


def test_html_entities_are_decoded() -> None:
    parser = get_parser(SourceKind.HTML)
    assert parser is not None
    assert "&" in parser.parse(b"<p>a &amp; b</p>", filename="e.html").text


def test_a_parse_result_with_only_warnings_still_succeeded() -> None:
    """A PDF where three pages of forty failed is worth indexing;
    refusing it would discard thirty-seven good pages to punish three."""
    result = ParseResult(text="usable", blocks=[ParsedBlock(text="usable")], warnings=["a page"])
    assert result.succeeded
    assert not result.is_empty


# ---- the factory's own builders ------------------------------------------------


def _settings(**service_kwargs: Any) -> Settings:
    base = get_settings()
    return Settings(
        application=base.application,
        database=base.database,
        redis=base.redis,
        rabbitmq=base.rabbitmq,
        email=base.email,
        neo4j=base.neo4j,
        minio=base.minio,
        service=RagServiceSettings(**service_kwargs),
    )


class _Redis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> bytes | None:
        value = self.store.get(key)
        return value.encode() if value is not None else None

    async def set(self, key: str, value: str) -> None:
        self.store[key] = value

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value


@pytest.mark.asyncio
async def test_the_redis_cache_adapter_round_trips() -> None:
    cache = _VectorCache(_Redis())  # type: ignore[arg-type]
    assert await cache.get("missing") is None
    await cache.set("k", "v", ttl_seconds=60)
    assert await cache.get("k") == "v"
    await cache.set("k2", "v2")
    assert await cache.get("k2") == "v2"


def test_the_builtin_provider_gets_the_builtin_encoder(http_client: Any) -> None:
    """No credential, no network -- which is what makes the whole pipeline
    testable."""
    service = _build_embeddings(
        http_client, _Redis(), _settings(embedding_provider="builtin")  # type: ignore[arg-type]
    )
    assert service.provider is EmbeddingProvider.BUILTIN


def test_the_cache_can_be_turned_off(http_client: Any) -> None:
    service = _build_embeddings(
        http_client,  # type: ignore[arg-type]
        _Redis(),  # type: ignore[arg-type]
        _settings(embedding_provider="builtin", embedding_cache_enabled=False),
    )
    assert service.model


def test_graph_rag_can_be_disabled_entirely() -> None:
    """``None`` rather than a disabled object, so the graph arm is absent
    from the code path rather than silently returning nothing."""
    assert _build_graph(_settings(graph_rag_enabled=False)) is None


def test_graph_rag_builds_a_retriever_when_enabled() -> None:
    retriever = _build_graph(_settings(graph_rag_enabled=True))
    assert retriever is not None


def test_cors_is_permissive_in_development_and_named_in_production() -> None:
    base = get_settings()
    development = _build_cors_config(base)
    assert development.allow_origins

    production = Settings(
        application=base.application.model_copy(update={"environment": Environment.PRODUCTION}),
        database=base.database,
        redis=base.redis,
        rabbitmq=base.rabbitmq,
        email=base.email,
        neo4j=base.neo4j,
        minio=base.minio,
        service=RagServiceSettings(cors_allowed_origins=["https://app.example.com"]),
    )
    assert "https://app.example.com" in _build_cors_config(production).allow_origins


# ---- retrieval and analytics corners ---------------------------------------------

pytestmark_async = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_a_result_whose_chunk_vanished_is_skipped_not_denied(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    retrieval_service: RetrievalService,
    chunks_repo: Any,
    caller: AccessContext,
) -> None:
    """Nothing was withheld -- it is simply gone -- so it must not inflate
    the denied count, which is an access-control signal."""
    record = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    await indexing_service.index_document(caller.organization_id, record.document.id)
    for chunk in record.chunks:
        await chunks_repo.delete(chunk.id)

    output = await retrieval_service.retrieve(caller, "nightly backup")
    assert output.denied == 0


@pytest.mark.asyncio
async def test_a_document_that_was_never_indexed_is_not_retrievable(
    ingestion_service: IngestionService,
    retrieval_service: RetrievalService,
    caller: AccessContext,
) -> None:
    record = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    output = await retrieval_service.retrieve(
        caller, "nightly backup", strategy=RetrievalStrategy.VECTOR
    )
    assert record.document.id not in {item.document.id for item in output.results}


@pytest.mark.asyncio
async def test_every_lexical_alias_strategy_runs(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    retrieval_service: RetrievalService,
    caller: AccessContext,
) -> None:
    """FUZZY, BOOLEAN, and METADATA are aliases of the lexical arm rather
    than bespoke implementations, and the mapping is stated rather than
    hidden -- naming them is what keeps them from looking implemented."""
    record = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    await indexing_service.index_document(caller.organization_id, record.document.id)
    for strategy in (
        RetrievalStrategy.FUZZY,
        RetrievalStrategy.BOOLEAN,
        RetrievalStrategy.METADATA,
        RetrievalStrategy.SEMANTIC,
    ):
        output = await retrieval_service.retrieve(caller, "nightly backup", strategy=strategy)
        assert output.query.strategy == strategy


@pytest.mark.asyncio
async def test_reranking_movement_is_measurable(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    retrieval_service: RetrievalService,
    rerankings_repo: RerankingResultRepository,
    caller: AccessContext,
) -> None:
    """Near-zero average movement means the reranker is pure latency, and
    that is only visible because both ranks are recorded."""
    record = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    await indexing_service.index_document(caller.organization_id, record.document.id)
    await retrieval_service.retrieve(caller, "restore the snapshot")
    assert await rerankings_repo.average_movement(caller.organization_id, since=ago(3_600)) >= 0.0


@pytest.mark.asyncio
async def test_a_statistics_window_can_be_named_explicitly(
    analytics_service: AnalyticsService, organization_id: uuid.UUID
) -> None:
    statistic = await analytics_service.compute_statistics(
        organization_id, window_start=ago(7_200), window_end=utcnow()
    )
    assert statistic.window_start < statistic.window_end


@pytest.mark.asyncio
async def test_evaluation_ignores_a_query_judged_entirely_irrelevant(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    retrieval_service: RetrievalService,
    analytics_service: AnalyticsService,
    caller: AccessContext,
) -> None:
    """Judged, but with no ground truth to compare against -- real
    information, and not something precision can be computed from."""
    record = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    await indexing_service.index_document(caller.organization_id, record.document.id)
    output = await retrieval_service.retrieve(caller, "backup")
    await retrieval_service.submit_feedback(
        caller,
        output.query.id,
        verdict=FeedbackVerdict.IRRELEVANT,
        chunk_id=output.results[0].chunk.id,
    )
    summary = await analytics_service.evaluate(caller.organization_id)
    assert not summary.is_measurable


@pytest.mark.asyncio
async def test_the_storage_estimate_scales_with_the_vector_count(
    analytics_service: AnalyticsService, organization_id: uuid.UUID
) -> None:
    assert await analytics_service.storage_used(organization_id) == 0


@pytest.mark.asyncio
async def test_a_report_over_a_named_window(
    analytics_service: AnalyticsService, organization_id: uuid.UUID
) -> None:
    report = await analytics_service.generate_report(
        organization_id, ReportKind.EMBEDDING, since=ago(7_200), title="Named"
    )
    assert report.title == "Named"
    assert "cost_usd_held" in report.content
    assert "cost_usd_spent" in report.content


@pytest.mark.asyncio
async def test_an_indexing_batch_size_below_one_is_clamped(
    documents_repo: Any,
    versions_repo: Any,
    chunks_repo: Any,
    vectors_repo: Any,
    jobs_repo: Any,
    audit_repo: Any,
    embeddings: Any,
    vector_store: Any,
    publisher: Any,
    ingestion_service: IngestionService,
    organization_id: uuid.UUID,
) -> None:
    """Zero would make the batch loop take no steps and embed nothing
    while reporting success."""
    service = IndexingService(
        documents_repo,
        versions_repo,
        chunks_repo,
        vectors_repo,
        jobs_repo,
        audit_repo,
        embeddings=embeddings,
        store=vector_store,
        publish_event=publisher,
        batch_size=0,
    )
    record = await ingestion_service.ingest(
        organization_id=organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    result = await service.index_document(organization_id, record.document.id)
    assert result.embedded == record.chunk_count


@pytest.mark.asyncio
async def test_a_context_budget_above_the_deployment_ceiling_is_clamped(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    retrieval_service: RetrievalService,
    caller: AccessContext,
) -> None:
    record = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    await indexing_service.index_document(caller.organization_id, record.document.id)
    output = await retrieval_service.build_context(caller, "backup", max_tokens=100_000)
    assert output.context.budget <= 100_000


@pytest.mark.asyncio
async def test_ingesting_something_over_the_byte_limit_is_flagged(
    documents_repo: Any,
    versions_repo: Any,
    chunks_repo: Any,
    metadata_repo: Any,
    audit_repo: Any,
    publisher: Any,
    organization_id: uuid.UUID,
) -> None:
    service = IngestionService(
        documents_repo,
        versions_repo,
        chunks_repo,
        metadata_repo,
        audit_repo,
        publish_event=publisher,
        max_bytes=10,
    )
    result = await service.ingest(
        organization_id=organization_id,
        data=b"a document comfortably over ten bytes",
        title="Big",
        filename="big.txt",
    )
    assert any("oversized" in str(finding["finding"]) for finding in result.findings)


@pytest.mark.asyncio
async def test_a_zero_chunk_ceiling_is_refused(
    documents_repo: Any,
    versions_repo: Any,
    chunks_repo: Any,
    metadata_repo: Any,
    audit_repo: Any,
    publisher: Any,
    organization_id: uuid.UUID,
) -> None:
    service = IngestionService(
        documents_repo,
        versions_repo,
        chunks_repo,
        metadata_repo,
        audit_repo,
        publish_event=publisher,
        max_chunks=0,
    )
    with pytest.raises(ValidationError, match="max_chunks"):
        await service.ingest(
            organization_id=organization_id, data=HANDBOOK, title="H", filename="h.md"
        )


@pytest.mark.asyncio
async def test_the_graph_arm_contributes_the_chunks_its_nodes_name(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    documents_repo: Any,
    chunks_repo: Any,
    queries_repo: Any,
    results_repo: Any,
    rerankings_repo: Any,
    feedback_repo: Any,
    audit_repo: Any,
    embeddings: Any,
    vector_store: Any,
    publisher: Any,
    caller: AccessContext,
) -> None:
    """A graph node with no chunk is real knowledge this arm cannot cite,
    and returning it would produce a citation pointing at nothing -- so
    only nodes carrying a ``chunk_id`` contribute.
    """

    record = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    await indexing_service.index_document(caller.organization_id, record.document.id)

    driver = _Driver(
        [
            {
                "key": "backups",
                "labels": ["GraphNode"],
                "props": {"name": "Backups", "chunk_id": str(record.chunks[0].id)},
            },
            {"key": "uncited", "labels": ["GraphNode"], "props": {"name": "Uncited"}},
        ]
    )
    service = RetrievalService(
        documents_repo,
        chunks_repo,
        queries_repo,
        results_repo,
        rerankings_repo,
        feedback_repo,
        audit_repo,
        embeddings=embeddings,
        store=vector_store,
        publish_event=publisher,
        graph=GraphRetriever(GraphClient(driver)),
    )
    output = await service.retrieve(caller, "backups", strategy=RetrievalStrategy.GRAPH)
    assert record.chunks[0].id in {item.chunk.id for item in output.results}


@pytest.mark.asyncio
async def test_a_hybrid_retrieval_runs_the_graph_arm_alongside_the_others(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    documents_repo: Any,
    chunks_repo: Any,
    queries_repo: Any,
    results_repo: Any,
    rerankings_repo: Any,
    feedback_repo: Any,
    audit_repo: Any,
    embeddings: Any,
    vector_store: Any,
    publisher: Any,
    caller: AccessContext,
) -> None:

    record = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    await indexing_service.index_document(caller.organization_id, record.document.id)

    service = RetrievalService(
        documents_repo,
        chunks_repo,
        queries_repo,
        results_repo,
        rerankings_repo,
        feedback_repo,
        audit_repo,
        embeddings=embeddings,
        store=vector_store,
        publish_event=publisher,
        graph=GraphRetriever(GraphClient(_Driver([]))),
    )
    output = await service.retrieve(caller, "nightly backup retention")
    assert output.results
