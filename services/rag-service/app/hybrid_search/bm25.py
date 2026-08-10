"""BM25 ranking (docs/062 "HYBRID SEARCH": BM25).

**A genuine gap.** Nothing anywhere in this monorepo scores lexical
relevance -- confirmed by a repo-wide search before writing this.
``shared_core.database.search.apply_search`` filters with ``ILIKE``,
``to_tsvector``, or trigram similarity, and ai-assistant-service's
keyword half is a bare ``ILIKE`` OR. All of those answer "does this
match?"; none answers "how well?", which is exactly what a hybrid ranker
needs from its lexical arm.

Implemented here rather than added as a dependency because BM25 is a
closed-form formula over term statistics -- roughly thirty lines -- and
the alternative (``rank_bm25``) would pull in numpy for arithmetic this
does not need.

**Why BM25 and not raw term frequency.** Two corrections make it work
where TF-IDF does not:

- *Saturation.* A document mentioning "backup" fifty times is not fifty
  times more about backups than one mentioning it once. ``k1`` bounds
  the contribution of repetition, so keyword-stuffed text cannot
  dominate.
- *Length normalisation.* A long document contains more of every term by
  accident. ``b`` discounts matches in documents longer than average, so
  a short precise chunk can outrank a long rambling one.

Both matter more here than in general search, because chunks vary in
length by design -- a table chunk and a prose chunk are not comparable
without normalisation.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

DEFAULT_K1 = 1.2
"""Term-frequency saturation. 1.2 is the value from the original Okapi
work and what Lucene and Elasticsearch both default to; a corpus tuned
against one of those stays comparable."""

DEFAULT_B = 0.75
"""Length-normalisation strength. 0 disables it entirely, 1 normalises
fully; 0.75 is the standard compromise."""

_TOKEN = re.compile(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*")
"""Words, plus hyphenated, underscored, and dotted compounds kept whole.
Deliberate: this service indexes technical text where ``pg_dump``,
``node.js``, and ``read-only`` are single terms, and a tokenizer that
shatters them makes those exact queries unanswerable."""


def tokenize(text: str) -> list[str]:
    """Split *text* into lower-cased BM25 terms.

    No stemming. A stemmer helps prose and hurts identifiers -- it would
    conflate ``logging`` with ``logs`` (useful) and also ``AXIS`` with
    ``axi`` (nonsense), and this corpus is full of identifiers, error
    codes, and hostnames where an exact match is the whole point. The
    vector arm of the hybrid already supplies the semantic matching a
    stemmer crudely approximates.
    """
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True, slots=True)
class ScoredDocument:
    """One document's BM25 score against one query."""

    doc_id: str
    score: float
    matched_terms: tuple[str, ...] = ()

    @property
    def matched(self) -> bool:
        """Whether any query term appeared at all."""
        return bool(self.matched_terms)


