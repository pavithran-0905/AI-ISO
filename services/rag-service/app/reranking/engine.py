"""Reranking (docs/062 "RERANKING").

Reordering a candidate set using signals the first-stage retrieval could
not use. Vector search knows only the embedding; it does not know that a
document is three years stale, that it is a table when the query asks for
a procedure, or that four of the top five chunks are the same paragraph
from four near-duplicate documents.

**What is implemented and what is not, stated plainly.**

Implemented, and deterministic functions of data already on the chunk
row: metadata affinity, freshness, access priority, confidence,
diversity (MMR), and their hybrid combination. Every one is exactly
testable.

Not implemented: ``CROSS_ENCODER``. A cross-encoder scores each
(query, chunk) pair through a transformer, which needs a model this
service does not ship and cannot fetch at import time. It is declared in
:class:`~app.models.enums.RerankMethod` and refused here with an
explanatory error rather than silently falling through to something
else -- a reranker that quietly did nothing would look like a working
one.

``LLM`` reranking is supported through an injected scorer, so a caller
that already has a model client can supply one. This service holds no
provider credential of its own, exactly as prompt-management-service
does not.

**Reranking only ever reorders.** It never adds a candidate the first
stage did not return, and never drops one except through an explicit
top-k cut. A reranker that could introduce documents would be a second
retrieval stage with none of the access control the first one applied.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from app.models.enums import ChunkKind, RerankMethod, classification_rank

HALF_LIFE_DAYS = 180.0
"""Freshness halves every six months. Chosen because operational
documentation -- runbooks, configuration, incident notes -- is the
dominant content here, and it decays on that order. Reference material
does not, which is why freshness is one weighted signal among several
rather than a filter."""

DEFAULT_DIVERSITY_LAMBDA = 0.7
"""MMR's trade-off: 1.0 is pure relevance, 0.0 is pure diversity. 0.7
keeps relevance dominant while still breaking up runs of near-identical
chunks."""


@dataclass(frozen=True, slots=True)
class Candidate:
    """One chunk being considered, with the signals a reranker can use."""

    key: str
    score: float
    rank: int
    content: str = ""
    document_id: str = ""
    chunk_kind: ChunkKind = ChunkKind.TEXT
    updated_at: datetime | None = None
    classification: str = "internal"
    metadata: Mapping[str, str] = field(default_factory=dict)
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class RerankedCandidate:
    """One candidate after reranking, with its movement recorded."""

    key: str
    score: float
    rank: int
    rank_before: int
    score_before: float
    method: RerankMethod
    signals: dict[str, float] = field(default_factory=dict)

    @property
    def moved(self) -> int:
        """How far it moved. Positive is up, negative is down.

        Persisted into ``reranking_results`` so a reranker that never
        changes an order -- and is therefore pure latency -- is visible
        rather than assumed useful.
        """
        return self.rank_before - self.rank


def freshness_score(updated_at: datetime | None, *, now: datetime | None = None) -> float:
    """Exponential decay on age, in ``[0, 1]``.

    ``0.5`` at one half-life, approaching zero for very old content.
    Undated content scores ``0.5`` rather than ``0.0``: absence of a date
    is not evidence of staleness, and scoring it as stale would bury
    every document whose source did not carry a timestamp.
    """
    if updated_at is None:
        return 0.5
    moment = now or datetime.now(UTC)
    reference = updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=UTC)
    age_days = max((moment - reference).total_seconds() / 86_400.0, 0.0)
    return math.pow(0.5, age_days / HALF_LIFE_DAYS)


def metadata_score(candidate: Candidate, filters: Mapping[str, str]) -> float:
    """How well a candidate's metadata matches what was asked for.

    Returns ``1.0`` when nothing was asked for -- an unfiltered query
    should not reorder on metadata at all, and returning ``0.0`` would
    make every candidate equally bad, which is the same as returning
    ``1.0`` but harder to read.
    """
    if not filters:
        return 1.0
    matched = sum(1 for key, value in filters.items() if candidate.metadata.get(key) == value)
    return matched / len(filters)


def access_priority_score(candidate: Candidate) -> float:
    """Prefer the least restrictive content among equals.

    **Not an access check.** Filtering out what a caller may not see
    happens before reranking, in the retrieval query itself -- doing it
    here would mean unauthorised chunks were fetched, scored, and only
    then dropped, which leaks their existence through timing and counts.
    This only breaks ties: given two equally relevant chunks, the one
    that is easier to share is the better answer.
    """
    rank = classification_rank(candidate.classification)
    return 1.0 - (rank / 4.0)


def confidence_score(candidate: Candidate) -> float:
    """The candidate's own stated confidence, or its retrieval score.

    Falls back to the first-stage score clamped into ``[0, 1]`` when no
    explicit confidence was supplied, so the signal is always present
    rather than sometimes absent.
    """
    if candidate.confidence is not None:
        return min(max(candidate.confidence, 0.0), 1.0)
    return min(max(candidate.score, 0.0), 1.0)


_MIN_SIMILARITY_TOKEN_LENGTH = 3
"""Shorter words are function words that every chunk shares, so counting
them would make any two English paragraphs look like near-duplicates."""


def _tokens(text: str) -> set[str]:
    return {word for word in text.lower().split() if len(word) >= _MIN_SIMILARITY_TOKEN_LENGTH}


def _similarity(left: str, right: str) -> float:
    """Jaccard overlap, used only to detect near-duplicates for MMR."""
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def diversify(
    candidates: Sequence[Candidate], *, limit: int, lambda_: float = DEFAULT_DIVERSITY_LAMBDA
) -> list[Candidate]:
    """Maximal Marginal Relevance: relevance minus redundancy.

    Greedily picks the candidate maximising
    ``lambda * relevance - (1 - lambda) * max_similarity_to_already_picked``.

    This is what stops a context window filling with four copies of the
    same paragraph from four near-duplicate documents -- a failure that
    looks fine in the ranking and wastes most of the token budget.

    Raises:
        ValueError: If *limit* is not positive or *lambda_* is outside
            ``[0, 1]``.
    """
    if limit < 1:
        raise ValueError(f"limit must be at least 1, got {limit!r}.")
    if not 0.0 <= lambda_ <= 1.0:
        raise ValueError(f"lambda_ must be within [0, 1], got {lambda_!r}.")

    remaining = list(candidates)
    if not remaining:
        return []

    scores = [candidate.score for candidate in remaining]
    low, high = min(scores), max(scores)
    spread = high - low
    relevance = {
        candidate.key: ((candidate.score - low) / spread if spread > 0 else 1.0)
        for candidate in remaining
    }

    selected: list[Candidate] = []
    while remaining and len(selected) < limit:
        best: Candidate | None = None
        best_value = -math.inf
        for candidate in remaining:
            redundancy = max(
                (_similarity(candidate.content, chosen.content) for chosen in selected),
                default=0.0,
            )
            value = lambda_ * relevance[candidate.key] - (1.0 - lambda_) * redundancy
            if value > best_value:
                best, best_value = candidate, value
        if best is None:  # pragma: no cover - remaining is non-empty here
            break
        selected.append(best)
        remaining.remove(best)
    return selected


_SIGNALS: dict[RerankMethod, Callable[[Candidate, Mapping[str, str]], float]] = {
    RerankMethod.METADATA: metadata_score,
    RerankMethod.FRESHNESS: lambda candidate, _filters: freshness_score(candidate.updated_at),
    RerankMethod.ACCESS_PRIORITY: lambda candidate, _filters: access_priority_score(candidate),
    RerankMethod.CONFIDENCE: lambda candidate, _filters: confidence_score(candidate),
}

HYBRID_WEIGHTS: dict[RerankMethod, float] = {
    RerankMethod.CONFIDENCE: 0.55,
    RerankMethod.FRESHNESS: 0.20,
    RerankMethod.METADATA: 0.15,
    RerankMethod.ACCESS_PRIORITY: 0.10,
}
"""Confidence dominates deliberately. The first-stage score is the only
signal that actually measures whether a chunk answers the question; the
rest are tie-breakers, and letting them outvote relevance would produce
a list that is fresh, well-labelled, and wrong."""


def rerank(
    candidates: Sequence[Candidate],
    *,
    method: RerankMethod = RerankMethod.HYBRID,
    limit: int | None = None,
    filters: Mapping[str, str] | None = None,
    lambda_: float = DEFAULT_DIVERSITY_LAMBDA,
    llm_scorer: Callable[[Sequence[Candidate]], Mapping[str, float]] | None = None,
) -> list[RerankedCandidate]:
    """Reorder *candidates* by *method*.

    Raises:
        NotImplementedError: For ``CROSS_ENCODER``, which needs a model
            this service does not ship. Refused explicitly rather than
            silently falling back, because a reranker that quietly did
            nothing is indistinguishable from a working one.
        ValueError: If ``LLM`` is requested with no ``llm_scorer``.
    """
    chosen = RerankMethod(method)
    ordered = sorted(candidates, key=lambda item: (item.rank, item.key))
    if not ordered:
        return []

    if chosen is RerankMethod.CROSS_ENCODER:
        raise NotImplementedError(
            "Cross-encoder reranking needs a transformer model this service does "
            "not ship and cannot fetch at import time. Use HYBRID, or supply an "
            "llm_scorer and request LLM."
        )

    active = dict(filters or {})
    cut = limit if limit is not None else len(ordered)
    if cut < 1:
        raise ValueError(f"limit must be at least 1, got {limit!r}.")

    if chosen is RerankMethod.DIVERSITY:
        picked = diversify(ordered, limit=cut, lambda_=lambda_)
        return _finalise(picked, ordered, chosen, {c.key: {"diversity": 1.0} for c in picked})

    if chosen is RerankMethod.LLM:
        if llm_scorer is None:
            raise ValueError(
                "LLM reranking requires an llm_scorer; this service holds no model "
                "provider credential of its own."
            )
        judged = llm_scorer(ordered)
        scored = {
            candidate.key: min(max(judged.get(candidate.key, candidate.score), 0.0), 1.0)
            for candidate in ordered
        }
        signals = {key: {"llm": value} for key, value in scored.items()}
        return _finalise(_by_score(ordered, scored, cut), ordered, chosen, signals)

    if chosen is RerankMethod.HYBRID:
        signals: dict[str, dict[str, float]] = {}
        scored = {}
        for candidate in ordered:
            parts = {str(name): _SIGNALS[name](candidate, active) for name in HYBRID_WEIGHTS}
            signals[candidate.key] = parts
            scored[candidate.key] = sum(
                HYBRID_WEIGHTS[name] * parts[str(name)] for name in HYBRID_WEIGHTS
            )
        return _finalise(_by_score(ordered, scored, cut), ordered, chosen, signals)

    signal = _SIGNALS[chosen]
    scored = {candidate.key: signal(candidate, active) for candidate in ordered}
    signals = {key: {str(chosen): value} for key, value in scored.items()}
    return _finalise(_by_score(ordered, scored, cut), ordered, chosen, signals)


def _by_score(
    candidates: Sequence[Candidate], scores: Mapping[str, float], limit: int
) -> list[Candidate]:
    """Order by score, breaking ties on the original rank.

    Tie-breaking on the incoming rank rather than the key preserves the
    first stage's judgement wherever the reranker has no opinion, which
    is the conservative choice: a reranker should not shuffle what it
    cannot distinguish.
    """
    return sorted(candidates, key=lambda item: (-scores[item.key], item.rank, item.key))[:limit]


def _finalise(
    picked: Sequence[Candidate],
    original: Sequence[Candidate],
    method: RerankMethod,
    signals: Mapping[str, Mapping[str, float]],
) -> list[RerankedCandidate]:
    """Attach final ranks and record where each candidate came from."""
    before = {candidate.key: candidate for candidate in original}
    return [
        RerankedCandidate(
            key=candidate.key,
            score=sum(signals.get(candidate.key, {}).values()),
            rank=index + 1,
            rank_before=before[candidate.key].rank,
            score_before=before[candidate.key].score,
            method=method,
            signals=dict(signals.get(candidate.key, {})),
        )
        for index, candidate in enumerate(picked)
    ]


def with_rank(candidates: Sequence[Candidate]) -> list[Candidate]:
    """Assign 1-based ranks by descending score."""
    ordered = sorted(candidates, key=lambda item: (-item.score, item.key))
    return [replace(candidate, rank=index + 1) for index, candidate in enumerate(ordered)]


__all__ = [
    "DEFAULT_DIVERSITY_LAMBDA",
    "HALF_LIFE_DAYS",
    "HYBRID_WEIGHTS",
    "Candidate",
    "RerankedCandidate",
    "access_priority_score",
    "confidence_score",
    "diversify",
    "freshness_score",
    "metadata_score",
    "rerank",
    "with_rank",
]
