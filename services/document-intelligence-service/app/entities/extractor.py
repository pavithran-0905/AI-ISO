"""Entity extraction (docs/063 "ENTITY EXTRACTION").

Pattern and heuristic extraction over document text. **No model, and that
is a decision rather than a shortfall.** A general-purpose NER model is
good at people and organisations and poor at exactly the entities this
platform reasons over -- hostnames, asset tags, serial numbers, IP
addresses -- because those are format-defined rather than
context-defined. A regular expression that knows what an RFC 1123
hostname looks like beats a language model at recognising one, is
auditable, costs nothing, and gives the same answer twice.

Where the deterministic approach is genuinely weaker -- a person's name
in running prose -- that is stated in the extractor's own docstring and
its confidence reflects it, rather than being papered over.

**Every match is normalised and scored.** The normalised form is what
downstream filters and joins use, because "ACME Corp." and "acme corp"
are one organisation and matching raw text finds one of them. The score
is what decides whether a value is acted on or reviewed, and a value
without one is a guess presented as a fact.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field

from app.models.enums import EntityKind, ExtractionMethod

CONTEXT_WINDOW = 120
"""Characters either side of a match kept as context. Enough to show the
sentence a reviewer needs; short enough that ten thousand entities do not
duplicate the document."""

MAX_VALUE_LENGTH = 2_048

MIN_HOSTNAME_LABELS = 2
"""A bare single label is a word, not a host. Two is the minimum that
distinguishes ``db-01.internal`` from ``restart``."""

_BARE_IDENTIFIER_CONFIDENCE = 0.68
"""Below the labelled form's 0.86. The hyphen and the shape are evidence;
a nearby "incident" is better evidence, and the two should not be trusted
equally."""

MAX_HOSTNAME_LENGTH = 253
"""RFC 1035's limit on a fully-qualified name. Anything longer is not a
hostname however much it looks like one."""


@dataclass(frozen=True, slots=True)
class ExtractedEntity:
    """One entity found in one document."""

    kind: EntityKind
    value: str
    normalized_value: str
    start: int
    end: int
    confidence: float
    method: ExtractionMethod = ExtractionMethod.PATTERN
    context: str = ""
    custom_kind: str = ""

    @property
    def span(self) -> tuple[int, int]:
        return (self.start, self.end)


@dataclass(frozen=True, slots=True)
class CustomEntityPattern:
    """An organization's own entity type.

    Supplied at call time rather than compiled in, so adding a tenant's
    asset-tag format is configuration rather than a release.
    """

    name: str
    pattern: str
    confidence: float = 0.7
    kind: EntityKind = EntityKind.CUSTOM

    def compiled(self) -> re.Pattern[str]:
        """The compiled pattern.

        Raises:
            ValueError: If the pattern does not compile. Refused at use
                rather than silently matching nothing, which is how a
                typo'd tenant pattern becomes "extraction found no asset
                tags in any document" six weeks later.
        """
        try:
            return re.compile(self.pattern, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(
                f"Custom entity pattern {self.name!r} is not a valid regular " f"expression: {exc}"
            ) from exc


# ---- the patterns -----------------------------------------------------------

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

_URL = re.compile(r"\bhttps?://[^\s<>\"'\)\]]+", re.IGNORECASE)

_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b")

_IPV6 = re.compile(r"\b(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?:/\d{1,3})?\b")

_PHONE = re.compile(
    r"(?<![\w.])"
    r"(?:\+\d{1,3}[\s.-]?)?"
    r"(?:\(\d{2,4}\)[\s.-]?|\d{2,4}[\s.-])"
    r"\d{3,4}[\s.-]?\d{3,4}"
    r"(?![\w])(?!\.\d)"
)
"""Deliberately conservative. A permissive phone pattern matches every
order number, port range, and version string in an infrastructure
document, and an entity list that is 80% false positives is one nobody
reads.

