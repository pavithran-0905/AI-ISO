"""The pure engines: tokens, chunking, BM25, fusion, metrics, reranking,
context assembly.

Every module here is a pure function over its inputs -- no I/O, no model
call -- which is what makes chunking and ranking regressions detectable at
all. A change in any of them silently changes retrieval quality, and these
are the only tests that would notice.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.chunking.splitter import (
    DEFAULT_CHUNK_SIZE,
    Chunk,
    ChunkingConfig,
    chunk_text,
    rechunk_needed,
)
from app.chunking.tokens import estimate_tokens, fits_within, truncate_to_tokens
from app.context.assembler import (
    ContextChunk,
    assemble,
    deduplicate,
    order_for_reading,
    similarity,
)
from app.evaluation.metrics import (
    citation_accuracy,
    dcg_at_k,
    evaluate_retrieval,
    f1,
    grounding_score,
    hit_rate_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.hybrid_search import bm25
from app.hybrid_search.fusion import (
    DEFAULT_RRF_K,
    RankedItem,
    fuse,
    max_score_fusion,
    reciprocal_rank_fusion,
    to_ranked,
    weighted_fusion,
)
from app.models.enums import ChunkKind, ChunkStrategy, FusionMethod, RerankMethod
from app.reranking.engine import (
    Candidate,
    access_priority_score,
    confidence_score,
    diversify,
    freshness_score,
    metadata_score,
    rerank,
)

# ---- tokens -----------------------------------------------------------------


def test_an_empty_string_costs_nothing_but_whitespace_costs_one() -> None:
    """Nothing to embed is genuinely free; whitespace is a real character
    the tokenizer will see, and floor-of-one keeps a chunk of it from
    letting a budget admit infinitely many."""
    assert estimate_tokens("") == 0
    assert estimate_tokens("   ") == 1


def test_longer_text_costs_more() -> None:
    short = estimate_tokens("backup")
    long = estimate_tokens("backup and restore procedure for the archive bucket")
    assert long > short


def test_long_words_cost_more_than_their_word_count() -> None:
    """A long word is several sub-tokens, and pretending otherwise
    under-counts exactly the technical vocabulary this service ingests."""
    assert estimate_tokens("internationalisation") > estimate_tokens("cat dog")


def test_non_ascii_costs_more_than_ascii_of_the_same_length() -> None:
    assert estimate_tokens("日本語のテキスト") > estimate_tokens("abcdefgh")


@pytest.mark.parametrize(("text", "budget"), [("short", 100), ("", 1)])
def test_fits_within_accepts_what_fits(text: str, budget: int) -> None:
    assert fits_within(text, budget=budget)


def test_fits_within_rejects_what_does_not() -> None:
    assert not fits_within("word " * 500, budget=10)


def test_truncate_respects_the_budget() -> None:
    truncated = truncate_to_tokens("word " * 200, budget=20)
    assert estimate_tokens(truncated) <= 20
    assert truncated


def test_truncating_something_that_fits_changes_nothing() -> None:
    assert truncate_to_tokens("a short line", budget=500) == "a short line"


# ---- chunking ---------------------------------------------------------------


MARKDOWN = (
    "# Handbook\n\n"
    "## Backups\n\n"
    "The nightly backup runs at 02:00 UTC and writes to the archive bucket.\n\n"
    "## Restore\n\n"
    "Select the snapshot and run the restore job. Verify the checksum first.\n"
)


def test_empty_text_produces_no_chunks() -> None:
    """Not one empty chunk: an embedding of "" is a real vector that
    matches queries for no reason."""
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


@pytest.mark.parametrize("strategy", list(ChunkStrategy))
def test_every_strategy_produces_usable_chunks(strategy: ChunkStrategy) -> None:
    chunks = chunk_text(MARKDOWN, ChunkingConfig(strategy=strategy, chunk_size=120, overlap=20))
    assert chunks
    assert all(chunk.content.strip() for chunk in chunks)
    assert [c.sequence for c in chunks] == list(range(len(chunks)))


def test_heading_chunking_carries_the_heading_trail() -> None:
    chunks = chunk_text(
        MARKDOWN, ChunkingConfig(strategy=ChunkStrategy.HEADING, chunk_size=400, overlap=40)
    )
    trails = [chunk.section_label for chunk in chunks if chunk.section_label]
    assert any(trail == "Handbook > Backups" for trail in trails), trails


def test_fixed_size_chunking_respects_the_window() -> None:
    text = "word " * 400
    chunks = chunk_text(
        text, ChunkingConfig(strategy=ChunkStrategy.FIXED_SIZE, chunk_size=100, overlap=10)
    )
    assert len(chunks) > 1
    assert all(len(chunk.content) <= 100 for chunk in chunks)


def test_sliding_window_chunks_overlap() -> None:
    text = "sentence one here. sentence two here. sentence three here. " * 8
    chunks = chunk_text(
        text, ChunkingConfig(strategy=ChunkStrategy.SLIDING_WINDOW, chunk_size=120, overlap=40)
    )
    assert len(chunks) > 1
    assert any(chunk.overlap_tokens > 0 for chunk in chunks[1:])


def test_code_aware_chunking_keeps_a_fence_whole() -> None:
    """A code block cut in half is invalid as code but is still embedded
    as if it were code."""
    fence = "```python\n" + "\n".join(f"line_{n} = {n}" for n in range(40)) + "\n```"
    chunks = chunk_text(
        f"Intro paragraph.\n\n{fence}\n\nTrailing paragraph.",
        ChunkingConfig(strategy=ChunkStrategy.CODE_AWARE, chunk_size=100, overlap=10),
    )
    code_chunks = [c for c in chunks if c.kind == ChunkKind.CODE]
    assert code_chunks
    assert all(chunk.content.count("```") % 2 == 0 for chunk in code_chunks)


def test_table_aware_chunking_keeps_a_table_whole() -> None:
    table = "\n".join(["| a | b |", "| - | - |", *[f"| {n} | {n * 2} |" for n in range(30)]])
    chunks = chunk_text(
        f"Before.\n\n{table}\n\nAfter.",
        ChunkingConfig(strategy=ChunkStrategy.TABLE_AWARE, chunk_size=80, overlap=10),
    )
    assert any(chunk.kind == ChunkKind.TABLE for chunk in chunks)


def test_chunk_offsets_index_into_the_original_text() -> None:
    chunks = chunk_text(
        MARKDOWN, ChunkingConfig(strategy=ChunkStrategy.PARAGRAPH, chunk_size=400, overlap=40)
    )
    for chunk in chunks:
        assert 0 <= chunk.start <= chunk.end <= len(MARKDOWN)


def test_max_chunks_is_a_ceiling() -> None:
    chunks = chunk_text(
        "word " * 5_000,
        ChunkingConfig(strategy=ChunkStrategy.FIXED_SIZE, chunk_size=20, overlap=5, max_chunks=7),
    )
    assert len(chunks) <= 7


@pytest.mark.parametrize(
    ("size", "overlap"),
    [(0, 0), (100, 100), (100, 150), (100, -1)],
)
def test_an_impossible_chunking_config_is_refused_at_construction(size: int, overlap: int) -> None:
    """Refused when built, not when split: discovering it halfway through
    a ten-thousand-chunk ingestion is worse."""
    with pytest.raises(ValueError, match=r"chunk_size|overlap"):
        ChunkingConfig(chunk_size=size, overlap=overlap)


def test_max_chunks_below_one_is_refused() -> None:
    with pytest.raises(ValueError, match="max_chunks"):
        ChunkingConfig(max_chunks=0)


def test_a_chunk_reports_its_own_size() -> None:
    chunk = Chunk(sequence=0, content="hello there", start=0, end=11)
    assert chunk.character_count == 11
    assert chunk.token_estimate >= 1
    assert chunk.section_label is None


def test_rechunk_is_needed_only_when_the_result_would_differ() -> None:
    """Compares the chunks a config would produce, not the config itself:
    two different configs that happen to split a short document
    identically require no re-embedding, and re-embedding identical chunks
    is the largest avoidable cost in this service."""
    base = ChunkingConfig(chunk_size=500, overlap=50)
    produced = chunk_text(MARKDOWN, base)
    assert not rechunk_needed(produced, MARKDOWN, base)
    assert rechunk_needed(produced, MARKDOWN, ChunkingConfig(chunk_size=60, overlap=10))
    extended = f"{MARKDOWN}\n## Escalation\n\nPage the on-call engineer.\n"
    assert rechunk_needed(produced, extended, base)


def test_the_default_chunk_size_is_what_the_config_uses() -> None:
    assert ChunkingConfig().chunk_size == DEFAULT_CHUNK_SIZE


# ---- BM25 -------------------------------------------------------------------


CORPUS = [
    ("a", "the nightly backup writes to the archive bucket"),
    ("b", "restore the snapshot and verify the checksum"),
    ("c", "the production vpc spans three availability zones"),
]


def test_tokenize_lowercases_and_drops_punctuation() -> None:
    assert bm25.tokenize("Backup, Restore!") == ["backup", "restore"]


def test_tokenize_keeps_hyphenated_identifiers_whole() -> None:
    """``on-call`` is one term in this corpus, not two."""
    assert "on-call" in bm25.tokenize("page the on-call engineer")


def test_bm25_ranks_the_matching_document_first() -> None:
    index = bm25.build_index(CORPUS)
    top = index.top("restore the snapshot checksum", limit=3)
    assert top[0].doc_id == "b"
    assert top[0].score > 0


def test_bm25_reports_which_terms_matched() -> None:
    index = bm25.build_index(CORPUS)
    scored = {row.doc_id: row for row in index.score("archive bucket")}
    assert scored["a"].matched
    assert set(scored["a"].matched_terms) == {"archive", "bucket"}
    assert not scored["c"].matched


def test_an_empty_index_scores_nothing() -> None:
    index = bm25.Bm25Index()
    assert index.document_count == 0
    assert index.average_length == 0.0
    assert index.score("anything") == []


def test_a_term_in_every_document_still_has_a_positive_idf() -> None:
    """Smoothed IDF: the raw formula goes negative once a term appears in
    more than half the corpus, which would let a common word push a
    document's score *down*."""
    index = bm25.build_index([("a", "backup"), ("b", "backup"), ("c", "backup")])
    assert index.inverse_document_frequency("backup") > 0


