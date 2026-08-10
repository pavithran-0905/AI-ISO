"""Retrieval evaluation metrics (docs/062 "EVALUATION").

**A genuine gap.** Nothing in this monorepo computes precision, recall,
MRR, nDCG, or hit rate -- confirmed by a repo-wide search. The nearest
things are prompt-management-service's A/B significance testing and
incident-management's queue maths, neither of which is retrieval
evaluation. ``numpy`` and ``scipy`` are not dependencies either, so
these are written directly; every one is a closed-form expression over a
short ranked list, which is arithmetic Python does exactly.

**Every metric here is computed against human feedback**, from
``retrieval_feedback``. That is the only ground truth this service has.
Grading retrieval against its own scores would measure nothing except
self-consistency -- a retriever that confidently returns the wrong
documents would score perfectly.

**The @k in every metric is not decoration.** Retrieval quality is a
statement about what a caller actually saw, and a caller saw ``k``
results. Reporting precision over an unbounded list describes a system
nobody used.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetricResult:
    """One metric's value, with what it was computed over.

    ``considered`` is carried because a metric over three results and one
    over three hundred are not equally trustworthy, and a bare float
    hides which one you have.
    """

    name: str
    value: float
    considered: int
    relevant_total: int = 0

    @property
    def is_measurable(self) -> bool:
        """Whether there was anything to measure.

        ``False`` where no results were returned or no relevance is
        known. Distinguishing that from a genuine ``0.0`` matters: one
        says retrieval failed, the other says nobody has judged it yet,
        and reporting them identically makes an unevaluated corpus look
        like a broken one.
        """
        return self.considered > 0


def _validate_k(k: int) -> None:
    if k < 1:
        raise ValueError(f"k must be at least 1, got {k!r}.")


def _top(retrieved: Sequence[str], k: int) -> list[str]:
    """The first *k* results, deduplicated in order.

    Deduplicated because the same chunk reaching the list twice through
    two arms would otherwise count twice toward precision, inflating it
    for a fusion bug rather than exposing it.
    """
    seen: dict[str, None] = {}
    for key in retrieved[:k]:
        seen.setdefault(key, None)
    return list(seen)


def precision_at_k(retrieved: Sequence[str], relevant: set[str], *, k: int) -> MetricResult:
    """Of the top *k* returned, what fraction were relevant.

    The denominator is how many results were actually returned, not *k*.
    A query returning three results, all relevant, has precision 1.0 --
    dividing by ``k = 10`` would report 0.3 and punish the system for
    the corpus being small rather than for ranking badly.
    """
    _validate_k(k)
    top = _top(retrieved, k)
    if not top:
        return MetricResult("precision", 0.0, 0, len(relevant))
    hits = sum(1 for key in top if key in relevant)
    return MetricResult("precision", hits / len(top), len(top), len(relevant))


def recall_at_k(retrieved: Sequence[str], relevant: set[str], *, k: int) -> MetricResult:
    """Of everything relevant, what fraction appeared in the top *k*.

    Undefined when nothing is known to be relevant -- there is no
    denominator. Reported as ``0.0`` with ``relevant_total = 0``, and
    :attr:`MetricResult.is_measurable` is how a caller tells that apart
    from a real zero.
    """
    _validate_k(k)
    if not relevant:
        return MetricResult("recall", 0.0, 0, 0)
    top = _top(retrieved, k)
    hits = sum(1 for key in top if key in relevant)
    return MetricResult("recall", hits / len(relevant), len(top), len(relevant))


def hit_rate_at_k(retrieved: Sequence[str], relevant: set[str], *, k: int) -> MetricResult:
    """Whether *any* relevant result appeared in the top *k*.

    Binary, and the metric that matters most for a RAG pipeline
    specifically: a generator given one correct chunk among five can
    usually answer, so "did we surface anything useful at all?" predicts
    downstream success better than precision does.
    """
    _validate_k(k)
    top = _top(retrieved, k)
    hit = any(key in relevant for key in top)
    return MetricResult("hit_rate", 1.0 if hit else 0.0, len(top), len(relevant))


def reciprocal_rank(retrieved: Sequence[str], relevant: set[str], *, k: int) -> MetricResult:
    """``1 / rank`` of the first relevant result, or ``0.0``.

    Rewards putting a correct answer first far more than putting one
    fifth: 1.0 against 0.2. That asymmetry is deliberate and matches how
    context assembly consumes the list -- the top chunks survive token
    budgeting, the tail is cut.
    """
    _validate_k(k)
    top = _top(retrieved, k)
    for index, key in enumerate(top, start=1):
        if key in relevant:
            return MetricResult("mrr", 1.0 / index, len(top), len(relevant))
    return MetricResult("mrr", 0.0, len(top), len(relevant))


def mean_reciprocal_rank(
    queries: Sequence[tuple[Sequence[str], set[str]]], *, k: int
) -> MetricResult:
    """Mean of :func:`reciprocal_rank` across queries.

    Queries with no known relevant results are skipped rather than
    scored zero: an unjudged query is not a failed one, and averaging
    unjudged zeros in drags the mean toward zero as the judged fraction
    shrinks -- exactly backwards.
    """
    _validate_k(k)
    scored = [
        reciprocal_rank(retrieved, relevant, k=k).value
        for retrieved, relevant in queries
        if relevant
    ]
    if not scored:
        return MetricResult("mrr", 0.0, 0, 0)
    return MetricResult("mrr", sum(scored) / len(scored), len(scored), len(scored))


def dcg_at_k(retrieved: Sequence[str], gains: Mapping[str, float], *, k: int) -> float:
    """Discounted cumulative gain over the top *k*.

    Uses ``gain / log2(rank + 1)``, the standard formulation: rank 1
    divides by ``log2(2) = 1`` and is undiscounted, rank 2 by
    ``log2(3)``, and so on. The alternative ``2**gain - 1`` numerator
    would weight graded relevance exponentially, which is right for
    web search with many grades and wrong here, where feedback is
    mostly binary and a handful of partial judgements.
    """
    _validate_k(k)
    return sum(
        gains.get(key, 0.0) / math.log2(index + 1)
        for index, key in enumerate(_top(retrieved, k), start=1)
    )


def ndcg_at_k(retrieved: Sequence[str], gains: Mapping[str, float], *, k: int) -> MetricResult:
    """DCG normalised by the best achievable ordering.

    The ideal DCG is computed from the *k* highest gains available, so
    the result is bounded by 1.0 and a query whose corpus contains only
    two relevant chunks is not punished for failing to return ten.

    Negative gains are refused rather than clamped: a negative gain makes
    the ideal ordering ill-defined (excluding the item scores higher than
    including it), so nDCG could exceed 1.0 and stop being a ratio.
    """
    _validate_k(k)
    for key, gain in gains.items():
        if gain < 0:
            raise ValueError(f"gain for {key!r} must not be negative, got {gain!r}.")

    top = _top(retrieved, k)
    positive = [gain for gain in gains.values() if gain > 0]
    if not positive:
        return MetricResult("ndcg", 0.0, len(top), 0)

    actual = dcg_at_k(retrieved, gains, k=k)
    ideal_order = sorted(positive, reverse=True)[:k]
    ideal = sum(gain / math.log2(index + 1) for index, gain in enumerate(ideal_order, start=1))
    value = actual / ideal if ideal > 0 else 0.0
    return MetricResult("ndcg", value, len(top), len(positive))


def citation_accuracy(
    cited: Sequence[str], supported: set[str], *, k: int | None = None
) -> MetricResult:
    """What fraction of citations point at chunks that were retrieved.

    A citation naming a chunk that never entered the context is a
    fabricated reference -- the most damaging failure mode a RAG system
    has, because it looks exactly like a real one to a reader.
    """
    considered = list(cited) if k is None else _top(cited, k)
    if not considered:
        return MetricResult("citation_accuracy", 0.0, 0, len(supported))
    valid = sum(1 for key in considered if key in supported)
    return MetricResult(
        "citation_accuracy", valid / len(considered), len(considered), len(supported)
    )


def grounding_score(answer_terms: Sequence[str], context_terms: set[str]) -> MetricResult:
    """What fraction of the answer's content words appear in the context.

    A crude but honest proxy: it measures lexical overlap, not
    entailment. A high score does not prove the answer is supported, but
    a low one is strong evidence it is not -- an answer sharing almost no
    vocabulary with its own retrieved context was not written from it.
    Named ``grounding`` because that is the slot it fills; this docstring
    is where the limitation is stated rather than hidden.
    """
    unique = list(dict.fromkeys(answer_terms))
    if not unique:
        return MetricResult("grounding", 0.0, 0, len(context_terms))
    grounded = sum(1 for term in unique if term in context_terms)
    return MetricResult("grounding", grounded / len(unique), len(unique), len(context_terms))


def evaluate_retrieval(
    retrieved: Sequence[str],
    relevant: set[str],
    *,
    k: int = 10,
    gains: Mapping[str, float] | None = None,
) -> dict[str, MetricResult]:
    """Every ranked-retrieval metric for one query, in one call.

    ``gains`` supplies graded relevance for nDCG. Without it, every
    relevant item is treated as gain 1.0 -- which makes nDCG a measure of
    ordering alone, still meaningful when feedback is binary.
    """
    _validate_k(k)
    graded = dict(gains) if gains else dict.fromkeys(relevant, 1.0)
    return {
        "precision": precision_at_k(retrieved, relevant, k=k),
        "recall": recall_at_k(retrieved, relevant, k=k),
        "hit_rate": hit_rate_at_k(retrieved, relevant, k=k),
        "mrr": reciprocal_rank(retrieved, relevant, k=k),
        "ndcg": ndcg_at_k(retrieved, graded, k=k),
    }


def f1(precision: float, recall: float) -> float:
    """Harmonic mean of precision and recall.

    Harmonic rather than arithmetic so that scoring 1.0 on one and 0.0 on
    the other gives 0.0, not 0.5 -- a retriever returning the whole
    corpus has perfect recall and is useless, and an arithmetic mean
    would call that a passing grade.
    """
    if precision < 0 or recall < 0:
        raise ValueError("precision and recall must not be negative.")
    total = precision + recall
    return 2 * precision * recall / total if total else 0.0


__all__ = [
    "MetricResult",
    "citation_accuracy",
    "dcg_at_k",
    "evaluate_retrieval",
    "f1",
    "grounding_score",
    "hit_rate_at_k",
    "mean_reciprocal_rank",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
    "reciprocal_rank",
]