**The trailing guard rejects a following word character or a dot that is
itself followed by a digit -- not a bare dot.** The first two are what
distinguish a phone number from a version string or a dotted quad; a
plain full stop is how most sentences containing a phone number end, and
refusing those found no phone numbers at all in the verification
document. Caught by running it, not by reading it."""

_HOSTNAME = re.compile(
    r"\b(?=[a-z0-9-]{1,63}(?:\.[a-z0-9-]{1,63})+\b)"
    r"(?!\d+\.\d+\.\d+\.\d+\b)"
    r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+\b",
    re.IGNORECASE,
)
"""RFC 1123 labels, with a lookahead that refuses anything shaped like a
dotted quad -- an IP is an IP, and reporting it as both is two entities
where there is one thing."""

_ISO_DATE = re.compile(r"\b(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b")

_TEXTUAL_DATE = re.compile(
    r"\b(\d{1,2})\s+"
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+(\d{4})\b",
    re.IGNORECASE,
)

_US_DATE = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+(\d{1,2}),?\s+(\d{4})\b",
    re.IGNORECASE,
)

_CURRENCY = re.compile(
    r"(?:(?P<symbol>[$£€¥])\s?(?P<amount>\d[\d,]*(?:\.\d{1,2})?)"
    r"|(?P<amount2>\d[\d,]*(?:\.\d{1,2})?)\s?(?P<code>USD|EUR|GBP|JPY|INR|AUD|CAD|CHF))",
    re.IGNORECASE,
)

_SERIAL = re.compile(
    r"\b(?:serial(?:\s+(?:number|no\.?))?|s/n|sn)\s*[:#-]?\s*([A-Z0-9][A-Z0-9-]{4,})\b",
    re.IGNORECASE,
)
"""Anchored on the label rather than on the shape. A bare alphanumeric
run is indistinguishable from a build number, a commit hash, or a licence
key; the word "serial" beside it is what makes it a serial number."""

_ASSET = re.compile(
    r"\b(?:asset(?:\s+(?:tag|id|name))?|ci|configuration\s+item)\s*[:#-]?\s*"
    r"([A-Z0-9][A-Z0-9._-]{2,})\b",
    re.IGNORECASE,
)

_LABELLED_IDENTIFIER = re.compile(
    r"\b(?:(?:ticket|incident|change|request|case|ref(?:erence)?|order|invoice|po)"
    r"\s*(?:number|no\.?|id|#)?\s*[:#-]?\s*)([A-Z]{2,6}-?\d{3,10})\b",
    re.IGNORECASE,
)

_BARE_IDENTIFIER = re.compile(r"\b([A-Z]{2,6}-\d{3,10})\b")
"""A hyphenated reference with no adjacent label -- ``INC-004821`` in a
title, where the label is two words away and the labelled pattern misses
it entirely. Requires the hyphen and uppercase letters, which is what
separates a ticket reference from a part number or a random token, and
scores lower than the labelled form because a nearby "incident" is real
evidence and a shape is only a shape."""

_ORGANIZATION = re.compile(
    r"\b([A-Z][A-Za-z0-9&\u0027\u2019.-]*(?:\s+[A-Z][A-Za-z0-9&\u0027\u2019.-]*){0,4})\s+"
    r"(Inc\.?|LLC|Ltd\.?|Limited|GmbH|B\.?V\.?|S\.?A\.?|PLC|Corp\.?|Corporation|"
    r"Company|Co\.|Holdings|Group|Partners|Technologies|Systems|Solutions)\b"
)
"""Anchored on a legal or trading suffix, because that is what actually
distinguishes an organisation from any other capitalised phrase. A
capitalisation-only heuristic labels every sentence-initial word and
every heading an organisation."""

_NAME = r"[A-Z][a-z]+(?:[ \t]+[A-Z]\.?)?(?:[ \t]+[A-Z][a-z]+){0,2}"
"""Intra-name separators are spaces and tabs, never ``\\s``.