def test_an_unseen_term_contributes_nothing() -> None:
    index = bm25.build_index(CORPUS)
    assert all(row.score == 0.0 for row in index.score("quantum tariffs"))


def test_rank_is_the_one_call_form_of_build_then_top() -> None:
    assert [row.doc_id for row in bm25.rank("archive bucket", CORPUS, limit=1)] == ["a"]


def test_add_many_matches_repeated_add() -> None:
    one = bm25.Bm25Index()
    one.add_many(CORPUS)
    other = bm25.Bm25Index()
    for doc_id, text in CORPUS:
        other.add(doc_id, text)
    assert one.document_count == other.document_count == 3


# ---- fusion -----------------------------------------------------------------


ARM_ONE = to_ranked([("x", 0.9), ("y", 0.5), ("z", 0.1)])
ARM_TWO = to_ranked([("y", 0.8), ("x", 0.4)])


def test_to_ranked_numbers_from_one() -> None:
    """1-based, matching how ranks are stored and cited; RRF's
    ``1/(k+rank)`` would weight a 0-based top hit differently."""
    assert [item.rank for item in ARM_ONE] == [1, 2, 3]


def test_rrf_prefers_what_both_arms_found() -> None:
    fused = reciprocal_rank_fusion({"one": ARM_ONE, "two": ARM_TWO})
    assert {item.key for item in fused[:2]} == {"x", "y"}
    assert fused[0].arm_count == 2


