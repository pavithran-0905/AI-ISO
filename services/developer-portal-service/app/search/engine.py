"""Search relevance scoring.

**A declared seam.** docs/074's own "DO NOT IMPLEMENT: External Search
Engines" rules out a live Elasticsearch/OpenSearch integration; "AI-
powered Ranking" is satisfied here by a deterministic keyword-overlap
scorer, not a live semantic-embedding search. A real deployment could
swap this module's internals for a vector-similarity call without
touching any caller -- the function signature (query, candidate ->
score) is the seam.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

_TITLE_WEIGHT = 3
_KEYWORD_WEIGHT = 2
_SUMMARY_WEIGHT = 1


@dataclass(frozen=True, slots=True)
class SearchCandidate:
    """The minimal shape :func:`score_candidate` needs from an indexed
    row -- decoupled from the ORM model so this stays a pure function."""

    title: str
    summary: str
    keywords: Sequence[str]


def _tokenize(text: str) -> set[str]:
    return {token for token in text.lower().split() if token}


def score_candidate(query: str, candidate: SearchCandidate) -> float:
    """A relevance score for *candidate* against *query*: weighted
    token overlap across title, keywords, and summary, normalized by
    the query's own token count so a longer query does not
    automatically outscore a shorter, more precise one."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0

    title_tokens = _tokenize(candidate.title)
    keyword_tokens = {keyword.lower() for keyword in candidate.keywords}
    summary_tokens = _tokenize(candidate.summary)

    score = (
        _TITLE_WEIGHT * len(query_tokens & title_tokens)
        + _KEYWORD_WEIGHT * len(query_tokens & keyword_tokens)
        + _SUMMARY_WEIGHT * len(query_tokens & summary_tokens)
    )
    return score / len(query_tokens)


def rank_candidates(
    query: str, candidates: Sequence[tuple[str, SearchCandidate]]
) -> list[tuple[str, float]]:
    """Rank *candidates* (each an opaque id paired with its own
    :class:`SearchCandidate`) against *query*, highest score first,
    excluding zero-score entries entirely -- a search result set with
    an irrelevant entry in it is worse than a shorter, all-relevant
    one."""
    scored = [
        (identifier, score_candidate(query, candidate)) for identifier, candidate in candidates
    ]
    return sorted(
        (entry for entry in scored if entry[1] > 0), key=lambda entry: entry[1], reverse=True
    )


__all__ = ["SearchCandidate", "rank_candidates", "score_candidate"]