``\\s`` matches a newline, so a name ending a line swallowed the first
capitalised word of the next one -- the verification document produced
the person ``"Jane Okafor\\nPrepared"``. A name does not span lines, and
only running it over a real multi-line document showed that."""

_TITLED_PERSON = re.compile(rf"\b(Mr|Mrs|Ms|Miss|Dr|Prof|Sir|Dame)\.?[ \t]+({_NAME})\b")

_LABELLED_PERSON = re.compile(
    r"\b(?:reviewed|approved|prepared|authored|signed|submitted|requested)[ \t]+by"
    rf"[ \t]*[:\-]?[ \t]*({_NAME})\b",
    re.IGNORECASE,
)
"""Anchored on a title or an explicit role label, and nothing else.

**The honest limit of this module.** A person named in running prose with
neither -- "the change was made by jane after the outage" -- is not found
here, and a language model would find it. Reporting a
capitalised-bigram heuristic as person extraction would fill the entity
table with headings and product names, which is worse than a gap somebody
knows about."""

_ADDRESS = re.compile(
    r"\b(\d{1,5}[A-Za-z]?\s+(?:[A-Z][A-Za-z.'-]*\s+){1,4}"
    r"(?:Street|St\.?|Road|Rd\.?|Avenue|Ave\.?|Boulevard|Blvd\.?|Lane|Ln\.?|Drive|Dr\.?|"
    r"Court|Ct\.?|Way|Place|Pl\.?|Terrace|Square|Sq\.?))"
    r"(?:,\s*[A-Z][A-Za-z.'-]+)*"
    r"(?:,?\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)?",
)

_MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)

_WHITESPACE = re.compile(r"\s+")


# ---- normalisation ------------------------------------------------------------


def normalize(kind: EntityKind, value: str) -> str:
    """The canonical form of *value* for its kind.

    What downstream filters and joins match on. Case-folding alone is not
    enough: a hostname's trailing dot, a phone number's punctuation, and
    a date's spelling all vary between documents describing the same
    thing.
    """
    collapsed = _WHITESPACE.sub(" ", value).strip()
    normalizer = _NORMALIZERS.get(kind)
    return normalizer(collapsed) if normalizer else collapsed.lower()


def _normalize_trimmed(value: str) -> str:
    """Lowercased, with the trailing dot or slash a document often carries."""
    return value.lower().rstrip(".").rstrip("/")


def _normalize_digits(value: str) -> str:
    """Digits and a leading plus, so punctuation stops mattering."""
    return re.sub(r"[^\d+]", "", value)


def _normalize_upper(value: str) -> str:
    """Uppercase and unspaced, for the identifier-shaped kinds."""
    return value.upper().replace(" ", "")


def _normalize_ip(value: str) -> str:
    """An IP address in its canonical form, or the input unchanged.

    ``2001:0db8::0001`` and ``2001:db8::1`` are one address, and a
    filter that compares the strings finds one of them. Returning the
    input for something unparseable rather than raising: the pattern is
    permissive on purpose and validation belongs to the caller that
    scored it.
    """
    candidate, _, prefix = value.partition("/")
    try:
        canonical = str(ipaddress.ip_address(candidate))
    except ValueError:
        return value.lower()
    return f"{canonical}/{prefix}" if prefix else canonical


def _normalize_date(value: str) -> str:
    """An ISO date, where the input can be read as one.

    Deliberately no ambiguous numeric formats: ``03/04/2024`` is March
    the fourth or the third of April depending on where the document was
    written, and this service cannot know which. Guessing produces dates
    that are wrong for half the world and confidently so, so those are
    not matched at all.
    """
    iso = _ISO_DATE.fullmatch(value)
    if iso:
        return value
    textual = _TEXTUAL_DATE.fullmatch(value)
    if textual:
        day, month, year = textual.groups()
        return f"{year}-{_MONTHS.index(month.lower()) + 1:02d}-{int(day):02d}"
    american = _US_DATE.fullmatch(value)
    if american:
        month, day, year = american.groups()
        return f"{year}-{_MONTHS.index(month.lower()) + 1:02d}-{int(day):02d}"
    return value.lower()


_SYMBOL_CODES = {"$": "USD", "£": "GBP", "€": "EUR", "¥": "JPY"}


def _normalize_currency(value: str) -> str:
    """An amount as ``CODE amount``, so two spellings compare equal."""
    match = _CURRENCY.fullmatch(value.strip())
    if not match:
        return value.lower()
    symbol = match.group("symbol")
    if symbol:
        amount = match.group("amount")
        code = _SYMBOL_CODES.get(symbol, symbol)
    else:
        amount = match.group("amount2")
        code = (match.group("code") or "").upper()
    return f"{code} {amount.replace(',', '')}".strip()


_NORMALIZERS: Mapping[EntityKind, Callable[[str], str]] = {
    EntityKind.EMAIL: _normalize_trimmed,
    EntityKind.HOSTNAME: _normalize_trimmed,
    EntityKind.URL: _normalize_trimmed,
    EntityKind.IP_ADDRESS: _normalize_ip,
    EntityKind.PHONE: _normalize_digits,
    EntityKind.DATE: _normalize_date,
    EntityKind.CURRENCY: _normalize_currency,
    EntityKind.SERIAL_NUMBER: _normalize_upper,
    EntityKind.ASSET_NAME: _normalize_upper,
    EntityKind.IDENTIFIER: _normalize_upper,
}
"""Per-kind normalisers. A dispatch table rather than a chain of
branches, so adding a kind is one entry rather than one more place to
forget."""


# ---- extraction ---------------------------------------------------------------


@dataclass(slots=True)
class ExtractionConfig:
    """How much to extract, and how sure to be before reporting it."""

    minimum_confidence: float = 0.5
    max_entities: int = 5_000
    kinds: frozenset[EntityKind] | None = None
    """Which kinds to look for. ``None`` means all of them; a caller that
    only wants hostnames should not pay for date parsing over a
    thousand-page document."""
    custom_patterns: tuple[CustomEntityPattern, ...] = ()
    context_window: int = CONTEXT_WINDOW

    def wants(self, kind: EntityKind) -> bool:
        return self.kinds is None or kind in self.kinds


_PATTERN_CONFIDENCE: Mapping[EntityKind, float] = {
    EntityKind.EMAIL: 0.97,
    EntityKind.URL: 0.95,
    EntityKind.IP_ADDRESS: 0.93,
    EntityKind.HOSTNAME: 0.80,
    EntityKind.DATE: 0.90,
    EntityKind.CURRENCY: 0.88,
    EntityKind.PHONE: 0.72,
    EntityKind.SERIAL_NUMBER: 0.85,
    EntityKind.ASSET_NAME: 0.82,
    EntityKind.IDENTIFIER: 0.86,
    EntityKind.ORGANIZATION: 0.75,
    EntityKind.PERSON: 0.70,
    EntityKind.ADDRESS: 0.70,
}
"""Per-kind base confidence, reflecting how much the *pattern* actually
proves. An email address matching the email pattern is almost certainly
an email address; a capitalised phrase before "Ltd" is probably an
organisation. Flattening these to one number would make the review
threshold meaningless."""


def extract_entities(text: str, config: ExtractionConfig | None = None) -> list[ExtractedEntity]:
    """Every entity in *text*, ordered by position and deduplicated.

    Overlapping matches are resolved by keeping the longer span, then the
    higher confidence. An IP address inside a URL is one entity in two
    readings, and returning both makes every count wrong.
    """
    settings = config or ExtractionConfig()
    if not text.strip():
        return []

    found = list(_scan(text, settings))
    kept = _resolve_overlaps(found)
    kept = [entity for entity in kept if entity.confidence >= settings.minimum_confidence]
    return kept[: settings.max_entities]


def _scan(text: str, config: ExtractionConfig) -> Iterator[ExtractedEntity]:
    """Every candidate match, before overlap resolution."""
    yield from _scan_whole_match(text, config)
    yield from _scan_captured(text, config)
    yield from _scan_custom(text, config)


def _scan_whole_match(text: str, config: ExtractionConfig) -> Iterator[ExtractedEntity]:
    """Patterns where the whole match is the entity."""
    simple: tuple[tuple[EntityKind, re.Pattern[str]], ...] = (
        (EntityKind.EMAIL, _EMAIL),
        (EntityKind.URL, _URL),
        (EntityKind.IP_ADDRESS, _IPV4),
        (EntityKind.IP_ADDRESS, _IPV6),
        (EntityKind.HOSTNAME, _HOSTNAME),
        (EntityKind.DATE, _ISO_DATE),
        (EntityKind.DATE, _TEXTUAL_DATE),
        (EntityKind.DATE, _US_DATE),
        (EntityKind.CURRENCY, _CURRENCY),
        (EntityKind.PHONE, _PHONE),
        (EntityKind.ADDRESS, _ADDRESS),
    )
    for kind, pattern in simple:
        if not config.wants(kind):
            continue
        for match in pattern.finditer(text):
            value = match.group(0)
            confidence = _score(kind, value)
            if confidence <= 0.0:
                continue
            yield _build(kind, value, match.start(), match.end(), confidence, text, config)


def _scan_captured(text: str, config: ExtractionConfig) -> Iterator[ExtractedEntity]:
    """Patterns anchored on a label, where a capture group is the entity."""
    captured: tuple[tuple[EntityKind, re.Pattern[str], int], ...] = (
        (EntityKind.SERIAL_NUMBER, _SERIAL, 1),
        (EntityKind.ASSET_NAME, _ASSET, 1),
        (EntityKind.IDENTIFIER, _LABELLED_IDENTIFIER, 1),
        (EntityKind.PERSON, _TITLED_PERSON, 2),
        (EntityKind.PERSON, _LABELLED_PERSON, 1),
    )
    for kind, pattern, group in captured:
        if not config.wants(kind):
            continue
        for match in pattern.finditer(text):
            value = match.group(group)
            if not value:
                continue
            yield _build(
                kind,
                value,
                match.start(group),
                match.end(group),
                _PATTERN_CONFIDENCE[kind],
                text,
                config,
            )

    if config.wants(EntityKind.IDENTIFIER):
        for match in _BARE_IDENTIFIER.finditer(text):
            yield _build(
                EntityKind.IDENTIFIER,
                match.group(1),
                match.start(1),
                match.end(1),
                _BARE_IDENTIFIER_CONFIDENCE,
                text,
                config,
            )

    if config.wants(EntityKind.ORGANIZATION):
        for match in _ORGANIZATION.finditer(text):
            yield _build(
                EntityKind.ORGANIZATION,
                match.group(0),
                match.start(),
                match.end(),
                _PATTERN_CONFIDENCE[EntityKind.ORGANIZATION],
                text,
                config,
            )


def _scan_custom(text: str, config: ExtractionConfig) -> Iterator[ExtractedEntity]:
    """The organization's own patterns."""
    for custom in config.custom_patterns:
        for match in custom.compiled().finditer(text):
            value = match.group(match.lastindex or 0)
            if not value:
                continue
            index = match.lastindex or 0
            yield _build(
                custom.kind,
                value,
                match.start(index),
                match.end(index),
                custom.confidence,
                text,
                config,
                custom_kind=custom.name,
            )


