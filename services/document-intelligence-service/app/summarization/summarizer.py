"""Summarization (docs/063 "SUMMARIZATION").

Six summary kinds, all built on one extractive ranker. Sentences are
scored on term salience, position, and the reader the summary is for --
an executive summary and a technical one rank the same document
differently because "cost" and "latency" are not equally interesting to
their readers.

**Every summary here is extractive.** Sentences come from the document
verbatim, which means a summary can be wrong about emphasis but never
about fact. :class:`AbstractiveBackend` is the seam where a generative
model plugs in; when none is configured, an abstractive request falls
back to extraction and *says so* in ``fallback_used`` rather than
returning invented text or an error.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.core.text import vocabulary
from app.models.enums import SummaryKind

MIN_SENTENCE_WORDS = 4
"""Shorter than this is a heading, a label or a page number."""

MAX_SENTENCE_WORDS = 80
"""Longer than this the "sentence" is an unpunctuated wall of text, and
including one swamps a summary."""

DEFAULT_SENTENCE_COUNT = 5

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])[ \t]+(?=[\"'(\[]?[A-Z0-9])|\n{2,}")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]+")
_HEADING = re.compile(r"^\s*(?:#{1,6}\s+|\d+(?:\.\d+)*[.)]?\s+)?(?P<title>[^\n]{3,80})\s*$")
_BULLET_PREFIX = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
"""A markdown table row. Not a sentence: a summary that selects one reads
as ``| payments-api | high | R. Mehta |``, and a divider row reads as
``| --- | --- |``. The live end-to-end run put exactly that into an
executive summary."""

STOPWORDS = vocabulary(
    """a an and are as at be been but by for from had has have he her his i if in into is it
    its of on or our she that the their them then there these they this to was were what when
    where which who will with would you your not no do does did can could should may might"""
)

EXECUTIVE_TERMS = vocabulary(
    """approval budget business cost customer decision deadline decision impact investment
    outcome priority recommendation revenue risk roi schedule scope stakeholder strategy
    summary timeline"""
)

TECHNICAL_TERMS = vocabulary(
    """api architecture cache cluster configuration cpu database dependency deployment endpoint
    error exception failure kubernetes latency memory migration network node performance
    pipeline query replica request rollback schema service throughput timeout version"""
)


class AbstractiveBackend(Protocol):
    """A generative summarizer, if one is configured.

    Deliberately narrow: this module owns sentence selection and hands a
    backend only the text and a length budget, so swapping the model
    cannot change what counts as an important sentence.
    """

    def summarize(self, text: str, *, max_words: int, kind: SummaryKind) -> str:
        """Prose summarizing *text* in at most *max_words* words."""
        ...


@dataclass(slots=True)
class SummarySentence:
    """One ranked sentence, with why it ranked where it did."""

    text: str
    score: float
    position: int
    word_count: int
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Summary:
    """One summary of one document."""

    kind: SummaryKind
    text: str = ""
    sentences: list[SummarySentence] = field(default_factory=list)
    confidence: float = 0.0
    fallback_used: bool = False
    """Set when an abstractive summary was asked for and extracted
    instead. The caller must be able to tell which it got."""
    source_word_count: int = 0
    keywords: list[str] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def compression_ratio(self) -> float:
        """How much shorter the summary is, as a fraction kept.

        Zero for an empty source rather than a division error: a summary
        of nothing has compressed nothing.
        """
        if not self.source_word_count:
            return 0.0
        return round(self.word_count / self.source_word_count, 4)


@dataclass(frozen=True, slots=True)
class SummaryConfig:
    """How summarization behaves."""

    sentence_count: int = DEFAULT_SENTENCE_COUNT
    max_words: int = 200
    min_sentence_words: int = MIN_SENTENCE_WORDS
    keyword_count: int = 8
    preserve_order: bool = True
    """Emit the chosen sentences in document order rather than in rank
    order. Rank order reads as a list of disconnected claims; document
    order preserves the argument the document was making."""


def summarize(
    text: str,
    *,
    kind: SummaryKind = SummaryKind.EXTRACTIVE,
    config: SummaryConfig | None = None,
    backend: AbstractiveBackend | None = None,
) -> Summary:
    """Summarize *text* in the manner *kind* asks for."""
    settings = config or SummaryConfig()
    chosen = SummaryKind(str(kind))
    source_words = len(text.split())
    summary = Summary(kind=chosen, source_word_count=source_words)
    if not text.strip():
        return summary

    if chosen is SummaryKind.SECTION:
        return _section_summary(text, settings, summary)

    sentences = _sentences(text, settings)
    if not sentences:
        return summary

    weights = _term_weights(sentences)
    summary.keywords = [term for term, _ in weights.most_common(settings.keyword_count)]
    ranked = _rank(sentences, weights, chosen)
    picked = ranked[: settings.sentence_count]
    if settings.preserve_order:
        picked = sorted(picked, key=lambda item: item.position)

    summary.sentences = picked
    summary.confidence = _confidence(picked, ranked)

    if chosen is SummaryKind.BULLET:
        summary.text = "\n".join(f"- {item.text}" for item in picked)
    elif chosen is SummaryKind.ABSTRACTIVE:
        summary.text, summary.fallback_used = _abstractive(text, picked, settings, backend, chosen)
    else:
        summary.text = " ".join(item.text for item in picked)

    summary.text = _truncate_words(summary.text, settings.max_words)
    return summary


def _abstractive(
    text: str,
    picked: Sequence[SummarySentence],
    config: SummaryConfig,
    backend: AbstractiveBackend | None,
    kind: SummaryKind,
) -> tuple[str, bool]:
    """Generated prose and whether extraction was used instead.

    A backend that raises is treated as a backend that is absent: a
    summarization failure must not fail the whole document pipeline when
    a truthful extractive summary is available.
    """
    if backend is None:
        return " ".join(item.text for item in picked), True
    try:
        generated = backend.summarize(text, max_words=config.max_words, kind=kind)
    except Exception:
        return " ".join(item.text for item in picked), True
    if not generated.strip():
        return " ".join(item.text for item in picked), True
    return generated.strip(), False


# ---- sentences ------------------------------------------------------------------


def _sentences(text: str, config: SummaryConfig) -> list[SummarySentence]:
    """Usable sentences from *text*, in document order.

    Hard-wrapped lines are rejoined first. Documents that came from a
    PDF text layer or a plain-text file break mid-sentence at whatever
    column they were typeset to, and splitting on newlines turns every
    sentence into two fragments -- a summary built from those reads as
    truncated nonsense however well it was ranked.

    Bullet lines are kept as separate sentences even without terminal
    punctuation, because a document whose substance is a bullet list
    would otherwise summarize to nothing.
    """
    found: list[SummarySentence] = []
    for unit, bullet in _units(text):
        for piece in _SENTENCE_SPLIT.split(unit):
            candidate = " ".join(piece.split())
            if not candidate:
                continue
            words = len(candidate.split())
            if words < config.min_sentence_words or words > MAX_SENTENCE_WORDS:
                continue
            if (
                not bullet
                and not re.search(r"[.!?:]$", candidate)
                and words < MIN_SENTENCE_WORDS * 2
            ):
                continue
            found.append(
                SummarySentence(text=candidate, score=0.0, position=len(found), word_count=words)
            )
    return found


def _units(text: str) -> list[tuple[str, bool]]:
    """Unwrapped chunks of *text* with whether each is a bullet.

    A heading is dropped rather than unwrapped into the paragraph below
    it, which would otherwise produce "Overview On 14 March the payments
    API..." -- a sentence the document does not contain.
    """
    units: list[tuple[str, bool]] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            units.append((" ".join(buffer), False))
            buffer.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if _TABLE_ROW.match(stripped):
            # A table is structure, not prose. Its rows belong to the
            # table extractor, and a sentence ranker fed them will pick
            # one whenever the document is mostly table.
            flush()
            continue
        if _BULLET_PREFIX.match(stripped):
            flush()
            units.append((_BULLET_PREFIX.sub("", stripped), True))
            continue
        if _is_heading(line):
            flush()
            continue
        buffer.append(stripped)
    flush()
    return units


def _tokens(sentence: str) -> list[str]:
    """Content words from *sentence*, folded and stopword-free."""
    folded = unicodedata.normalize("NFKD", sentence.lower())
    plain = "".join(char for char in folded if not unicodedata.combining(char))
    return [word for word in _WORD.findall(plain) if word not in STOPWORDS]


def _term_weights(sentences: Sequence[SummarySentence]) -> Counter[str]:
    """How much each term contributes, by frequency across sentences.

    A term in every sentence carries no information about which sentence
    matters, so weights are damped by how widely a term is spread -- the
    same reason TF-IDF exists, applied within one document.
    """
    frequency: Counter[str] = Counter()
    spread: Counter[str] = Counter()
    for sentence in sentences:
        tokens = _tokens(sentence.text)
        frequency.update(tokens)
        spread.update(set(tokens))

    total = len(sentences)
    weighted: Counter[str] = Counter()
    for term, count in frequency.items():
        damping = math.log(1 + total / spread[term])
        weighted[term] = round(count * damping, 6)
    return weighted


def _rank(
    sentences: Sequence[SummarySentence], weights: Mapping[str, float], kind: SummaryKind
) -> list[SummarySentence]:
    """Sentences most-important first, each carrying its reasons."""
    audience = _audience_terms(kind)
    highest = max(len(sentence.text.split()) for sentence in sentences)

    # Divided by length, so a long sentence does not win merely by
    # containing more words than a short one that says more; then scaled
    # against the best sentence, so salience lands on 0..1. Without that
    # scaling the raw figure runs to several points and every bonus
    # below is lost in the noise -- which is what made an executive
    # summary and a technical one come out identical.
    raw = {
        sentence.position: (
            sum(weights.get(token, 0.0) for token in _tokens(sentence.text))
            / max(len(_tokens(sentence.text)), 1)
        )
        for sentence in sentences
    }
    ceiling = max(raw.values()) or 1.0

    for sentence in sentences:
        tokens = _tokens(sentence.text)
        if not tokens:
            sentence.score = 0.0
            continue
        salience = raw[sentence.position] / ceiling
        reasons = [f"term salience {salience:.3f}"]
        score = salience

        lead = _LEAD_BONUS * max(0.0, 1.0 - sentence.position / _LEAD_SPAN)
        if lead:
            score += lead
            reasons.append(f"appears early (+{lead:.3f})")

        if audience:
            hits = sorted({token for token in tokens if token in audience})
            if hits:
                bonus = _AUDIENCE_BONUS * min(len(hits), _MAX_AUDIENCE_HITS)
                score += bonus
                reasons.append(f"{kind!s} terms {hits} (+{bonus:.3f})")

        if sentence.word_count < highest / _SHORT_SENTENCE_DIVISOR:
            score -= _SHORT_SENTENCE_PENALTY
            reasons.append(f"unusually short (-{_SHORT_SENTENCE_PENALTY})")

        sentence.score = round(max(score, 0.0), 6)
        sentence.reasons = reasons
    return sorted(sentences, key=lambda item: (-item.score, item.position))


_LEAD_BONUS = 0.35
"""What appearing early is worth. Documents state their subject first,
and a purely frequency-ranked summary routinely opens on a mid-document
detail because the opening sentence was too short to score."""

_LEAD_SPAN = 5.0
"""How many sentences the lead bonus decays over."""

_AUDIENCE_BONUS = 0.12
_MAX_AUDIENCE_HITS = 3
"""Capped, so a sentence stuffed with jargon cannot outrank one that
actually says something."""

_SHORT_SENTENCE_DIVISOR = 3.0
_SHORT_SENTENCE_PENALTY = 0.15


def _audience_terms(kind: SummaryKind) -> frozenset[str]:
    """The vocabulary this summary's reader cares about."""
    if kind is SummaryKind.EXECUTIVE:
        return EXECUTIVE_TERMS
    if kind is SummaryKind.TECHNICAL:
        return TECHNICAL_TERMS
    return frozenset()