def test_rrf_records_where_each_contribution_came_from() -> None:
    """A fused number with nothing behind it is unauditable."""
    fused = {item.key: item for item in reciprocal_rank_fusion({"one": ARM_ONE, "two": ARM_TWO})}
    assert fused["x"].source_ranks == {"one": 1, "two": 2}
    assert set(fused["x"].arms) == {"one", "two"}
    assert pytest.approx(fused["x"].contributions["one"]) == 1.0 / (DEFAULT_RRF_K + 1)


def test_weighted_fusion_follows_its_weights() -> None:
    heavy_one = weighted_fusion({"one": ARM_ONE, "two": ARM_TWO}, {"one": 1.0, "two": 0.0})
    heavy_two = weighted_fusion({"one": ARM_ONE, "two": ARM_TWO}, {"one": 0.0, "two": 1.0})
    assert heavy_one[0].key == "x"
    assert heavy_two[0].key == "y"


def test_a_negative_weight_is_refused() -> None:
    """A negative weight would make an arm's agreement count *against* an
    item, which is not a weighting -- it is a sign error nobody would spot
    in the output."""
    with pytest.raises(ValueError, match="must not be negative"):
        weighted_fusion({"one": ARM_ONE}, {"one": -1.0})


def test_weighted_fusion_with_no_weight_for_an_arm_ignores_it() -> None:
    fused = weighted_fusion({"one": ARM_ONE, "two": ARM_TWO}, {"one": 1.0})
    assert fused[0].key == "x"