def _build(
    kind: EntityKind,
    value: str,
    start: int,
    end: int,
    confidence: float,
    text: str,
    config: ExtractionConfig,
    *,
    custom_kind: str = "",
) -> ExtractedEntity:
    """One entity record, with its context cut from the source."""
    trimmed = value.strip()[:MAX_VALUE_LENGTH]
    window = config.context_window
    return ExtractedEntity(
        kind=kind,
        value=trimmed,
        normalized_value=normalize(kind, trimmed)[:MAX_VALUE_LENGTH],
        start=start,
        end=end,
        confidence=round(confidence, 4),
        method=ExtractionMethod.PATTERN if not custom_kind else ExtractionMethod.TEMPLATE,
        context=_WHITESPACE.sub(" ", text[max(0, start - window) : end + window]).strip(),
        custom_kind=custom_kind,
    )


def _score(kind: EntityKind, value: str) -> float:
    """The confidence for one match, after kind-specific validation.

    Returns ``0.0`` for a match the pattern found and the semantics
    reject -- ``999.1.1.1`` is shaped like an IP address and is not one.
    Reporting it at reduced confidence would leave it in the table for a
    reviewer to reject one at a time.
    """
    base = _PATTERN_CONFIDENCE.get(kind, 0.5)
    if kind is EntityKind.IP_ADDRESS:
        candidate, _, _prefix = value.partition("/")
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            return 0.0
        # A private or loopback address in an infrastructure document is
        # more likely to be the real subject than a public one, which is
        # as often an example in prose.
        return min(base + 0.03, 1.0) if address.is_private else base
    if kind is EntityKind.HOSTNAME:
        label_count = value.count(".") + 1
        if label_count < MIN_HOSTNAME_LABELS or len(value) > MAX_HOSTNAME_LENGTH:
            return 0.0
        # A deeper name is more likely to be a real host than a bare
        # two-label string, which is as often a filename or a version.
        return min(base + 0.05 * (label_count - MIN_HOSTNAME_LABELS), 0.95)
    if kind is EntityKind.DATE:
        return base
    return base


