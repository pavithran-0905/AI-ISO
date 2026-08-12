"""Context assembly (docs/062 "CONTEXT ASSEMBLY").

Turning a ranked list of chunks into the block of text a model actually
receives. Four decisions happen here, and each one silently degrades
answer quality if it is wrong:

**Token budgeting.** The budget is a hard limit, not a target. Overflow
does not degrade gracefully -- the provider truncates from one end, and
which end is not something this service controls, so a chunk that was
carefully ranked first can be the one that gets cut. Everything is
measured before it is included.

**Deduplication.** Overlapping chunks are guaranteed by design: the
splitter repeats text either side of every boundary so answers spanning a
seam survive. That same overlap means near-identical chunks reach here
routinely, and including both spends the budget twice for one fact.

**Ordering.** Assembled by relevance but emitted in *document* order
where chunks come from the same source, because prose read out of order
is harder to follow -- for a model as for a person. Relevance decides
what gets in; document order decides how it reads.

**Citation mapping.** Every included chunk gets a stable label, and the
mapping from label to chunk is returned alongside the text. A citation a
reader cannot resolve is worse than no citation, because it looks like
evidence.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.chunking.tokens import estimate_tokens, truncate_to_tokens

DEFAULT_MAX_TOKENS = 8_000
DUPLICATE_THRESHOLD = 0.85
"""Jaccard overlap above which two chunks are treated as the same
content. High, because the cost of a false positive -- dropping a chunk
that genuinely said something new -- is losing an answer, while the cost
of a false negative is only wasted budget."""

_MIN_TOKEN_LENGTH = 3


@dataclass(frozen=True, slots=True)
class ContextChunk:
    """One candidate for inclusion in the assembled context."""

    key: str
    content: str
    score: float
    document_id: str = ""
    document_title: str = ""
    sequence: int = 0
    page_number: int | None = None
    section_path: str | None = None
    source_uri: str | None = None

    @property
    def token_estimate(self) -> int:
        return estimate_tokens(self.content)


@dataclass(frozen=True, slots=True)
class Citation:
    """A resolvable reference to one included chunk."""

    label: str
    chunk_key: str
    document_id: str
    document_title: str
    page_number: int | None = None
    section_path: str | None = None
    source_uri: str | None = None
    score: float = 0.0

    def render(self) -> str:
        """A one-line human-readable reference.

        Includes the section trail and page where known: a citation that
        names only the document sends a reader to search a 200-page PDF,
        which is not meaningfully better than no citation at all.
        """
        parts = [self.document_title or self.document_id]
        if self.section_path:
            parts.append(self.section_path)
        if self.page_number is not None:
            parts.append(f"p. {self.page_number}")
        return f"[{self.label}] {' — '.join(parts)}"


@dataclass(slots=True)
class AssembledContext:
    """The final context block, plus everything needed to audit it."""

    text: str
    citations: list[Citation] = field(default_factory=list)
    included: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    """Chunks that ranked but did not fit, or were dropped as duplicates.
    Recorded because "the model never saw it" is a different failure from
    "retrieval never found it", and only one of them is fixed by
    improving retrieval."""
    duplicates_dropped: int = 0
    token_count: int = 0
    budget: int = 0
    truncated: bool = False

    @property
    def utilisation(self) -> float:
        """What fraction of the budget was used."""
        return self.token_count / self.budget if self.budget else 0.0

    @property
    def citation_map(self) -> dict[str, str]:
        """``{label: chunk_key}``, for resolving a model's citations."""
        return {citation.label: citation.chunk_key for citation in self.citations}


def _tokens(text: str) -> set[str]:
    """Words long enough to carry meaning.

    Short words are function words present in nearly every chunk, so
    counting them would make any two English paragraphs look like
    duplicates. A consequence worth knowing: text made entirely of one-
    and two-letter words has no comparable tokens and scores ``0.0``
    against itself.
    """
    return {word for word in text.lower().split() if len(word) >= _MIN_TOKEN_LENGTH}


def _label_cost(position: int, include_citations: bool) -> int:
    """Tokens the ``[n] `` prefix will add for the chunk at *position*.

    Computed per position rather than assumed constant: ``[9] `` and
    ``[10] `` are not the same length, and a fixed estimate would drift
    over a long context.
    """
    return estimate_tokens(f"[{position}] ") if include_citations else 0