def test_max_score_fusion_takes_the_best_single_arm() -> None:
    fused = {item.key: item.score for item in max_score_fusion({"one": ARM_ONE, "two": ARM_TWO})}
    assert fused["x"] >= fused["z"]


def test_fuse_dispatches_on_method() -> None:
    for method in FusionMethod:
        weights = {"one": 0.5, "two": 0.5} if method is FusionMethod.WEIGHTED_SCORE else None
        fused = fuse({"one": ARM_ONE, "two": ARM_TWO}, method=method, weights=weights)
        assert fused
        assert [item.rank for item in fused] == list(range(1, len(fused) + 1))


def test_fusing_nothing_yields_nothing() -> None:
    assert fuse({}) == []
    assert reciprocal_rank_fusion({"one": []}) == []


def test_a_single_arm_keeps_its_own_order() -> None:
    fused = reciprocal_rank_fusion({"only": ARM_ONE})
    assert [item.key for item in fused] == ["x", "y", "z"]


def test_ranked_items_can_be_built_from_pairs() -> None:
    assert to_ranked([]) == []
    assert to_ranked([("k", 1.0)]) == [RankedItem(key="k", score=1.0, rank=1)]


# ---- metrics ----------------------------------------------------------------


RETRIEVED = ["a", "b", "c", "d"]
RELEVANT = {"a", "c"}


def test_precision_counts_the_hits_among_what_was_returned() -> None:
    assert precision_at_k(RETRIEVED, RELEVANT, k=4).value == 0.5


def test_recall_counts_the_hits_among_what_exists() -> None:
    assert recall_at_k(RETRIEVED, RELEVANT, k=4).value == 1.0


def test_hit_rate_is_binary() -> None:
    assert hit_rate_at_k(RETRIEVED, RELEVANT, k=1).value == 1.0
    assert hit_rate_at_k(["z"], RELEVANT, k=1).value == 0.0


def test_reciprocal_rank_rewards_an_early_hit() -> None:
    assert reciprocal_rank(RETRIEVED, RELEVANT, k=4).value == 1.0
    assert reciprocal_rank(["z", "a"], RELEVANT, k=4).value == 0.5


def test_an_unmeasurable_metric_is_not_a_zero() -> None:
    """One says retrieval failed, the other says nobody has judged it."""
    empty = precision_at_k([], RELEVANT, k=4)
    assert empty.value == 0.0
    assert not empty.is_measurable
    assert precision_at_k(RETRIEVED, RELEVANT, k=4).is_measurable


def test_recall_against_no_ground_truth_is_unmeasurable() -> None:
    assert not recall_at_k(RETRIEVED, set(), k=4).is_measurable


def test_ndcg_rewards_putting_the_best_first() -> None:
    gains = {"a": 1.0, "c": 0.5}
    good = ndcg_at_k(["a", "c", "b"], gains, k=3).value
    bad = ndcg_at_k(["b", "c", "a"], gains, k=3).value
    assert good > bad
    assert good == pytest.approx(1.0)