def _resolve_overlaps(entities: Sequence[ExtractedEntity]) -> list[ExtractedEntity]:
    """Keep one entity per span, preferring the longer, surer reading.

    Sorted by start, then by descending length, then by descending
    confidence, so the first match at any position is the one to keep and
    everything it covers is dropped.
    """
    ordered = sorted(
        entities, key=lambda item: (item.start, -(item.end - item.start), -item.confidence)
    )
    kept: list[ExtractedEntity] = []
    covered_to = -1
    for entity in ordered:
        if entity.start < covered_to:
            continue
        kept.append(entity)
        covered_to = entity.end
    return kept


def group_by_kind(
    entities: Sequence[ExtractedEntity],
) -> dict[EntityKind, list[ExtractedEntity]]:
    """Entities bucketed by kind, in the order they were found."""
    grouped: dict[EntityKind, list[ExtractedEntity]] = {}
    for entity in entities:
        grouped.setdefault(entity.kind, []).append(entity)
    return grouped


def distinct_values(entities: Sequence[ExtractedEntity], kind: EntityKind) -> list[str]:
    """The distinct normalised values of one kind, first-seen order.

    Deduplicated on the normalised form, which is the point of having
    one: a document naming ``db-01.example.com`` eight times mentions one
    host.
    """
    seen: dict[str, None] = {}
    for entity in entities:
        if entity.kind == kind:
            seen.setdefault(entity.normalized_value, None)
    return list(seen)


@dataclass(slots=True)
class ExtractionSummary:
    """What one extraction pass produced, for the job record."""

    entities: list[ExtractedEntity] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.entities)

    @property
    def counts(self) -> dict[str, int]:
        return {str(kind): len(items) for kind, items in group_by_kind(self.entities).items()}

    @property
    def mean_confidence(self) -> float | None:
        """``None`` when nothing was found -- not ``0.0``, which would
        read as an extractor that found things and doubted all of them."""
        if not self.entities:
            return None
        return sum(entity.confidence for entity in self.entities) / len(self.entities)


__all__ = [
    "CONTEXT_WINDOW",
    "CustomEntityPattern",
    "ExtractedEntity",
    "ExtractionConfig",
    "ExtractionSummary",
    "distinct_values",
    "extract_entities",
    "group_by_kind",
    "normalize",
]