def similarity(left: str, right: str) -> float:
    """Jaccard overlap of two chunks' words."""
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def deduplicate(
    chunks: Sequence[ContextChunk], *, threshold: float = DUPLICATE_THRESHOLD
) -> tuple[list[ContextChunk], list[str]]:
    """Drop chunks that repeat content already kept.

    Keeps the *first* occurrence, which is the highest-ranked one because
    the caller passes them in rank order. Returns the survivors and the
    keys dropped.

    Raises:
        ValueError: If *threshold* is outside ``[0, 1]``.
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"threshold must be within [0, 1], got {threshold!r}.")

    kept: list[ContextChunk] = []
    dropped: list[str] = []
    for chunk in chunks:
        if any(similarity(chunk.content, existing.content) >= threshold for existing in kept):
            dropped.append(chunk.key)
            continue
        kept.append(chunk)
    return kept, dropped


def order_for_reading(chunks: Sequence[ContextChunk]) -> list[ContextChunk]:
    """Group by document, then order by position within it.

    Documents are ordered by their best-scoring chunk, so the most
    relevant source still comes first; within a document, chunks are
    emitted in the order they were written. Interleaving two documents'
    fragments by raw relevance produces text that reads as non-sequitur,
    and a model asked to reason over it does measurably worse.
    """
    best: dict[str, float] = {}
    for chunk in chunks:
        key = chunk.document_id or chunk.key
        best[key] = max(best.get(key, float("-inf")), chunk.score)
    return sorted(
        chunks,
        key=lambda chunk: (
            -best[chunk.document_id or chunk.key],
            chunk.document_id or chunk.key,
            chunk.sequence,
        ),
    )


def assemble(
    chunks: Sequence[ContextChunk],
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    deduplicate_chunks: bool = True,
    threshold: float = DUPLICATE_THRESHOLD,
    include_citations: bool = True,
    separator: str = "\n\n",
    allow_partial: bool = False,
) -> AssembledContext:
    """Build a context block from *chunks*, best first.

    ``allow_partial`` truncates the first chunk that does not fit rather
    than skipping it. Off by default: a chunk cut mid-sentence can change
    what it appears to say, and a model has no way to know it is reading
    a fragment. Skipping is the safer failure.

    Raises:
        ValueError: If *max_tokens* is not positive.
    """
    if max_tokens < 1:
        raise ValueError(f"max_tokens must be at least 1, got {max_tokens!r}.")

    candidates = list(chunks)
    dropped: list[str] = []
    if deduplicate_chunks:
        candidates, dropped = deduplicate(candidates, threshold=threshold)

    selected: list[ContextChunk] = []
    excluded: list[str] = list(dropped)
    used = 0
    truncated = False
    separator_cost = estimate_tokens(separator)

    for chunk in candidates:
        if not chunk.content.strip():
            # A blank chunk would still be labelled and cited, producing a
            # citation that points at nothing -- the "gesture at evidence"
            # this module exists to avoid. The chunker never emits one, so
            # this only catches a caller assembling something else.
            excluded.append(chunk.key)
            continue
        # Both the separator and the citation label are real text in the
        # emitted body, so both are charged against the budget. Omitting
        # the label cost overruns by ~3 tokens per chunk -- invisible
        # when chunks are skipped and slack absorbs it, and a genuine
        # overrun the moment truncation fills the budget exactly.
        overhead = (separator_cost if selected else 0) + _label_cost(
            len(selected) + 1, include_citations
        )
        cost = chunk.token_estimate + overhead
        if used + cost <= max_tokens:
            selected.append(chunk)
            used += cost
            continue
        remaining = max_tokens - used - overhead
        if allow_partial and remaining > 0:
            shortened = truncate_to_tokens(chunk.content, budget=remaining)
            if shortened.strip():
                # Rebuild rather than mutate: ContextChunk is frozen so a
                # truncated copy cannot be mistaken for the original.
                selected.append(
                    ContextChunk(
                        key=chunk.key,
                        content=shortened,
                        score=chunk.score,
                        document_id=chunk.document_id,
                        document_title=chunk.document_title,
                        sequence=chunk.sequence,
                        page_number=chunk.page_number,
                        section_path=chunk.section_path,
                        source_uri=chunk.source_uri,
                    )
                )
                used += estimate_tokens(shortened) + overhead
                truncated = True
                continue
        excluded.append(chunk.key)

    ordered = order_for_reading(selected)
    citations = (
        [
            Citation(
                label=str(index),
                chunk_key=chunk.key,
                document_id=chunk.document_id,
                document_title=chunk.document_title,
                page_number=chunk.page_number,
                section_path=chunk.section_path,
                source_uri=chunk.source_uri,
                score=chunk.score,
            )
            for index, chunk in enumerate(ordered, start=1)
        ]
        if include_citations
        else []
    )

    if include_citations:
        body = separator.join(
            f"[{citation.label}] {chunk.content}"
            for citation, chunk in zip(citations, ordered, strict=True)
        )
    else:
        body = separator.join(chunk.content for chunk in ordered)

    return AssembledContext(
        text=body,
        citations=citations,
        included=[chunk.key for chunk in ordered],
        excluded=excluded,
        duplicates_dropped=len(dropped),
        token_count=estimate_tokens(body),
        budget=max_tokens,
        truncated=truncated,
    )


def resolve_citations(context: AssembledContext, cited_labels: Sequence[str]) -> list[Citation]:
    """Turn the labels a model emitted back into real citations.

    Unknown labels are skipped rather than invented. A model citing "[7]"
    when only four chunks were supplied has fabricated a reference, and
    :func:`~app.evaluation.metrics.citation_accuracy` is what measures how
    often that happens -- silently inventing a citation to match would
    hide the exact failure this is here to catch.
    """
    by_label = {citation.label: citation for citation in context.citations}
    return [by_label[label] for label in dict.fromkeys(cited_labels) if label in by_label]


__all__ = [
    "DEFAULT_MAX_TOKENS",
    "DUPLICATE_THRESHOLD",
    "AssembledContext",
    "Citation",
    "ContextChunk",
    "assemble",
    "deduplicate",
    "order_for_reading",
    "resolve_citations",
    "similarity",
]
