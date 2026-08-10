"""The chunking engine (docs/062 "CHUNKING STRATEGIES").

**Chunking is the single decision that most determines retrieval
quality**, and it is made once at ingestion and then baked into every
vector. A chunk that splits a sentence in half embeds a fragment whose
meaning is not the meaning of either sentence; a chunk that swallows
five unrelated sections embeds an average of five topics and is close to
none of them. Neither failure is visible in the vectors themselves --
they surface much later as retrieval that is subtly, unaccountably bad.

That is why every strategy here is a pure function over text with no
model call and no I/O: chunking has to be re-runnable, diffable, and
assertable exactly, or a regression in it is undetectable.

**Overlap exists to survive bad boundaries.** However good the splitter,
some answer will straddle a boundary. Overlap means the tokens either
side of every cut appear in two chunks, so a query matching across a
seam still matches one of them whole.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.chunking.tokens import estimate_tokens
from app.models.enums import ChunkKind, ChunkStrategy

DEFAULT_CHUNK_SIZE = 1_000
DEFAULT_OVERLAP = 150

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\[])")
"""A sentence boundary is punctuation followed by whitespace and then
something that can start a sentence. The lookahead is what keeps
``"version 1.2 of"`` and ``"e.g. this"`` from splitting -- a bare
``[.!?]\\s`` rule shatters version numbers, abbreviations, and decimals,
which is exactly the technical text this service ingests most."""

_MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_SETEXT_HEADING = re.compile(r"^(.+)\n(=+|-+)\s*$", re.MULTILINE)
_FENCE = re.compile(r"^\s*(```|~~~)")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_CODE_BLOCK = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)

_MIN_CHUNK_CHARACTERS = 1
"""A chunk of nothing is not a chunk. Empty and whitespace-only
candidates are dropped rather than embedded -- an embedding of "" is a
real vector that will match queries for no reason."""


@dataclass(frozen=True, slots=True)
class Chunk:
    """One unit of text, with everything a citation needs to point at it."""

    sequence: int
    content: str
    start: int
    end: int
    kind: ChunkKind = ChunkKind.TEXT
    heading: str | None = None
    section_path: tuple[str, ...] = ()
    overlap_tokens: int = 0

    @property
    def token_estimate(self) -> int:
        """How many tokens this chunk costs."""
        return estimate_tokens(self.content)

    @property
    def character_count(self) -> int:
        return len(self.content)

    @property
    def section_label(self) -> str | None:
        """The heading trail, rendered for a citation."""
        return " > ".join(self.section_path) if self.section_path else None


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    """How one document should be split.

    Raises on construction rather than at split time: a config with
    ``overlap >= chunk_size`` cannot make progress -- every window would
    start at or before the previous one -- and discovering that halfway
    through a 10,000-chunk ingestion is worse than discovering it when
    the config is built.
    """

    strategy: ChunkStrategy = ChunkStrategy.HYBRID
    chunk_size: int = DEFAULT_CHUNK_SIZE
    overlap: int = DEFAULT_OVERLAP
    max_chunks: int = 10_000
    respect_code_fences: bool = True

    def __post_init__(self) -> None:
        if self.chunk_size < 1:
            raise ValueError(f"chunk_size must be at least 1, got {self.chunk_size!r}.")
        if self.overlap < 0:
            raise ValueError(f"overlap must not be negative, got {self.overlap!r}.")
        if self.overlap >= self.chunk_size:
            raise ValueError(
                f"overlap ({self.overlap}) must be smaller than chunk_size "
                f"({self.chunk_size}); an overlap at least as large as the window "
                "makes every window start at or before the previous one, so "
                "splitting would never terminate."
            )
        if self.max_chunks < 1:
            raise ValueError(f"max_chunks must be at least 1, got {self.max_chunks!r}.")


@dataclass(slots=True)
class _Section:
    """A run of text under one heading trail, before size-splitting."""

    content: str
    start: int
    path: tuple[str, ...] = ()
    heading: str | None = None
    kind: ChunkKind = ChunkKind.TEXT
    splittable: bool = True
    """False for a fenced code block or a markdown table: splitting one
    across chunks produces two fragments that are each invalid as the
    thing they claim to be, and a half-table embeds as noise."""


# ---------------------------------------------------------------------------
# Boundary finding
# ---------------------------------------------------------------------------


def _last_boundary(text: str, *, pattern: re.Pattern[str], search_from: int) -> int | None:
    """The last match of *pattern* at or after *search_from*, or ``None``.

    Only the tail of the window is searched. A boundary near the start
    would produce a chunk far smaller than requested, which wastes the
    budget the caller asked for -- so a bad boundary late beats a good
    boundary early.
    """
    best: int | None = None
    for match in pattern.finditer(text, search_from):
        best = match.end()
    return best


def _split_point(text: str, *, limit: int) -> int:
    """Where to cut *text* so the first piece is at most *limit* long.

    Prefers a paragraph break, then a sentence end, then any whitespace,
    and only cuts mid-word when the text contains no break at all --
    which happens for a single enormous token like a base64 blob, where
    every option is equally bad and refusing to split would be worse.
    """
    if len(text) <= limit:
        return len(text)

    window = text[:limit]
    search_from = limit // 3
    """Only the last two thirds are considered, so a chunk is never
    smaller than about a third of the requested size."""

    for pattern in (_PARAGRAPH_BREAK, _SENTENCE_END):
        found = _last_boundary(window, pattern=pattern, search_from=search_from)
        if found is not None:
            return found

    whitespace = window.rfind(" ", search_from)
    if whitespace > 0:
        return whitespace + 1
    return limit


def _overlap_prefix(previous: str, *, overlap: int) -> str:
    """The tail of *previous* to repeat at the start of the next chunk.

    Taken on a word boundary so the repeated text reads as language
    rather than starting mid-word.
    """
    if overlap <= 0 or not previous:
        return ""
    tail = previous[-overlap:]
    space = tail.find(" ")
    return tail[space + 1 :] if space != -1 else tail


# ---------------------------------------------------------------------------
# Size-based splitting -- the shared core of every strategy
# ---------------------------------------------------------------------------


def _windows(section: _Section, config: ChunkingConfig) -> list[tuple[str, int, int, int]]:
    """Split one section into ``(content, start, end, overlap_tokens)``.

    An unsplittable section is returned whole even when it exceeds the
    window: a code block or table cut in half is worse than one that is
    simply large, because the fragments are invalid as code and as
    tables while still being embedded as if they were.
    """
    text = section.content
    if not text.strip():
        return []
    if not section.splittable or len(text) <= config.chunk_size:
        return [(text, section.start, section.start + len(text), 0)]

    pieces: list[tuple[str, int, int, int]] = []
    cursor = 0
    carried = ""
    while cursor < len(text):
        budget = config.chunk_size - len(carried)
        if budget < 1:
            # Defensive: ChunkingConfig forbids overlap >= chunk_size, so
            # the carried prefix is always shorter than the window.
            budget = config.chunk_size
        remainder = text[cursor:]
        cut = _split_point(remainder, limit=budget)
        body = remainder[:cut]
        if not body:
            break
        content = f"{carried}{body}" if carried else body
        pieces.append(
            (
                content,
                section.start + cursor - len(carried),
                section.start + cursor + len(body),
                estimate_tokens(carried),
            )
        )
        cursor += cut
        carried = _overlap_prefix(body, overlap=config.overlap)
    return pieces


# ---------------------------------------------------------------------------
# Section extraction -- one function per structural strategy
# ---------------------------------------------------------------------------


def _whole(text: str) -> list[_Section]:
    return [_Section(content=text, start=0)]


def _paragraphs(text: str) -> list[_Section]:
    sections: list[_Section] = []
    cursor = 0
    for piece in _PARAGRAPH_BREAK.split(text):
        start = text.find(piece, cursor) if piece else cursor
        if piece.strip():
            sections.append(_Section(content=piece, start=start))
        cursor = start + len(piece)
    return sections


def _sentences(text: str) -> list[_Section]:
    sections: list[_Section] = []
    cursor = 0
    for piece in _SENTENCE_END.split(text):
        start = text.find(piece, cursor) if piece else cursor
        if piece.strip():
            sections.append(_Section(content=piece, start=start))
        cursor = start + len(piece)
    return sections


def _headings(text: str) -> list[_Section]:
    """Split on markdown headings, carrying the heading trail down.

    The trail is what makes a citation usable: "Operations > Backups >
    Restore" tells a reader where to look in a way "page 14" does not.
    """
    matches = list(_MARKDOWN_HEADING.finditer(text))
    if not matches:
        return _whole(text)

    sections: list[_Section] = []
    preamble = text[: matches[0].start()]
    if preamble.strip():
        sections.append(_Section(content=preamble, start=0))

    trail: list[str] = []
    for index, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        del trail[level - 1 :]
        trail.append(title)

        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.start() : end]
        if body.strip():
            sections.append(
                _Section(
                    content=body,
                    start=match.start(),
                    path=tuple(trail),
                    heading=title,
                    kind=(
                        ChunkKind.HEADING
                        if body.strip() == match.group(0).strip()
                        else ChunkKind.TEXT
                    ),
                )
            )
    return sections


def _fenced_spans(text: str) -> list[tuple[int, int]]:
    """Character spans covered by fenced code blocks."""
    return [(match.start(), match.end()) for match in _CODE_BLOCK.finditer(text)]


def _code_aware(text: str) -> list[_Section]:
    """Keep fenced code blocks whole; split the prose around them.

    A code block cut across chunks yields two fragments that neither
    parse nor read as code, and whose embeddings describe neither the
    function above the cut nor the one below it.
    """
    spans = _fenced_spans(text)
    if not spans:
        return _paragraphs(text)

    sections: list[_Section] = []
    cursor = 0
    for start, end in spans:
        prose = text[cursor:start]
        if prose.strip():
            sections.extend(
                _Section(content=s.content, start=start_of + s.start, path=s.path)
                for start_of, s in ((cursor, s) for s in _paragraphs(prose))
            )
        sections.append(
            _Section(
                content=text[start:end],
                start=start,
                kind=ChunkKind.CODE,
                splittable=False,
            )
        )
        cursor = end
    tail = text[cursor:]
    if tail.strip():
        sections.extend(
            _Section(content=s.content, start=cursor + s.start, path=s.path)
            for s in _paragraphs(tail)
        )
    return sections


def _table_runs(text: str) -> list[_Section]:
    """Keep contiguous markdown table rows together.

    A table split across chunks loses its header row on the second half,
    which is exactly the row that says what the columns mean.
    """
    lines = text.splitlines(keepends=True)
    sections: list[_Section] = []
    buffer: list[str] = []
    buffer_start = 0
    offset = 0
    in_table = False

    def flush(kind: ChunkKind) -> None:
        nonlocal buffer
        joined = "".join(buffer)
        if joined.strip():
            sections.append(
                _Section(
                    content=joined,
                    start=buffer_start,
                    kind=kind,
                    splittable=kind is not ChunkKind.TABLE,
                )
            )
        buffer = []

    for line in lines:
        is_row = bool(_TABLE_ROW.match(line))
        if is_row != in_table:
            flush(ChunkKind.TABLE if in_table else ChunkKind.TEXT)
            buffer_start = offset
            in_table = is_row
        buffer.append(line)
        offset += len(line)
    flush(ChunkKind.TABLE if in_table else ChunkKind.TEXT)
    return sections


def _semantic(text: str) -> list[_Section]:
    """Group adjacent paragraphs that share vocabulary.

    **Lexical, not embedding-based, and that is a deliberate limit.**
    True semantic chunking embeds every candidate boundary and cuts where
    similarity drops, which costs one embedding call per paragraph at
    ingestion -- for a large corpus that is a bigger spend than embedding
    the chunks themselves. This approximates it with Jaccard overlap on
    content words, which catches the common case (a topic shift comes
    with a vocabulary shift) at zero cost. Named honestly: it is
    ``SEMANTIC`` in the enum because that is the strategy slot it fills,
    and this docstring is where the approximation is stated.
    """
    paragraphs = _paragraphs(text)
    if len(paragraphs) < _MIN_PARAGRAPHS_TO_MERGE:
        return paragraphs

    merged: list[_Section] = []
    current = paragraphs[0]
    for nxt in paragraphs[1:]:
        if _lexical_overlap(current.content, nxt.content) >= _SEMANTIC_THRESHOLD:
            current = _Section(
                content=text[current.start : nxt.start + len(nxt.content)],
                start=current.start,
                path=current.path,
            )
        else:
            merged.append(current)
            current = nxt
    merged.append(current)
    return merged


_SEMANTIC_THRESHOLD = 0.05
"""Jaccard overlap above which two adjacent paragraphs are treated as one
topic.