def _confidence(picked: Sequence[SummarySentence], ranked: Sequence[SummarySentence]) -> float:
    """How well the chosen sentences separated from the rest.

    A summary is trustworthy to the degree its sentences actually stood
    out. Where every sentence scores alike the selection is arbitrary,
    and reporting high confidence for an arbitrary choice is the failure
    worth avoiding.
    """
    if not picked:
        return 0.0
    if len(ranked) <= len(picked):
        return round(_FULL_COVERAGE_CONFIDENCE, 4)
    chosen_mean = sum(item.score for item in picked) / len(picked)
    rest = ranked[len(picked) :]
    rest_mean = sum(item.score for item in rest) / len(rest)
    if chosen_mean <= 0:
        return 0.0
    separation = (chosen_mean - rest_mean) / chosen_mean
    return round(min(_MIN_CONFIDENCE + separation, 0.99), 4)


_FULL_COVERAGE_CONFIDENCE = 0.95
"""A "summary" that kept every sentence is a faithful one, whatever else
it is."""

_MIN_CONFIDENCE = 0.5
"""The floor: an extractive summary is made of real sentences from the
document, so it is never worthless even when selection was arbitrary."""


def _truncate_words(text: str, limit: int) -> str:
    """*text* cut to *limit* words, with an ellipsis if anything was cut."""
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]) + " ..."


