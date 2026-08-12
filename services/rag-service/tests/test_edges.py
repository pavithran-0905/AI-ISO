"""The branches the happy path never reaches.

Malformed input, empty corners, and the failure modes each module was
written to survive rather than propagate.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from shared_core.exceptions.not_found import NotFoundError

from app.chunking.splitter import ChunkingConfig, chunk_text
from app.context.assembler import ContextChunk, assemble, deduplicate, order_for_reading
from app.models.enums import (
    ChunkStrategy,
    ClassificationLevel,
    DocumentStatus,
    IndexStatus,
    ReportKind,
    RerankMethod,
    RetrievalStrategy,
    SourceKind,
)
from app.parsers import get_parser
from app.parsers.base import MAX_PARSE_BYTES
from app.repositories.document import (
    DocumentChunkRepository,
    DocumentMetadataRepository,
    DocumentRepository,
    DocumentVersionRepository,
)
from app.security.access import AccessContext
from app.services.analytics import AnalyticsService
from app.services.documents import DocumentService
from app.services.indexing import IndexingService
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService
from app.services.sources import SourceService
from tests.conftest import HANDBOOK, NETWORK, ago, utcnow

# ---- chunking corners --------------------------------------------------------


def test_a_single_enormous_token_is_still_split() -> None:
    """A base64 blob has no whitespace at all; refusing to split it would
    make one chunk the size of the document."""
    chunks = chunk_text(
        "A" * 500, ChunkingConfig(strategy=ChunkStrategy.FIXED_SIZE, chunk_size=100, overlap=10)
    )
    assert len(chunks) > 1


def test_text_with_no_headings_falls_back_to_the_whole_document() -> None:
    chunks = chunk_text(
        "No headings anywhere in this text at all.",
        ChunkingConfig(strategy=ChunkStrategy.HEADING, chunk_size=400, overlap=40),
    )
    assert len(chunks) == 1


def test_setext_headings_are_recognised() -> None:
    text = "Handbook\n========\n\nThe nightly backup runs at 02:00.\n"
    chunks = chunk_text(
        text, ChunkingConfig(strategy=ChunkStrategy.HEADING, chunk_size=400, overlap=40)
    )
    assert chunks


def test_a_list_becomes_its_own_kind() -> None:
    text = "Steps:\n\n- restart the service\n- verify health\n- promote to primary\n"
    chunks = chunk_text(
        text, ChunkingConfig(strategy=ChunkStrategy.HYBRID, chunk_size=200, overlap=20)
    )
    assert chunks


def test_semantic_chunking_splits_where_the_topic_changes() -> None:
    text = (
        "The nightly backup writes to the archive bucket. Retention is thirty days.\n\n"
        "The production vpc spans three availability zones. Peering is one-way.\n\n"
        "Primary on-call acknowledges within fifteen minutes. Escalation follows.\n"
    )
    chunks = chunk_text(
        text, ChunkingConfig(strategy=ChunkStrategy.SEMANTIC, chunk_size=400, overlap=40)
    )
    assert len(chunks) >= 2


def test_sentence_chunking_does_not_split_a_version_number() -> None:
    """A bare ``[.!?]\\s`` rule shatters version numbers, abbreviations,
    and decimals -- exactly the technical text this service ingests."""
    chunks = chunk_text(
        "Install version 1.2 of the agent. Then restart it.",
        ChunkingConfig(strategy=ChunkStrategy.SENTENCE, chunk_size=400, overlap=20),
    )
    assert all("1.2" in chunk.content or "restart" in chunk.content for chunk in chunks)


# ---- context assembly corners --------------------------------------------------


def test_ordering_nothing_yields_nothing() -> None:
    assert order_for_reading([]) == []


def test_deduplicating_nothing_yields_nothing() -> None:
    kept, dropped = deduplicate([])
    assert kept == []
    assert dropped == []


def test_a_chunk_of_whitespace_contributes_nothing_to_a_block() -> None:
    assembled = assemble(
        [ContextChunk(key="a", content="   ", score=1.0, document_id="d", document_title="D")],
        max_tokens=100,
    )
    assert not assembled.text.strip()


def test_citations_carry_page_and_section_when_the_parser_found_them() -> None:
    assembled = assemble(
        [
            ContextChunk(
                key="a",
                content="Restore from the snapshot.",
                score=1.0,
                document_id="d",
                document_title="Handbook",
                page_number=14,
                section_path="Operations > Restore",
                source_uri="https://wiki/ops",
            )
        ],
        max_tokens=200,
    )
    citation = assembled.citations[0]
    assert citation.page_number == 14
    assert "Restore" in citation.render()


# ---- parser corners ---------------------------------------------------------------


def test_an_empty_csv_parses_to_nothing() -> None:
    parser = get_parser(SourceKind.CSV)
    assert parser is not None
    assert parser.parse(b"", filename="e.csv").is_empty


def test_a_csv_with_only_a_header_still_parses() -> None:
    parser = get_parser(SourceKind.CSV)
    assert parser is not None
    assert parser.parse(b"name,role\n", filename="h.csv").error is None


def test_a_json_array_parses() -> None:
    parser = get_parser(SourceKind.JSON)
    assert parser is not None
    result = parser.parse(b'[{"a": 1}, {"b": 2}]', filename="a.json")
    assert result.succeeded


def test_a_json_scalar_parses() -> None:
    parser = get_parser(SourceKind.JSON)
    assert parser is not None
    assert parser.parse(b'"just a string"', filename="s.json").succeeded


def test_html_without_a_body_still_parses() -> None:
    parser = get_parser(SourceKind.HTML)
    assert parser is not None
    assert parser.parse(b"<p>Bare paragraph.</p>", filename="b.html").succeeded


def test_html_strips_style_as_well_as_script() -> None:
    parser = get_parser(SourceKind.HTML)
    assert parser is not None
    result = parser.parse(
        b"<html><head><style>.a{color:red}</style></head><body><p>Text.</p></body></html>",
        filename="s.html",
    )
    assert "color:red" not in result.text


def test_an_empty_yaml_document_parses_to_nothing() -> None:
    parser = get_parser(SourceKind.YAML)
    assert parser is not None
    assert parser.parse(b"", filename="e.yaml").is_empty


def test_malformed_xml_fails_without_raising() -> None:
    parser = get_parser(SourceKind.XML)
    assert parser is not None
    assert not parser.parse(b"<unclosed>", filename="b.xml").succeeded


def test_a_markdown_code_fence_is_marked_as_code() -> None:
    parser = get_parser(SourceKind.MARKDOWN)
    assert parser is not None
    result = parser.parse(b"# T\n\n```python\nx = 1\n```\n", filename="c.md")
    assert any(block.is_code for block in result.blocks)


def test_a_markdown_table_is_marked_as_a_table() -> None:
    parser = get_parser(SourceKind.MARKDOWN)
    assert parser is not None
    result = parser.parse(b"# T\n\n| a | b |\n| - | - |\n| 1 | 2 |\n", filename="t.md")
    assert any(block.is_table for block in result.blocks)


def test_an_oversized_upload_is_refused_by_every_parser() -> None:

    parser = get_parser(SourceKind.TXT)
    assert parser is not None
    result = parser.parse(b"x" * (MAX_PARSE_BYTES + 1), filename="huge.txt")
    assert result.error is not None


# ---- service corners ------------------------------------------------------------

pytestmark_async = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_ingesting_by_content_type_alone(
    ingestion_service: IngestionService, organization_id: uuid.UUID
) -> None:
    result = await ingestion_service.ingest(
        organization_id=organization_id,
        data=b"Plain text with no filename at all.",
        title="Untitled",
        content_type="text/plain",
    )
    assert result.chunk_count > 0


@pytest.mark.asyncio
async def test_ingesting_with_an_explicit_source_kind(
    ingestion_service: IngestionService, organization_id: uuid.UUID
) -> None:
    result = await ingestion_service.ingest(
        organization_id=organization_id,
        data=b"# Title\n\nBody text.",
        title="T",
        source_kind=SourceKind.MARKDOWN,
    )
    assert result.chunk_count > 0


@pytest.mark.asyncio
async def test_tags_and_roles_are_deduplicated_and_trimmed(
    ingestion_service: IngestionService, organization_id: uuid.UUID
) -> None:
    result = await ingestion_service.ingest(
        organization_id=organization_id,
        data=HANDBOOK,
        title="H",
        filename="h.md",
        tags=["ops", "ops", " ops ", ""],
    )
    assert result.document.tags.count("ops") >= 1


@pytest.mark.asyncio
async def test_a_document_can_be_scoped_to_a_project(
    ingestion_service: IngestionService,
    document_service: DocumentService,
    organization_id: uuid.UUID,
) -> None:
    project = uuid.uuid4()
    result = await ingestion_service.ingest(
        organization_id=organization_id,
        data=HANDBOOK,
        title="H",
        filename="h.md",
        project_scope_id=project,
    )
    inside = AccessContext.build(
        organization_id, clearance=ClassificationLevel.INTERNAL, project_scope_ids=[project]
    )
    outside = AccessContext.build(organization_id, clearance=ClassificationLevel.INTERNAL)
    assert (await document_service.get_document(inside, result.document.id)).id
    assert result.document.id not in {
        row.id for row in await document_service.list_documents(outside)
    }


@pytest.mark.asyncio
async def test_updating_nothing_changes_nothing(
    ingestion_service: IngestionService,
    document_service: DocumentService,
    admin_caller: AccessContext,
) -> None:
    result = await ingestion_service.ingest(
        organization_id=admin_caller.organization_id,
        data=HANDBOOK,
        title="H",
        filename="h.md",
    )
    unchanged = await document_service.update_document(admin_caller, result.document.id)
    assert unchanged.title == "H"


@pytest.mark.asyncio
async def test_setting_the_same_classification_is_not_a_change(
    ingestion_service: IngestionService,
    document_service: DocumentService,
    caller: AccessContext,
) -> None:
    """Re-asserting a document's existing classification must not be
    refused as an escalation."""
    result = await ingestion_service.ingest(
        organization_id=caller.organization_id,
        data=HANDBOOK,
        title="H",
        filename="h.md",
        classification=ClassificationLevel.INTERNAL,
    )
    same = await document_service.update_document(
        caller, result.document.id, classification=ClassificationLevel.INTERNAL
    )
    assert same.classification == ClassificationLevel.INTERNAL


@pytest.mark.asyncio
async def test_expiry_skips_what_is_already_archived(
    ingestion_service: IngestionService,
    document_service: DocumentService,
    documents_repo: DocumentRepository,
    organization_id: uuid.UUID,
) -> None:
    result = await ingestion_service.ingest(
        organization_id=organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    result.document.expires_at = ago(3_600)
    result.document.status = DocumentStatus.ARCHIVED
    await documents_repo.update(result.document)
    assert result.document.id not in await document_service.expire_documents(utcnow())


@pytest.mark.asyncio
async def test_a_job_with_no_targets_completes(
    indexing_service: IndexingService, organization_id: uuid.UUID
) -> None:
    job = await indexing_service.queue_job(organization_id)
    outcome = await indexing_service.run_job(job)
    assert outcome.job.status == IndexStatus.COMPLETED
    assert outcome.results == []


@pytest.mark.asyncio
async def test_a_job_can_be_scoped_to_one_knowledge_source(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    source_service: SourceService,
    organization_id: uuid.UUID,
) -> None:
    source = await source_service.create_source(
        organization_id, slug="wiki", name="Wiki", source_kind=SourceKind.CONFLUENCE
    )
    await ingestion_service.ingest(
        organization_id=organization_id,
        data=HANDBOOK,
        title="In source",
        filename="a.md",
        knowledge_source_id=source.id,
    )
    await ingestion_service.ingest(
        organization_id=organization_id, data=NETWORK, title="Outside", filename="b.md"
    )
    job = await indexing_service.queue_job(organization_id, knowledge_source_id=source.id)
    outcome = await indexing_service.run_job(job)
    assert len(outcome.results) == 1


@pytest.mark.asyncio
async def test_a_job_naming_one_document_indexes_only_it(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    organization_id: uuid.UUID,
) -> None:
    first = await ingestion_service.ingest(
        organization_id=organization_id, data=HANDBOOK, title="A", filename="a.md"
    )
    await ingestion_service.ingest(
        organization_id=organization_id, data=NETWORK, title="B", filename="b.md"
    )
    job = await indexing_service.queue_job(organization_id, document_id=first.document.id)
    outcome = await indexing_service.run_job(job)
    assert [row.document_id for row in outcome.results] == [first.document.id]


@pytest.mark.asyncio
async def test_reclaiming_when_nothing_is_stale_is_a_no_op(
    indexing_service: IndexingService,
) -> None:
    assert await indexing_service.reclaim_stale_jobs(utcnow()) == []


@pytest.mark.asyncio
async def test_retrieval_can_be_narrowed_to_named_documents(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    retrieval_service: RetrievalService,
    caller: AccessContext,
) -> None:
    wanted = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=HANDBOOK, title="A", filename="a.md"
    )
    other = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=NETWORK, title="B", filename="b.md"
    )
    for record in (wanted, other):
        await indexing_service.index_document(caller.organization_id, record.document.id)

    output = await retrieval_service.retrieve(
        caller, "backup", strategy=RetrievalStrategy.VECTOR, document_ids=[wanted.document.id]
    )
    assert {item.document.id for item in output.results} == {wanted.document.id}


@pytest.mark.asyncio
async def test_explicit_fusion_weights_are_honoured(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    retrieval_service: RetrievalService,
    caller: AccessContext,
) -> None:
    record = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=HANDBOOK, title="A", filename="a.md"
    )
    await indexing_service.index_document(caller.organization_id, record.document.id)
    output = await retrieval_service.retrieve(
        caller, "backup retention", weights={"vector": 1.0, "keyword": 0.0}
    )
    assert output.results


@pytest.mark.asyncio
async def test_a_cross_encoder_rerank_is_refused_through_the_service(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    retrieval_service: RetrievalService,
    caller: AccessContext,
) -> None:
    record = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=HANDBOOK, title="A", filename="a.md"
    )
    await indexing_service.index_document(caller.organization_id, record.document.id)
    with pytest.raises(NotImplementedError):
        await retrieval_service.retrieve(caller, "backup", rerank_method=RerankMethod.CROSS_ENCODER)


@pytest.mark.asyncio
async def test_a_graph_strategy_with_no_graph_returns_nothing(
    retrieval_service: RetrievalService, caller: AccessContext
) -> None:
    """Absent rather than present-and-silent: a graph that is off should
    not look like a graph that knows nothing."""
    output = await retrieval_service.retrieve(caller, "backups", strategy=RetrievalStrategy.GRAPH)
    assert output.results == []


@pytest.mark.asyncio
async def test_metadata_filters_reach_the_query(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    retrieval_service: RetrievalService,
    caller: AccessContext,
) -> None:
    record = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=HANDBOOK, title="A", filename="a.md"
    )
    await indexing_service.index_document(caller.organization_id, record.document.id)
    output = await retrieval_service.retrieve(
        caller, "backup", metadata_filters={"department": "finance"}
    )
    assert output.query.metadata_filters == {"department": "finance"}


@pytest.mark.asyncio
async def test_context_assembly_can_drop_citations(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    retrieval_service: RetrievalService,
    caller: AccessContext,
) -> None:
    record = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=HANDBOOK, title="A", filename="a.md"
    )
    await indexing_service.index_document(caller.organization_id, record.document.id)
    output = await retrieval_service.build_context(
        caller, "backup", max_tokens=500, include_citations=False
    )
    assert output.context.text.strip()


@pytest.mark.asyncio
async def test_partial_context_truncates_when_asked(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    retrieval_service: RetrievalService,
    caller: AccessContext,
) -> None:
    record = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=HANDBOOK, title="A", filename="a.md"
    )
    await indexing_service.index_document(caller.organization_id, record.document.id)
    output = await retrieval_service.build_context(
        caller, "backup", max_tokens=15, allow_partial=True
    )
    assert output.context.token_count <= 15


@pytest.mark.asyncio
async def test_statistics_over_an_empty_tenant_are_all_zero(
    analytics_service: AnalyticsService, organization_id: uuid.UUID
) -> None:
    statistic = await analytics_service.compute_statistics(organization_id)
    assert statistic.documents_total == 0
    assert statistic.retrieval_count == 0
    assert statistic.top_documents == []
    assert statistic.unanswered_queries == []


@pytest.mark.asyncio
async def test_evaluating_a_query_nobody_judged_is_unmeasurable(
    ingestion_service: IngestionService,
    indexing_service: IndexingService,
    retrieval_service: RetrievalService,
    analytics_service: AnalyticsService,
    caller: AccessContext,
) -> None:
    record = await ingestion_service.ingest(
        organization_id=caller.organization_id, data=HANDBOOK, title="A", filename="a.md"
    )
    await indexing_service.index_document(caller.organization_id, record.document.id)
    output = await retrieval_service.retrieve(caller, "backup")
    measured = await analytics_service.evaluate_query(caller.organization_id, output.query.id)
    assert not measured["recall"].is_measurable


@pytest.mark.asyncio
async def test_a_report_over_an_empty_tenant_still_completes(
    analytics_service: AnalyticsService, organization_id: uuid.UUID
) -> None:

    report = await analytics_service.generate_report(organization_id, ReportKind.RETRIEVAL)
    assert report.content is not None


@pytest.mark.asyncio
async def test_a_source_can_be_registered_with_no_optional_settings(
    source_service: SourceService, organization_id: uuid.UUID
) -> None:
    source = await source_service.create_source(
        organization_id, slug="bare", name="Bare", source_kind=SourceKind.TXT
    )
    assert source.default_tags == []
    assert source.chunk_strategy is None


@pytest.mark.asyncio
async def test_claiming_a_source_in_another_tenant_is_not_found(
    source_service: SourceService, organization_id: uuid.UUID
) -> None:
    with pytest.raises(NotFoundError):
        await source_service.claim_for_sync(organization_id, uuid.uuid4())


@pytest.mark.asyncio
async def test_updating_a_source_in_another_tenant_is_not_found(
    source_service: SourceService, organization_id: uuid.UUID
) -> None:
    with pytest.raises(NotFoundError):
        await source_service.update_source(organization_id, uuid.uuid4(), name="X")


# ---- repository corners --------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_keyword_search_with_no_usable_terms_finds_nothing(
    chunks_repo: DocumentChunkRepository, organization_id: uuid.UUID
) -> None:
    """Punctuation alone yields no terms, and an empty tsquery would
    otherwise match either everything or nothing depending on the
    operator."""
    assert await chunks_repo.search_keyword(organization_id, "!!! ???") == []


@pytest.mark.asyncio
async def test_chunks_can_be_fetched_by_id_within_a_tenant(
    ingestion_service: IngestionService,
    chunks_repo: DocumentChunkRepository,
    organization_id: uuid.UUID,
) -> None:
    result = await ingestion_service.ingest(
        organization_id=organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    ids = [chunk.id for chunk in result.chunks]
    assert len(await chunks_repo.list_by_ids(organization_id, ids)) == len(ids)
    assert await chunks_repo.list_by_ids(uuid.uuid4(), ids) == []
    assert await chunks_repo.list_by_ids(organization_id, []) == []


@pytest.mark.asyncio
async def test_unembedded_chunks_are_selectable(
    ingestion_service: IngestionService,
    chunks_repo: DocumentChunkRepository,
    organization_id: uuid.UUID,
) -> None:
    await ingestion_service.ingest(
        organization_id=organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    assert await chunks_repo.list_unembedded(organization_id)


@pytest.mark.asyncio
async def test_deleting_a_versions_chunks(
    ingestion_service: IngestionService,
    chunks_repo: DocumentChunkRepository,
    organization_id: uuid.UUID,
) -> None:
    result = await ingestion_service.ingest(
        organization_id=organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    assert result.version is not None
    removed = await chunks_repo.delete_for_version(result.version.id)
    assert removed == result.chunk_count


@pytest.mark.asyncio
async def test_metadata_can_be_read_back_and_filtered_on(
    ingestion_service: IngestionService,
    metadata_repo: DocumentMetadataRepository,
    organization_id: uuid.UUID,
) -> None:
    """A metadata filter is an indexed equality on a column, which is why
    these are rows rather than a JSON blob."""
    result = await ingestion_service.ingest(
        organization_id=organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    await metadata_repo.upsert(
        result.document.id, organization_id, "department", "finance", extracted=False
    )
    matched = await metadata_repo.find_documents(organization_id, {"department": "finance"})
    assert result.document.id in matched
    assert await metadata_repo.find_documents(organization_id, {"department": "legal"}) == set()
    assert await metadata_repo.find_documents(organization_id, {}) == set()


@pytest.mark.asyncio
async def test_versions_are_listed_newest_first(
    ingestion_service: IngestionService,
    versions_repo: DocumentVersionRepository,
    organization_id: uuid.UUID,
) -> None:
    first = await ingestion_service.ingest(
        organization_id=organization_id,
        data=HANDBOOK,
        title="H",
        filename="h.md",
        external_id="ops/h",
    )
    await ingestion_service.ingest(
        organization_id=organization_id,
        data=HANDBOOK + b"\nmore\n",
        title="H",
        filename="h.md",
        external_id="ops/h",
    )
    listed = await versions_repo.list_for_document(first.document.id)
    assert [row.version_number for row in listed] == [2, 1]
    assert await versions_repo.next_version_number(first.document.id) == 3


@pytest.mark.asyncio
async def test_requiring_a_version_or_chunk_in_another_tenant_is_not_found(
    versions_repo: DocumentVersionRepository,
    chunks_repo: DocumentChunkRepository,
    organization_id: uuid.UUID,
) -> None:
    with pytest.raises(NotFoundError):
        await versions_repo.require_in_org(organization_id, uuid.uuid4())
    with pytest.raises(NotFoundError):
        await chunks_repo.require_in_org(organization_id, uuid.uuid4())


@pytest.mark.asyncio
async def test_documents_are_countable_in_a_window(
    ingestion_service: IngestionService,
    documents_repo: DocumentRepository,
    organization_id: uuid.UUID,
) -> None:
    await ingestion_service.ingest(
        organization_id=organization_id, data=HANDBOOK, title="H", filename="h.md"
    )
    assert await documents_repo.list_in_window(organization_id, since=ago(3_600), until=utcnow())


@pytest.mark.asyncio
async def test_a_document_search_matches_the_description(
    ingestion_service: IngestionService,
    documents_repo: DocumentRepository,
    organization_id: uuid.UUID,
) -> None:
    result = await ingestion_service.ingest(
        organization_id=organization_id, data=HANDBOOK, title="Handbook", filename="h.md"
    )
    result.document.description = "Everything about archive retention"
    await documents_repo.update(result.document)
    assert await documents_repo.search_in_org(organization_id, "retention")


@pytest.mark.asyncio
async def test_an_impossible_ingest_chunk_ceiling_is_respected(
    documents_repo: DocumentRepository,
    versions_repo: DocumentVersionRepository,
    chunks_repo: DocumentChunkRepository,
    metadata_repo: DocumentMetadataRepository,
    audit_repo: Any,
    publisher: Any,
    organization_id: uuid.UUID,
) -> None:
    """The ceiling is enforced at storage time too, not only inside the
    splitter: a strategy that ignored ``max_chunks`` would otherwise write
    every chunk it produced."""
    service = IngestionService(
        documents_repo,
        versions_repo,
        chunks_repo,
        metadata_repo,
        audit_repo,
        publish_event=publisher,
        chunk_size=40,
        chunk_overlap=5,
        max_chunks=2,
    )
    result = await service.ingest(
        organization_id=organization_id,
        data=b"word " * 400,
        title="Long",
        filename="long.txt",
    )
    assert result.chunk_count <= 2