def test_dcg_is_zero_when_nothing_is_relevant() -> None:
    assert dcg_at_k(["x", "y"], {"a": 1.0}, k=2) == 0.0


def test_mean_reciprocal_rank_averages_only_the_judged() -> None:
    """A query nobody judged is excluded rather than scored zero:
    including it would drive the metric down in proportion to how little
    feedback exists."""
    result = mean_reciprocal_rank([(RETRIEVED, RELEVANT), (["z"], set())], k=4)
    assert result.value == 1.0
    assert result.considered == 1


def test_mean_reciprocal_rank_over_nothing_is_unmeasurable() -> None:
    assert not mean_reciprocal_rank([], k=4).is_measurable


def test_citation_accuracy_counts_the_citations_that_resolve() -> None:
    assert citation_accuracy(["1", "2"], {"1", "2"}).value == 1.0
    assert citation_accuracy(["1", "9"], {"1"}).value == 0.5
    assert not citation_accuracy([], {"1"}).is_measurable


def test_grounding_measures_how_much_of_an_answer_came_from_context() -> None:
    assert grounding_score(["backup", "restore"], {"backup", "restore"}).value == 1.0
    assert grounding_score(["backup", "invented"], {"backup"}).value == 0.5
    assert not grounding_score([], {"backup"}).is_measurable


def test_f1_balances_precision_and_recall() -> None:
    assert f1(1.0, 1.0) == 1.0
    assert f1(0.0, 1.0) == 0.0
    assert f1(0.5, 0.5) == pytest.approx(0.5)


def test_evaluate_retrieval_returns_every_metric() -> None:
    measured = evaluate_retrieval(RETRIEVED, RELEVANT, k=4)
    assert set(measured) == {"precision", "recall", "hit_rate", "mrr", "ndcg"}


def test_evaluate_retrieval_accepts_graded_relevance() -> None:
    measured = evaluate_retrieval(RETRIEVED, RELEVANT, k=4, gains={"a": 1.0, "c": 0.2})
    assert measured["ndcg"].is_measurable


@pytest.mark.parametrize("k", [0, -1])
def test_a_non_positive_k_is_refused(k: int) -> None:
    with pytest.raises(ValueError, match="k must"):
        precision_at_k(RETRIEVED, RELEVANT, k=k)


# ---- reranking --------------------------------------------------------------


def _candidate(key: str, rank: int, **kwargs: object) -> Candidate:
    defaults: dict[str, object] = {
        "key": key,
        "score": 1.0 / rank,
        "rank": rank,
        "content": f"chunk {key} about backups and restores",
        "document_id": f"doc-{key}",
    }
    defaults.update(kwargs)
    return Candidate(**defaults)  # type: ignore[arg-type]


CANDIDATES = [_candidate("a", 1), _candidate("b", 2), _candidate("c", 3)]


def test_freshness_prefers_recent_content() -> None:
    now = datetime.now(UTC)
    assert freshness_score(now, now=now) > freshness_score(now - timedelta(days=365), now=now)


def test_content_with_no_date_is_not_penalised_to_zero() -> None:
    """Unknown is not stale; scoring it zero would bury every document
    whose source never recorded a date."""
    assert 0.0 < freshness_score(None) <= 1.0


def test_metadata_score_rewards_matching_filters() -> None:
    candidate = _candidate("a", 1, metadata={"department": "finance"})
    assert metadata_score(candidate, {"department": "finance"}) == 1.0
    assert metadata_score(candidate, {"department": "legal"}) == 0.0
    assert metadata_score(candidate, {}) == 1.0


def test_access_priority_prefers_the_least_restrictive() -> None:
    assert access_priority_score(_candidate("a", 1, classification="public")) > (
        access_priority_score(_candidate("b", 2, classification="secret"))
    )


def test_confidence_prefers_an_explicit_value_over_the_raw_score() -> None:
    assert confidence_score(_candidate("a", 1, confidence=0.25)) == 0.25
    assert confidence_score(_candidate("a", 1, score=5.0)) == 1.0
    assert confidence_score(_candidate("a", 1, score=-3.0)) == 0.0