# ---- section summaries ----------------------------------------------------------


def _section_summary(text: str, config: SummaryConfig, summary: Summary) -> Summary:
    """One sentence per section, keyed by heading.

    The kind that answers "what is in this document" rather than "what
    does this document say", which is the question a reader of a long
    runbook or policy actually has.
    """
    sections = split_sections(text)
    if not sections:
        return summary

    per_section = max(1, config.sentence_count // max(len(sections), 1))
    parts: list[str] = []
    for title, body in sections.items():
        inner = summarize(
            body,
            kind=SummaryKind.EXTRACTIVE,
            config=SummaryConfig(
                sentence_count=per_section,
                max_words=config.max_words,
                min_sentence_words=config.min_sentence_words,
            ),
        )
        if not inner.text:
            continue
        summary.sections[title] = inner.text
        summary.sentences.extend(inner.sentences)
        parts.append(f"{title}: {inner.text}")

    summary.text = _truncate_words("\n".join(parts), config.max_words)
    summary.keywords = [
        term
        for term, _ in _term_weights(_sentences(text, config)).most_common(config.keyword_count)
    ]
    summary.confidence = round(_SECTION_CONFIDENCE if summary.sections else 0.0, 4)
    return summary


_SECTION_CONFIDENCE = 0.85
"""Section summaries are structural rather than judged, so their
confidence reflects the heading detection rather than a ranking."""


def split_sections(text: str) -> dict[str, str]:
    """Text split into ``heading -> body``.

    Content before the first heading is kept under ``"Introduction"``
    rather than discarded -- in most documents that preamble is the part
    stating what the document is for.
    """
    sections: dict[str, str] = {}
    title = "Introduction"
    body: list[str] = []
    for line in text.splitlines():
        if _is_heading(line):
            if any(entry.strip() for entry in body):
                sections[title] = "\n".join(body).strip()
            title = _heading_title(line)
            body = []
            continue
        body.append(line)
    if any(entry.strip() for entry in body):
        sections[title] = "\n".join(body).strip()
    return sections


def _is_heading(line: str) -> bool:
    """Whether *line* introduces a section.

    A markdown hash, a numbered heading, or a short line with no
    terminal punctuation -- the three ways plain-text documents mark a
    heading when they have no styling to do it with.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADING_LENGTH:
        return False
    if stripped.startswith("#"):
        return True
    if re.match(r"^\d+(?:\.\d+)*[.)]\s+\S", stripped):
        return True
    if stripped.endswith((".", ",", ";", "!", "?")):
        return False
    if _BULLET_PREFIX.match(stripped):
        return False
    return len(stripped.split()) <= _MAX_HEADING_WORDS and (
        stripped.isupper() or stripped[0].isupper()
    )


_MAX_HEADING_LENGTH = 80
_MAX_HEADING_WORDS = 8


def _heading_title(line: str) -> str:
    """The heading's own words, markers stripped."""
    stripped = line.strip().lstrip("#").strip()
    stripped = re.sub(r"^\d+(?:\.\d+)*[.)]?\s*", "", stripped)
    match = _HEADING.match(stripped)
    return (match.group("title").strip() if match else stripped) or "Section"


def summarize_many(
    text: str,
    kinds: Iterable[SummaryKind],
    *,
    config: SummaryConfig | None = None,
    backend: AbstractiveBackend | None = None,
) -> dict[SummaryKind, Summary]:
    """Several summaries of one document, keyed by kind.

    What the pipeline actually wants: a document gets its executive and
    technical summaries in one pass rather than being re-read per kind.
    """
    return {
        SummaryKind(str(kind)): summarize(text, kind=kind, config=config, backend=backend)
        for kind in kinds
    }


__all__ = [
    "DEFAULT_SENTENCE_COUNT",
    "EXECUTIVE_TERMS",
    "MAX_SENTENCE_WORDS",
    "MIN_SENTENCE_WORDS",
    "STOPWORDS",
    "TECHNICAL_TERMS",
    "AbstractiveBackend",
    "Summary",
    "SummaryConfig",
    "SummarySentence",
    "split_sections",
    "summarize",
    "summarize_many",
]
