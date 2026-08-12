"""Translation (docs/063 "TRANSLATION").

Language detection, glossary-driven terminology, and the machinery that
keeps the things which must not be translated out of the translator's
reach.

**Some text must survive translation unchanged.** A hostname, an error
code, a product name, a change identifier: translating ``payments-api``
into another language produces a string that refers to nothing. Those
spans are replaced with opaque placeholders before the backend sees the
text and restored afterwards, and any placeholder that does not come
back is reported rather than quietly left as a placeholder in the
output.

**A translation without a backend is not a translation.** With no
backend configured this module refuses rather than returning the source
text labelled as translated -- a caller storing that as the French
version of a document has been told a falsehood that nothing downstream
can detect.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.core.text import vocabulary

DEFAULT_SOURCE_LANGUAGE = "en"

MIN_DETECTION_CHARACTERS = 12
"""Below this there is not enough text to distinguish two languages that
share an alphabet, and a confident guess would be a fabrication."""

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

_PRESERVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url", re.compile(r"https?://\S+|www\.\S+")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("code", re.compile(r"`[^`\n]+`")),
    ("identifier", re.compile(r"\b[A-Z]{2,6}-\d{3,10}\b")),
    ("version", re.compile(r"\bv?\d+\.\d+(?:\.\d+)+\b")),
    # The trailing lookbehind keeps the sentence's own full stop out of
    # the path: without it "/etc/payments/pool.yaml." is protected whole
    # and the sentence comes back from translation with no end.
    ("path", re.compile(r"(?:/[\w.-]+){2,}/?(?<![.,;:])")),
    ("hostname", re.compile(r"\b(?:[a-z0-9]+(?:[.-][a-z0-9]+)+)\b")),
)
"""Ordered longest-construct first: the earliest match wins a span, so a
URL is protected whole rather than being carved up by the hostname
pattern inside it, and ``/etc/payments/pool.yaml`` is one path rather
than a loose ``/etc/payments/`` beside a "hostname" called
``pool.yaml``."""

_PLACEHOLDER = "{index}"
"""Private-use codepoints, so a placeholder cannot collide with anything
the source document legitimately contains."""

_PLACEHOLDER_FINDER = re.compile("(\\d+)")

LANGUAGE_PROFILES: Mapping[str, frozenset[str]] = {
    "en": vocabulary(
        "the and of to in that is was for with as on are be this have from by not or it at"
    ),
    "es": vocabulary("el la de que y en los se del las un por con no una para es su al lo como"),
    "fr": vocabulary(
        "le la de et les des en du un une pour dans que est qui par sur ne pas au avec"
    ),
    "de": vocabulary(
        "der die und in den von zu das mit sich des auf fur ist im dem nicht ein eine als"
    ),
    "pt": vocabulary("de que em nao os as um uma para com por dos das ao mais como mas foi ser"),
    "it": vocabulary("di che il la per un in una non sono con del si le della gli nel come piu"),
    "nl": vocabulary("de het een van en in dat is op te zijn voor met niet aan er die ook maar"),
}
"""Function words per language. Content words vary by document; function
words do not, which is what makes them a language signature."""

SCRIPT_LANGUAGES: Mapping[str, str] = {
    "CYRILLIC": "ru",
    "ARABIC": "ar",
    "HEBREW": "he",
    "HIRAGANA": "ja",
    "KATAKANA": "ja",
    "HANGUL": "ko",
    "DEVANAGARI": "hi",
    "THAI": "th",
    "GREEK": "el",
    "CJK": "zh",
}
"""A non-Latin script settles the language before any word list does."""


@dataclass(frozen=True, slots=True)
class LanguageGuess:
    """A detected language and how sure the detection is."""

    language: str
    confidence: float
    scores: Mapping[str, float] = field(default_factory=dict)
    is_reliable: bool = True

    def __str__(self) -> str:
        return self.language


class TranslationBackend(Protocol):
    """A translation engine.

    Receives text with preserved spans already replaced by placeholders,
    and must return them unchanged; this module verifies that it did.
    """

    def translate(self, text: str, *, source: str, target: str) -> str:
        """*text* rendered in *target*."""
        ...


class TranslationUnavailableError(RuntimeError):
    """Raised when translation was asked for and no backend can do it."""


@dataclass(frozen=True, slots=True, eq=False)
class GlossaryEntry:
    """One term with a fixed handling.

    Compared and hashed by identity. A frozen dataclass holding a mapping
    is not hashable by value -- its generated ``__hash__`` raises on the
    ``translations`` dict -- so a caller putting entries in a set or
    using one as a dictionary key would hit a ``TypeError`` at runtime
    rather than a type error at build time.
    """

    term: str
    translations: Mapping[str, str] = field(default_factory=dict)
    preserve: bool = False
    """Never translate this term, whatever the target language. For a
    product or system name that is the same word everywhere."""
    case_sensitive: bool = False


@dataclass(slots=True)
class Glossary:
    """The terms whose translation is decided in advance."""

    entries: list[GlossaryEntry] = field(default_factory=list)

    def add(self, entry: GlossaryEntry) -> None:
        self.entries.append(entry)

    def preserved(self) -> list[GlossaryEntry]:
        return [entry for entry in self.entries if entry.preserve]

    def for_target(self, target: str) -> list[tuple[GlossaryEntry, str]]:
        """Entries with a required rendering in *target*."""
        return [
            (entry, entry.translations[target])
            for entry in self.entries
            if not entry.preserve and target in entry.translations
        ]

    def sorted_terms(self) -> list[GlossaryEntry]:
        """Entries longest term first.

        Longest-first matters: with "change request" and "change" both in
        the glossary, matching the short one first leaves "request"
        stranded and the phrase mistranslated.
        """
        return sorted(self.entries, key=lambda entry: len(entry.term), reverse=True)


@dataclass(slots=True)
class TranslationResult:
    """One translation, with everything needed to trust or reject it."""

    text: str = ""
    source_language: str = DEFAULT_SOURCE_LANGUAGE
    target_language: str = ""
    confidence: float = 0.0
    detected: LanguageGuess | None = None
    preserved_terms: list[str] = field(default_factory=list)
    glossary_applied: list[str] = field(default_factory=list)
    lost_placeholders: list[str] = field(default_factory=list)
    """Protected spans the backend failed to return. A non-empty list
    means the output is missing text the source had."""
    warnings: list[str] = field(default_factory=list)

    @property
    def is_faithful(self) -> bool:
        """Whether every protected span survived."""
        return not self.lost_placeholders


@dataclass(frozen=True, slots=True)
class TranslationConfig:
    """How translation behaves."""

    preserve_identifiers: bool = True
    preserve_urls: bool = True
    preserve_code: bool = True
    minimum_detection_confidence: float = 0.35
    skip_when_same_language: bool = True
    """Return the source unchanged when it is already in the target
    language, rather than paying a backend to round-trip it."""


def detect_language(text: str) -> LanguageGuess:
    """Which language *text* is written in.

    Script first, function words second. A Cyrillic document is Russian
    before any word list is consulted, and no amount of English function
    words in a Latin-script document can make it Japanese.
    """
    stripped = text.strip()
    if len(stripped) < MIN_DETECTION_CHARACTERS:
        return LanguageGuess(language=DEFAULT_SOURCE_LANGUAGE, confidence=0.0, is_reliable=False)

    script = _dominant_script(stripped)
    if script in SCRIPT_LANGUAGES:
        return LanguageGuess(language=SCRIPT_LANGUAGES[script], confidence=0.95)

    words = [_fold(word) for word in _WORD.findall(stripped.lower())]
    if not words:
        return LanguageGuess(language=DEFAULT_SOURCE_LANGUAGE, confidence=0.0, is_reliable=False)

    scores = {
        language: sum(1 for word in words if word in profile) / len(words)
        for language, profile in LANGUAGE_PROFILES.items()
    }
    ranked = sorted(scores.items(), key=lambda item: -item[1])
    best, best_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    if best_score <= 0:
        return LanguageGuess(
            language=DEFAULT_SOURCE_LANGUAGE,
            confidence=0.0,
            scores=scores,
            is_reliable=False,
        )

    # Confidence is the margin over the next candidate, not the raw hit
    # rate. A document scoring 0.2 on English and 0.19 on Dutch is not an
    # 80%-confident English document, however high the raw figure looks.
    margin = (best_score - runner_up) / best_score
    confidence = round(min(_DETECTION_FLOOR + margin * _DETECTION_SPAN, 0.99), 4)
    return LanguageGuess(
        language=best,
        confidence=confidence,
        scores={key: round(value, 4) for key, value in scores.items()},
        is_reliable=confidence >= _RELIABLE_DETECTION,
    )


_DETECTION_FLOOR = 0.35
_DETECTION_SPAN = 0.6
_RELIABLE_DETECTION = 0.5


def _dominant_script(text: str) -> str:
    """The script most of *text* is written in."""
    counts: dict[str, int] = {}
    for char in text:
        if not char.isalpha():
            continue
        name = unicodedata.name(char, "")
        script = next(
            (key for key in SCRIPT_LANGUAGES if key in name),
            "CJK" if "CJK" in name else "LATIN",
        )
        counts[script] = counts.get(script, 0) + 1
    if not counts:
        return "LATIN"
    return max(counts.items(), key=lambda item: item[1])[0]


def _fold(word: str) -> str:
    """*word* with accents removed, so profiles need no accented forms."""
    decomposed = unicodedata.normalize("NFKD", word)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def translate(
    text: str,
    *,
    target: str,
    backend: TranslationBackend | None = None,
    source: str | None = None,
    glossary: Glossary | None = None,
    config: TranslationConfig | None = None,
) -> TranslationResult:
    """Translate *text* into *target*.

    Raises:
        TranslationUnavailableError: When no backend is configured. There
            is no honest degraded translation -- returning the source
            would mean storing English text as the French version of a
            document, with nothing downstream able to tell.
    """
    settings = config or TranslationConfig()
    result = TranslationResult(target_language=target)

    guess = detect_language(text)
    result.detected = guess
    result.source_language = source or guess.language
    if source is None and not guess.is_reliable:
        result.warnings.append(
            f"Source language was detected as {guess.language!r} at "
            f"{guess.confidence} confidence, which is below the reliable "
            "threshold; pass source explicitly if this is wrong."
        )

    if not text.strip():
        result.confidence = 0.0
        return result

    if settings.skip_when_same_language and result.source_language == target:
        result.text = text
        result.confidence = 1.0
        result.warnings.append(
            f"Text is already in {target!r}; returned unchanged without translating."
        )
        return result

    if backend is None:
        raise TranslationUnavailableError(
            f"No translation backend is configured, so {text.strip()[:40]!r} "
            f"cannot be translated into {target!r}."
        )

    protected, spans = protect(text, glossary=glossary, config=settings)
    # The values, not the keys: the keys are opaque placeholder tokens
    # and this field is what a reviewer reads to see what was held back.
    result.preserved_terms = list(spans.values())

    translated = backend.translate(protected, source=result.source_language, target=target)
    restored, lost = restore(translated, spans)
    result.lost_placeholders = lost
    result.text = restored

    if glossary is not None:
        result.text, result.glossary_applied = _apply_glossary(result.text, glossary, target)

    result.confidence = _translation_confidence(guess, lost, spans, explicit=source is not None)
    if lost:
        result.warnings.append(
            f"{len(lost)} protected term(s) did not survive the backend and are "
            "missing from the output."
        )
    return result


def protect(
    text: str,
    *,
    glossary: Glossary | None = None,
    config: TranslationConfig | None = None,
) -> tuple[str, dict[str, str]]:
    """*text* with untranslatable spans replaced, and what they were.

    Spans are found on the original text and substituted from the end
    backwards, so replacing one cannot shift the offsets of the ones
    still to be replaced.
    """
    settings = config or TranslationConfig()
    enabled = {
        "url": settings.preserve_urls,
        "email": settings.preserve_urls,
        "code": settings.preserve_code,
        "identifier": settings.preserve_identifiers,
        "version": settings.preserve_identifiers,
        "hostname": settings.preserve_identifiers,
        "path": settings.preserve_identifiers,
    }

    found: list[tuple[int, int, str]] = []
    for name, pattern in _PRESERVE_PATTERNS:
        if not enabled.get(name, True):
            continue
        for match in pattern.finditer(text):
            if not any(start < match.end() and match.start() < end for start, end, _ in found):
                found.append((match.start(), match.end(), match.group()))

    if glossary is not None:
        for entry in glossary.preserved():
            flags = 0 if entry.case_sensitive else re.IGNORECASE
            for match in re.finditer(rf"\b{re.escape(entry.term)}\b", text, flags):
                if not any(start < match.end() and match.start() < end for start, end, _ in found):
                    found.append((match.start(), match.end(), match.group()))

    found.sort(key=lambda item: item[0])
    spans: dict[str, str] = {}
    result = text
    for index, (start, end, value) in reversed(list(enumerate(found))):
        token = _PLACEHOLDER.format(index=index)
        spans[token] = value
        result = result[:start] + token + result[end:]
    return result, spans


def restore(text: str, spans: Mapping[str, str]) -> tuple[str, list[str]]:
    """*text* with placeholders put back, and the values that went missing.

    Any placeholder the backend invented but that was never issued is
    stripped, because leaving a private-use control pair in delivered
    prose is worse than losing whatever the backend meant by it.
    """
    result = text
    lost: list[str] = []
    for token, value in spans.items():
        if token in result:
            result = result.replace(token, value)
        else:
            lost.append(value)
    return _PLACEHOLDER_FINDER.sub("", result), lost


def _apply_glossary(text: str, glossary: Glossary, target: str) -> tuple[str, list[str]]:
    """Force glossary renderings into *text*, longest term first."""
    applied: list[str] = []
    result = text
    required = {entry.term: rendering for entry, rendering in glossary.for_target(target)}
    for entry in glossary.sorted_terms():
        if entry.term not in required:
            continue
        replacement = required[entry.term]
        flags = 0 if entry.case_sensitive else re.IGNORECASE
        pattern = rf"\b{re.escape(entry.term)}\b"
        result, count = re.subn(pattern, replacement, result, flags=flags)
        if count:
            applied.append(entry.term)
    return result, applied


def _translation_confidence(
    guess: LanguageGuess,
    lost: Sequence[str],
    spans: Mapping[str, str],
    *,
    explicit: bool,
) -> float:
    """How much the translation can be trusted.

    Bounded above by the source-language detection, because a translation
    from the wrong source language is wrong however fluent it reads --
    unless the caller stated the source, in which case detection is not
    part of the chain at all.
    """
    score = 0.95 if explicit else max(guess.confidence, _DETECTION_FLOOR)
    if spans and lost:
        score *= 1.0 - len(lost) / len(spans)
    return round(max(min(score, 0.99), 0.0), 4)


def translate_many(
    text: str,
    targets: Iterable[str],
    *,
    backend: TranslationBackend | None = None,
    source: str | None = None,
    glossary: Glossary | None = None,
    config: TranslationConfig | None = None,
) -> dict[str, TranslationResult]:
    """Translate *text* into several languages, keyed by target.

    Detection runs once for all of them, which is both faster and more
    consistent than letting each target reach its own conclusion about
    what language the source was in.
    """
    guess = detect_language(text)
    resolved = source or guess.language
    return {
        target: translate(
            text,
            target=target,
            backend=backend,
            source=resolved,
            glossary=glossary,
            config=config,
        )
        for target in targets
    }


__all__ = [
    "DEFAULT_SOURCE_LANGUAGE",
    "LANGUAGE_PROFILES",
    "MIN_DETECTION_CHARACTERS",
    "SCRIPT_LANGUAGES",
    "Glossary",
    "GlossaryEntry",
    "LanguageGuess",
    "TranslationBackend",
    "TranslationConfig",
    "TranslationResult",
    "TranslationUnavailableError",
    "detect_language",
    "protect",
    "restore",
    "translate",
    "translate_many",
]