def test_diversify_avoids_returning_near_duplicates() -> None:
    same = "the nightly backup writes to the archive bucket every night"
    candidates = [
        _candidate("a", 1, content=same),
        _candidate("b", 2, content=same),
        _candidate("c", 3, content="the production vpc spans three availability zones"),
    ]
    picked = [c.key for c in diversify(candidates, limit=2)]
    assert "a" in picked
    assert "c" in picked


def test_diversify_of_nothing_is_nothing() -> None:
    assert diversify([], limit=3) == []


@pytest.mark.parametrize(
    "method",
    [m for m in RerankMethod if m not in {RerankMethod.CROSS_ENCODER, RerankMethod.LLM}],
)
def test_every_available_method_returns_a_dense_ranking(method: RerankMethod) -> None:
    ordered = rerank(CANDIDATES, method=method)
    assert [item.rank for item in ordered] == [1, 2, 3]
    assert {item.key for item in ordered} == {"a", "b", "c"}


@pytest.mark.parametrize(
    "method",
    [m for m in RerankMethod if m not in {RerankMethod.CROSS_ENCODER, RerankMethod.LLM}],
)
def test_the_reported_score_is_the_one_that_ordered(method: RerankMethod) -> None:
    """Descending and monotonic with the rank beside it. Reporting a
    different number would let any client sorting on ``score`` undo the
    reranking it just paid for."""
    scores = [item.score for item in rerank(CANDIDATES, method=method)]
    assert scores == sorted(scores, reverse=True), scores


def test_reranking_records_where_each_candidate_started() -> None:
    ordered = {item.key: item for item in rerank(CANDIDATES, method=RerankMethod.CONFIDENCE)}
    assert ordered["a"].rank_before == 1
    assert ordered["a"].method == RerankMethod.CONFIDENCE
    assert ordered["a"].signals


def test_reranking_reports_how_far_each_candidate_moved() -> None:
    """A reranker that never changes an order is pure latency, and that
    is only visible if the movement is recorded."""
    ordered = rerank(CANDIDATES, method=RerankMethod.FRESHNESS)
    assert all(item.moved == item.rank_before - item.rank for item in ordered)


def test_reranking_nothing_yields_nothing() -> None:
    assert rerank([], method=RerankMethod.HYBRID) == []


def test_the_limit_truncates() -> None:
    assert len(rerank(CANDIDATES, method=RerankMethod.HYBRID, limit=2)) == 2


def test_a_limit_below_one_is_refused() -> None:
    with pytest.raises(ValueError, match="limit"):
        rerank(CANDIDATES, limit=0)


def test_a_cross_encoder_rerank_is_refused_rather_than_faked() -> None:
    """A reranker that quietly did nothing is indistinguishable from a
    working one."""
    with pytest.raises(NotImplementedError):
        rerank(CANDIDATES, method=RerankMethod.CROSS_ENCODER)


def test_llm_reranking_without_a_scorer_is_refused() -> None:
    with pytest.raises(ValueError, match="llm_scorer"):
        rerank(CANDIDATES, method=RerankMethod.LLM)


def test_llm_reranking_uses_the_scorer_it_was_given() -> None:
    ordered = rerank(
        CANDIDATES,
        method=RerankMethod.LLM,
        llm_scorer=lambda items: {item.key: 1.0 if item.key == "c" else 0.0 for item in items},
    )
    assert ordered[0].key == "c"


# ---- context assembly -------------------------------------------------------


def _context(key: str, content: str, score: float = 1.0, **kwargs: object) -> ContextChunk:
    defaults: dict[str, object] = {
        "key": key,
        "content": content,
        "score": score,
        "document_id": f"doc-{key}",
        "document_title": f"Doc {key}",
    }
    defaults.update(kwargs)
    return ContextChunk(**defaults)  # type: ignore[arg-type]


def test_similarity_is_one_for_identical_text() -> None:
    assert similarity("backup restore archive", "backup restore archive") == 1.0