@dataclass(slots=True)
class Bm25Index:
    """An in-memory BM25 index over a set of documents.

    Built per query batch rather than persisted. That is a deliberate
    scope limit with a real consequence: it is right for reranking a
    candidate set already narrowed by the database (hundreds of chunks),
    and wrong for scoring an entire corpus (millions). The corpus-scale
    path is PostgreSQL's own full-text index via ``apply_search``, which
    is why that is used first to *select* candidates and this is used to
    *rank* them.
    """

    k1: float = DEFAULT_K1
    b: float = DEFAULT_B
    _doc_ids: list[str] = field(default_factory=list)
    _term_frequencies: list[Counter[str]] = field(default_factory=list)
    _lengths: list[int] = field(default_factory=list)
    _document_frequency: Counter[str] = field(default_factory=Counter)

    def __post_init__(self) -> None:
        if self.k1 < 0:
            raise ValueError(f"k1 must not be negative, got {self.k1!r}.")
        if not 0.0 <= self.b <= 1.0:
            raise ValueError(f"b must be within [0, 1], got {self.b!r}.")

    @property
    def document_count(self) -> int:
        return len(self._doc_ids)

    @property
    def average_length(self) -> float:
        """Mean document length in terms. ``0.0`` for an empty index."""
        return sum(self._lengths) / len(self._lengths) if self._lengths else 0.0

    def add(self, doc_id: str, text: str) -> None:
        """Index one document."""
        terms = tokenize(text)
        self._doc_ids.append(doc_id)
        frequencies = Counter(terms)
        self._term_frequencies.append(frequencies)
        self._lengths.append(len(terms))
        self._document_frequency.update(frequencies.keys())

    def add_many(self, documents: Iterable[tuple[str, str]]) -> None:
        """Index several documents."""
        for doc_id, text in documents:
            self.add(doc_id, text)

    def inverse_document_frequency(self, term: str) -> float:
        """How much signal *term* carries.

        Uses the ``+1`` smoothed form, ``log(1 + (N - df + 0.5) /
        (df + 0.5))``, rather than the classical
        ``log((N - df + 0.5) / (df + 0.5))``. The classical form goes
        **negative** for a term appearing in more than half the
        documents, which means a common term actively subtracts from a
        document's score -- a document matching *more* query terms can
        rank below one matching fewer. The smoothed form is bounded below
        by zero, so a match never hurts.
        """
        if not self._doc_ids:
            return 0.0
        df = self._document_frequency.get(term, 0)
        n = len(self._doc_ids)
        return math.log(1.0 + (n - df + 0.5) / (df + 0.5))

    def score(self, query: str) -> list[ScoredDocument]:
        """Score every indexed document against *query*, best first.

        Documents matching nothing are included with a score of ``0.0``
        rather than dropped: the caller is fusing this list with others
        by rank, and a document missing from one arm is different from a
        document that arm scored zero.
        """
        terms = tokenize(query)
        if not self._doc_ids:
            return []

        average = self.average_length
        idf = {term: self.inverse_document_frequency(term) for term in set(terms)}
        results: list[ScoredDocument] = []
        for index, doc_id in enumerate(self._doc_ids):
            frequencies = self._term_frequencies[index]
            length = self._lengths[index]
            total = 0.0
            matched: list[str] = []
            for term in terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                matched.append(term)
                # Length normalisation is undefined for an empty corpus;
                # average is only zero when every document is empty, in
                # which case no term can have matched at all.
                norm = 1.0 - self.b + self.b * (length / average) if average else 1.0
                total += idf[term] * (frequency * (self.k1 + 1.0) / (frequency + self.k1 * norm))
            results.append(
                ScoredDocument(
                    doc_id=doc_id,
                    score=total,
                    matched_terms=tuple(dict.fromkeys(matched)),
                )
            )
        results.sort(key=lambda item: (-item.score, item.doc_id))
        return results

    def top(self, query: str, *, limit: int) -> list[ScoredDocument]:
        """The best *limit* documents that matched at least one term.

        Raises:
            ValueError: If *limit* is not positive.
        """
        if limit < 1:
            raise ValueError(f"limit must be at least 1, got {limit!r}.")
        return [item for item in self.score(query) if item.matched][:limit]


def build_index(
    documents: Sequence[tuple[str, str]], *, k1: float = DEFAULT_K1, b: float = DEFAULT_B
) -> Bm25Index:
    """Build a :class:`Bm25Index` over *documents*."""
    index = Bm25Index(k1=k1, b=b)
    index.add_many(documents)
    return index


def rank(
    query: str,
    documents: Sequence[tuple[str, str]],
    *,
    limit: int = 10,
    k1: float = DEFAULT_K1,
    b: float = DEFAULT_B,
) -> list[ScoredDocument]:
    """Score *documents* against *query* in one call."""
    return build_index(documents, k1=k1, b=b).top(query, limit=limit)


__all__ = [
    "DEFAULT_B",
    "DEFAULT_K1",
    "Bm25Index",
    "ScoredDocument",
    "build_index",
    "rank",
    "tokenize",
]