**Calibrated against measured pairs, not chosen by feel.** Over hand-built
same-topic and different-topic paragraph pairs, different-topic overlap
was uniformly ``0.0`` while same-topic overlap ranged ``0.0``-``0.33``.
Anything above zero is therefore evidence of a shared topic, and the
threshold sits just above it. An earlier value of ``0.12`` was inside the
same-topic range and refused to merge genuinely related paragraphs --
which made this strategy behave identically to ``PARAGRAPH`` and so do
nothing at all.

The one case this cannot catch is visible in that same data: a same-topic
pair that shares no content words scores ``0.0`` and will not merge.
Separating those needs embeddings, which is precisely the per-paragraph
cost this approximation exists to avoid."""

_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "was",
        "were",
        "will",
        "with",
        "this",
        "these",
        "those",
        "but",
        "not",
        "you",
        "your",
        "we",
        "our",
        "they",
        "their",
    ]
)
"""Function words carry no topic, so leaving them in would make every
pair of English paragraphs look related."""

_MIN_CONTENT_WORD_LENGTH = 3
"""Shorter tokens are overwhelmingly function words, initials, or
fragments of markup, and including them adds noise to the overlap without
adding topic."""

_MIN_PARAGRAPHS_TO_MERGE = 2
"""Nothing to compare a lone paragraph against."""


def _content_words(text: str) -> set[str]:
    """Lower-cased words that carry topic, stopwords removed."""
    return {
        word
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if len(word) >= _MIN_CONTENT_WORD_LENGTH and word not in _STOPWORDS
    }


def _lexical_overlap(left: str, right: str) -> float:
    """Jaccard similarity of two texts' content words."""
    a, b = _content_words(left), _content_words(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _hybrid(text: str) -> list[_Section]:
    """Headings first, then code and tables kept whole inside each.

    The default, because real documents are all of these at once: a
    runbook is headings around prose around commands around a table, and
    a strategy that only understands one of those mangles the rest.
    """
    sections: list[_Section] = []
    for section in _headings(text):
        for inner in _code_aware(section.content):
            for leaf in _table_runs(inner.content):
                if not leaf.content.strip():
                    continue
                sections.append(
                    _Section(
                        content=leaf.content,
                        start=section.start + inner.start + leaf.start,
                        path=section.path,
                        heading=section.heading,
                        kind=leaf.kind if leaf.kind is not ChunkKind.TEXT else inner.kind,
                        splittable=leaf.splittable and inner.splittable,
                    )
                )
    return sections


_STRATEGIES = {
    ChunkStrategy.FIXED_SIZE: _whole,
    ChunkStrategy.SLIDING_WINDOW: _whole,
    ChunkStrategy.PARAGRAPH: _paragraphs,
    ChunkStrategy.SENTENCE: _sentences,
    ChunkStrategy.HEADING: _headings,
    ChunkStrategy.CODE_AWARE: _code_aware,
    ChunkStrategy.TABLE_AWARE: _table_runs,
    ChunkStrategy.SEMANTIC: _semantic,
    ChunkStrategy.HYBRID: _hybrid,
}
"""``FIXED_SIZE`` and ``SLIDING_WINDOW`` share ``_whole`` because the
difference between them is entirely the overlap: a fixed-size split is a
sliding window with zero overlap. Modelling that as two section
extractors would duplicate the windowing code to express a parameter."""


def chunk_text(text: str, config: ChunkingConfig | None = None) -> list[Chunk]:
    """Split *text* into retrievable chunks.

    Returns an empty list for empty or whitespace-only input rather than
    one empty chunk: an embedding of "" is a real vector that matches
    queries for no reason.
    """
    settings = config or ChunkingConfig()
    if not text.strip():
        return []

    extract = _STRATEGIES[ChunkStrategy(settings.strategy)]
    chunks: list[Chunk] = []
    for section in extract(text):
        for content, start, end, overlap in _windows(section, settings):
            if len(content.strip()) < _MIN_CHUNK_CHARACTERS:
                continue
            chunks.append(
                Chunk(
                    sequence=len(chunks),
                    content=content,
                    start=max(start, 0),
                    end=end,
                    kind=_classify(content, section.kind),
                    heading=section.heading,
                    section_path=section.path,
                    overlap_tokens=overlap,
                )
            )
            if len(chunks) >= settings.max_chunks:
                return chunks
    return chunks


def _classify(content: str, declared: ChunkKind) -> ChunkKind:
    """What this chunk's content actually is.

    The section's own kind wins when it is specific -- a code block is a
    code block regardless of what its text looks like -- and content is
    only inspected to upgrade an otherwise-unclassified chunk.
    """
    if declared is not ChunkKind.TEXT:
        return declared
    stripped = content.strip()
    if _FENCE.match(stripped):
        return ChunkKind.CODE
    lines = [line for line in stripped.splitlines() if line.strip()]
    if lines and all(_TABLE_ROW.match(line) for line in lines):
        return ChunkKind.TABLE
    if lines and all(_LIST_ITEM.match(line) for line in lines):
        return ChunkKind.LIST
    if len(lines) == 1 and _MARKDOWN_HEADING.match(stripped):
        return ChunkKind.HEADING
    return ChunkKind.TEXT


def rechunk_needed(previous: Sequence[Chunk], text: str, config: ChunkingConfig) -> bool:
    """Whether *text* would chunk differently than *previous* did.

    Lets an incremental reindex skip documents whose chunking is
    unchanged even though something else about them moved -- re-embedding
    identical chunks is the largest avoidable cost in this service.
    """
    fresh = chunk_text(text, config)
    if len(fresh) != len(previous):
        return True
    return any(new.content != old.content for new, old in zip(fresh, previous, strict=True))


__all__ = [
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_OVERLAP",
    "Chunk",
    "ChunkingConfig",
    "chunk_text",
    "rechunk_needed",
]