def test_similarity_is_zero_for_unrelated_text() -> None:
    assert similarity("backup restore", "quantum tariffs") == 0.0


def test_deduplicate_drops_near_identical_chunks() -> None:
    text = "the nightly backup writes to the archive bucket"
    kept, dropped = deduplicate([_context("a", text), _context("b", text)])
    assert len(kept) == 1
    assert dropped == ["b"]


def test_deduplicate_keeps_distinct_chunks() -> None:
    kept, dropped = deduplicate(
        [_context("a", "backups run nightly"), _context("b", "the vpc spans three zones")]
    )
    assert len(kept) == 2
    assert dropped == []


def test_order_for_reading_groups_a_document_together() -> None:
    """A model reading two halves of one document interleaved with a third
    is reading something nobody wrote."""
    ordered = order_for_reading(
        [
            _context("a1", "first", document_id="doc-1", sequence=0),
            _context("b1", "other", document_id="doc-2", sequence=0),
            _context("a2", "second", document_id="doc-1", sequence=1),
        ]
    )
    documents = [chunk.document_id for chunk in ordered]
    assert documents.index("doc-1") + 1 == documents.index("doc-1", documents.index("doc-1") + 1)


def test_assembly_includes_what_fits_and_names_what_does_not() -> None:
    assembled = assemble(
        [_context("a", "word " * 20), _context("b", "other " * 200)], max_tokens=40
    )
    assert "a" in assembled.included
    assert "b" in assembled.excluded
    assert assembled.token_count <= 40


def test_assembly_labels_and_cites_every_included_chunk() -> None:
    assembled = assemble([_context("a", "backups run nightly")], max_tokens=200)
    assert assembled.citations
    citation = assembled.citations[0]
    assert citation.chunk_key == "a"
    assert "Doc a" in citation.render()
    assert assembled.citation_map == {citation.label: "a"}


def test_the_citation_label_cost_is_charged_against_the_budget() -> None:
    """The ``[1] `` prefix is real text the model pays for; omitting it
    from the count overruns every budget by the number of citations."""
    with_labels = assemble([_context("a", "word " * 30)], max_tokens=500, include_citations=True)
    without = assemble([_context("a", "word " * 30)], max_tokens=500, include_citations=False)
    assert with_labels.token_count >= without.token_count


def test_assembly_reports_its_utilisation() -> None:
    assembled = assemble([_context("a", "word " * 10)], max_tokens=100)
    assert 0.0 < assembled.utilisation <= 1.0
    assert assembled.budget == 100


def test_assembling_nothing_yields_an_empty_block() -> None:
    assembled = assemble([], max_tokens=100)
    assert assembled.text == ""
    assert not assembled.citations
    assert assembled.utilisation == 0.0


def test_a_chunk_that_cannot_fit_is_skipped_not_cut() -> None:
    """A chunk cut mid-sentence can change what it appears to say, and a
    model has no way to know it is reading a fragment."""
    assembled = assemble([_context("a", "word " * 500)], max_tokens=10, allow_partial=False)
    assert assembled.included == []
    assert assembled.excluded == ["a"]


def test_partial_assembly_truncates_when_asked() -> None:
    assembled = assemble([_context("a", "word " * 500)], max_tokens=20, allow_partial=True)
    assert assembled.included == ["a"]
    assert assembled.truncated
    assert assembled.token_count <= 20


def test_a_non_positive_budget_is_refused() -> None:
    with pytest.raises(ValueError, match="max_tokens"):
        assemble([_context("a", "text")], max_tokens=0)


def test_duplicates_are_counted_in_the_result() -> None:
    text = "the nightly backup writes to the archive bucket"
    assembled = assemble([_context("a", text), _context("b", text)], max_tokens=500)
    assert assembled.duplicates_dropped == 1


def test_deduplication_can_be_turned_off() -> None:
    text = "the nightly backup writes to the archive bucket"
    assembled = assemble(
        [_context("a", text), _context("b", text)], max_tokens=500, deduplicate_chunks=False
    )
    assert assembled.duplicates_dropped == 0
    assert len(assembled.included) == 2
