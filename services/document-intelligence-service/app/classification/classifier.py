"""Document classification (docs/063 "DOCUMENT CLASSIFICATION").

Four methods over one document: explicit **rules** an organization wrote,
**keyword** evidence weighted by how distinctive each term is, **structure**
(does it read like a form? a log? a table?), and **template** matching
against a known layout. Each produces its own labels with its own
confidence, and the results are fused.

**Multi-label by default.** A document that is both a policy and a
certificate is genuinely both, and forcing a single winner loses whichever
one the router needed. Single-label is available and is a caller's
choice.

**Every label carries its rationale.** A classification nobody can
explain is one nobody can correct -- and correcting the *rule* is the
only thing that fixes the next thousand documents. The matched terms and
the deciding rule travel with the label.

**No model.** The spec's DO NOT IMPLEMENT list rules out
business-specific document templates, which is most of what a trained
document classifier encodes; and a classifier whose decisions cannot be
explained to the person overriding them is one they will stop trusting.
The AI method is declared in :class:`~app.models.enums.ClassificationMethod`
and is where a deployment plugs one in.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from app.models.enums import ClassificationMethod, DocumentCategory

DEFAULT_MINIMUM_CONFIDENCE = 0.35
"""Below this, a label is noise. Every document contains the word
"report" somewhere."""

MAX_LABELS = 5
"""More than this and the classification says nothing. A document
labelled with everything has been labelled with nothing."""

_TOKEN = re.compile(r"[a-z][a-z0-9-]{1,}")
_LINE = re.compile(r"^.*$", re.MULTILINE)
MAX_FIELD_VALUE_WORDS = 5
"""A form field's value is a name, a date, an identifier, or a tick --
not a sentence. Five words is generous for all four and short of any
prose."""

_KEY_VALUE_LINE = re.compile(
    r"^[ \t]*(?![0-9]{2,})(?P<label>[A-Za-z][A-Za-z \t/()#-]{1,40})[ \t]*[:=][ \t]*"
    r"(?P<value>\S+(?:[ \t]+\S+){0," + str(MAX_FIELD_VALUE_WORDS - 1) + r"})[ \t]*$"
)
"""A form field: a short alphabetic label, a separator, and a *short*
value that ends the line.

Every constraint here was earned by a false positive the verification
found, not anticipated:

- The label may not start with two or more digits. Without that, a log
  line's timestamp (``2024-03-11 04:21:11 INFO ...``) reads as
  ``label: value`` and twelve log lines classify as a form.
- The value is capped at five words and must reach the end of the line.
  Without that, a prose sentence introduced by a colon --
  ``"Prerequisite: you have the snapshot id and the on-call escalation
  path."`` -- does the same to a runbook, which then carries a spurious
  FORM label into whatever routes on it.

A character cap alone was tried first and was not enough: that sentence
is 57 characters, comfortably inside a 60-character limit. Counting
words is what actually separates a field from a sentence."""
_CHECKBOX_LINE = re.compile(r"[\[(]\s*[xX✓ ]?\s*[\])]")
_TABLE_LINE = re.compile(r"^\s*\|.*\|\s*$|^\s*(?:\S+\s{2,}){2,}\S+\s*$")
_LOG_LINE = re.compile(
    r"^\s*(?:\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}|\[\d{2}:\d{2}:\d{2}\])"
    r"|\b(?:INFO|WARN|WARNING|ERROR|DEBUG|TRACE|FATAL)\b"
)
_CONFIG_LINE = re.compile(r"^\s*(?:[\w.-]+\s*[:=]\s*\S+|<[\w:-]+[^>]*>|[-#]\s*\w+:)\s*$")
_NUMBERED_CLAUSE = re.compile(r"^\s*\d+(?:\.\d+){0,3}[.)]\s+[A-Z]")


# ---- keyword evidence ---------------------------------------------------------


CATEGORY_TERMS: Mapping[DocumentCategory, tuple[str, ...]] = {
    DocumentCategory.RUNBOOK: (
        "runbook",
        "procedure",
        "step",
        "prerequisite",
        "rollback",
        "escalate",
        "on-call",
        "remediation",
        "restore",
        "failover",
        "troubleshooting",
    ),
    DocumentCategory.POLICY: (
        "policy",
        "shall",
        "must",
        "compliance",
        "governance",
        "mandatory",
        "prohibited",
        "enforcement",
        "scope",
        "exception",
        "adherence",
    ),
    DocumentCategory.REPORT: (
        "report",
        "summary",
        "findings",
        "analysis",
        "quarter",
        "metrics",
        "conclusion",
        "recommendation",
        "observed",
        "trend",
    ),
    DocumentCategory.SPECIFICATION: (
        "specification",
        "requirement",
        "interface",
        "schema",
        "endpoint",
        "parameter",
        "protocol",
        "constraint",
        "acceptance",
        "architecture",
    ),
    DocumentCategory.CORRESPONDENCE: (
        "dear",
        "regards",
        "sincerely",
        "attached",
        "enquiry",
        "reply",
        "correspondence",
        "subject",
        "acknowledge",
    ),
    DocumentCategory.FORM: (
        "form",
        "applicant",
        "signature",
        "date-signed",
        "checkbox",
        "tick",
        "complete",
        "submit",
        "declaration",
        "authorised",
    ),
    DocumentCategory.LOG: (
        "log",
        "timestamp",
        "severity",
        "trace",
        "exception",
        "stacktrace",
        "logged",
        "event",
        "level",
    ),
    DocumentCategory.CONFIGURATION: (
        "configuration",
        "config",
        "setting",
        "default",
        "environment",
        "variable",
        "yaml",
        "manifest",
        "deployment",
        "replicas",
    ),
    DocumentCategory.DIAGRAM: (
        "diagram",
        "figure",
        "topology",
        "flowchart",
        "architecture-diagram",
        "legend",
        "depicted",
    ),
    DocumentCategory.CERTIFICATE: (
        "certificate",
        "certify",
        "issued",
        "expiry",
        "valid-until",
        "serial",
        "authority",
        "thumbprint",
        "attest",
    ),
}
"""Per-category vocabulary.

Infrastructure-and-operations categories rather than invoice /
purchase-order / contract: the spec's DO NOT IMPLEMENT list rules out
business-specific document templates, and a fixed set of commercial
document types is exactly that. Organizations add their own through
:class:`ClassificationRule`."""


def _document_frequency() -> dict[str, int]:
    """How many categories each term appears in.

    A term claimed by one category is strong evidence; one claimed by
    five is nearly none. Computed from the table itself rather than
    hand-assigned, so adding a term to a second category automatically
    devalues it instead of quietly double-counting.
    """
    counts: dict[str, int] = {}
    for terms in CATEGORY_TERMS.values():
        for term in set(terms):
            counts[term] = counts.get(term, 0) + 1
    return counts


_TERM_FREQUENCY = _document_frequency()
_CATEGORY_COUNT = len(CATEGORY_TERMS)


def term_weight(term: str) -> float:
    """How much one term's presence is worth.

    Inverse category frequency, smoothed: a term claimed by one category
    is worth more than one claimed by several.

    **Today only "exception" is shared**, between LOG and POLICY, so the
    weights are near-uniform and this function is currently doing very
    little. It is here because the vocabulary grows, and the moment a
    second category claims "restore" or "summary" the weighting starts
    mattering -- discovering that by watching classification quality
    drift is much worse than paying for it now.
    """
    frequency = _TERM_FREQUENCY.get(term, 1)
    return math.log(1.0 + _CATEGORY_COUNT / frequency)


# ---- rules ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClassificationRule:
    """An organization's own classification rule.

    Supplied at call time, so a tenant adding a category is configuration
    rather than a release. Rules outrank every other method, because
    somebody wrote this one down on purpose.
    """

    name: str
    category: DocumentCategory
    pattern: str | None = None
    required_terms: tuple[str, ...] = ()
    forbidden_terms: tuple[str, ...] = ()
    custom_category: str = ""
    confidence: float = 0.95
    route_to: str = ""

    def compiled(self) -> re.Pattern[str] | None:
        """The compiled pattern, or ``None`` if the rule has none.

        Raises:
            ValueError: If the pattern does not compile. Refused at use
                rather than silently matching nothing -- a typo'd rule
                that quietly classifies nothing looks exactly like a
                category that never occurs.
        """
        if not self.pattern:
            return None
        try:
            return re.compile(self.pattern, re.IGNORECASE | re.MULTILINE)
        except re.error as exc:
            raise ValueError(
                f"Classification rule {self.name!r} has an invalid pattern: {exc}"
            ) from exc


@dataclass(frozen=True, slots=True)
class DocumentTemplate:
    """A known document layout to match against.

    Matching is on the *labels* a form carries, not on its values: two
    filled copies of one form share their field names and share nothing
    else.
    """

    name: str
    category: DocumentCategory
    field_labels: tuple[str, ...]
    custom_category: str = ""
    minimum_match: float = 0.6
    route_to: str = ""


@dataclass(frozen=True, slots=True)
class Classification:
    """One label, with what decided it."""

    category: DocumentCategory
    confidence: float
    method: ClassificationMethod
    custom_category: str = ""
    rationale: str = ""
    matched_terms: tuple[str, ...] = ()
    is_primary: bool = False
    route_to: str = ""

    @property
    def label(self) -> str:
        """The category as somebody reads it, custom name winning."""
        return self.custom_category or str(self.category)


@dataclass(slots=True)
class ClassificationResult:
    """Every label one document earned."""

    classifications: list[Classification] = field(default_factory=list)
    considered: int = 0

    @property
    def primary(self) -> Classification | None:
        """The single best label, or ``None`` if nothing cleared the floor.

        ``None`` rather than falling back to ``OTHER``: "we could not
        classify this" and "this is an other-category document" are
        different facts, and only the first one should route a document
        to a human.
        """
        return self.classifications[0] if self.classifications else None

    @property
    def labels(self) -> list[str]:
        return [item.label for item in self.classifications]

    @property
    def routes(self) -> list[str]:
        """Distinct destinations, in confidence order."""
        seen: dict[str, None] = {}
        for item in self.classifications:
            if item.route_to:
                seen.setdefault(item.route_to, None)
        return list(seen)


@dataclass(frozen=True, slots=True)
class ClassifierConfig:
    """How the classifier behaves for one call."""

    minimum_confidence: float = DEFAULT_MINIMUM_CONFIDENCE
    multi_label: bool = True
    max_labels: int = MAX_LABELS
    rules: tuple[ClassificationRule, ...] = ()
    templates: tuple[DocumentTemplate, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.minimum_confidence <= 1.0:
            raise ValueError(
                f"minimum_confidence must be within [0, 1], got {self.minimum_confidence!r}."
            )
        if self.max_labels < 1:
            raise ValueError(f"max_labels must be at least 1, got {self.max_labels!r}.")


def classify(
    text: str,
    *,
    config: ClassifierConfig | None = None,
    field_labels: Sequence[str] = (),
) -> ClassificationResult:
    """Classify one document.

    *field_labels* are the key-value labels form extraction found, used
    for template matching. Passed in rather than re-derived, because form
    extraction has already done that work and doing it twice risks the
    two disagreeing.
    """
    settings = config or ClassifierConfig()
    if not text.strip():
        return ClassificationResult()

    candidates: list[Classification] = []
    candidates.extend(_by_rules(text, settings.rules))
    candidates.extend(_by_template(field_labels, settings.templates))
    candidates.extend(_by_keywords(text))
    candidates.extend(_by_structure(text))

    merged = _merge(candidates)
    kept = [item for item in merged if item.confidence >= settings.minimum_confidence]
    kept = kept[: 1 if not settings.multi_label else settings.max_labels]
    if kept:
        kept[0] = _as_primary(kept[0])
    return ClassificationResult(classifications=kept, considered=len(candidates))


def _as_primary(item: Classification) -> Classification:
    return Classification(
        category=item.category,
        confidence=item.confidence,
        method=item.method,
        custom_category=item.custom_category,
        rationale=item.rationale,
        matched_terms=item.matched_terms,
        is_primary=True,
        route_to=item.route_to,
    )


def _by_rules(text: str, rules: Sequence[ClassificationRule]) -> list[Classification]:
    """Labels from the organization's own rules.

    A rule with required terms needs all of them; a rule with forbidden
    terms is disqualified by any. Both are checked before the pattern,
    which is the expensive part.
    """
    lowered = text.lower()
    found: list[Classification] = []
    for rule in rules:
        if any(term.lower() not in lowered for term in rule.required_terms):
            continue
        if any(term.lower() in lowered for term in rule.forbidden_terms):
            continue
        pattern = rule.compiled()
        matched: tuple[str, ...] = tuple(rule.required_terms)
        if pattern is not None:
            hit = pattern.search(text)
            if hit is None:
                continue
            matched = (*matched, hit.group(0)[:80])
        elif not rule.required_terms:
            # A rule with neither a pattern nor required terms matches
            # every document, which is a misconfiguration rather than a
            # classification. Skipped rather than applied to everything.
            continue
        found.append(
            Classification(
                category=rule.category,
                confidence=rule.confidence,
                method=ClassificationMethod.RULE,
                custom_category=rule.custom_category,
                rationale=f"Matched rule {rule.name!r}.",
                matched_terms=matched,
                route_to=rule.route_to,
            )
        )
    return found


def _by_template(
    field_labels: Sequence[str], templates: Sequence[DocumentTemplate]
) -> list[Classification]:
    """Labels from matching a known form's field labels."""
    if not field_labels or not templates:
        return []
    present = {label.strip().lower().rstrip(":") for label in field_labels if label.strip()}
    found: list[Classification] = []
    for template in templates:
        expected = {label.strip().lower().rstrip(":") for label in template.field_labels}
        if not expected:
            continue
        overlap = present & expected
        score = len(overlap) / len(expected)
        if score < template.minimum_match:
            continue
        found.append(
            Classification(
                category=template.category,
                confidence=min(0.6 + 0.35 * score, 0.97),
                method=ClassificationMethod.TEMPLATE,
                custom_category=template.custom_category,
                rationale=(
                    f"Matched template {template.name!r} on {len(overlap)} of "
                    f"{len(expected)} field labels."
                ),
                matched_terms=tuple(sorted(overlap)),
                route_to=template.route_to,
            )
        )
    return found


def _by_keywords(text: str) -> list[Classification]:
    """Labels from weighted term evidence.

    Scores are normalised against the best-scoring category rather than
    against a fixed maximum: what matters is which category the document
    looks most like, and an absolute score would make a long document
    confident about everything simply because it contains more words.
    """
    tokens = set(_TOKEN.findall(text.lower()))
    if not tokens:
        return []

    scored: dict[DocumentCategory, tuple[float, list[str]]] = {}
    for category, terms in CATEGORY_TERMS.items():
        hits = [term for term in terms if term in tokens]
        if not hits:
            continue
        scored[category] = (sum(term_weight(term) for term in hits), hits)

    if not scored:
        return []

    best = max(score for score, _ in scored.values())
    found: list[Classification] = []
    for category, (score, hits) in scored.items():
        relative = score / best if best else 0.0
        # Capped below a rule's confidence: keyword evidence is real and
        # is never as good as somebody having written the rule down.
        confidence = min(0.30 + 0.55 * relative, 0.88)
        found.append(
            Classification(
                category=category,
                confidence=round(confidence, 4),
                method=ClassificationMethod.KEYWORD,
                rationale=f"Matched {len(hits)} distinctive term(s).",
                matched_terms=tuple(sorted(hits)),
            )
        )
    return found


def _by_structure(text: str) -> list[Classification]:
    """Labels from how the document is shaped rather than what it says.

    A form is recognisable with none of its vocabulary present: it is
    mostly ``label: value`` lines and checkboxes. A log is timestamps.
    Structure is what catches a document written in a language the term
    table does not cover.
    """
    lines = [line for line in _LINE.findall(text) if line.strip()]
    if not lines:
        return []
    total = len(lines)

    # A log line's timestamp and a config line's assignment both read as
    # key-value shapes, so those categories are tested first and a
    # document that looks like either is not also offered as a form.
    log_ratio = _ratio(lines, _LOG_LINE)
    config_ratio = _ratio(lines, _CONFIG_LINE)
    form_ratio = _ratio(lines, _KEY_VALUE_LINE) + _ratio(lines, _CHECKBOX_LINE) / 2
    if log_ratio >= _STRUCTURE_FLOOR or config_ratio >= _STRUCTURE_FLOOR:
        form_ratio = 0.0

    ratios = {
        DocumentCategory.FORM: form_ratio,
        DocumentCategory.LOG: log_ratio,
        DocumentCategory.CONFIGURATION: config_ratio,
        DocumentCategory.POLICY: _ratio(lines, _NUMBERED_CLAUSE),
        DocumentCategory.REPORT: _ratio(lines, _TABLE_LINE),
    }

    found: list[Classification] = []
    for category, ratio in ratios.items():
        if ratio < _STRUCTURE_FLOOR:
            continue
        found.append(
            Classification(
                category=category,
                confidence=round(min(0.35 + 0.5 * ratio, 0.85), 4),
                method=ClassificationMethod.STRUCTURE,
                rationale=f"{ratio:.0%} of {total} lines have this shape.",
            )
        )
    return found


_STRUCTURE_FLOOR = 0.30
"""Below this, a shape is incidental. Every document has a few lines with
a colon in them."""


def _ratio(lines: Sequence[str], pattern: re.Pattern[str]) -> float:
    """What fraction of lines match."""
    if not lines:
        return 0.0
    return sum(1 for line in lines if pattern.search(line)) / len(lines)


def _merge(candidates: Iterable[Classification]) -> list[Classification]:
    """One label per category, best evidence winning, most confident first.

    Two methods agreeing raises confidence, because independent evidence
    is what agreement means -- but never past the better method's own
    ceiling, so keyword agreement cannot promote a guess to a certainty.
    """
    best: dict[tuple[DocumentCategory, str], Classification] = {}
    for candidate in candidates:
        key = (candidate.category, candidate.custom_category)
        existing = best.get(key)
        if existing is None:
            best[key] = candidate
            continue
        winner, other = (
            (existing, candidate)
            if _method_rank(existing.method) >= _method_rank(candidate.method)
            else (candidate, existing)
        )
        best[key] = Classification(
            category=winner.category,
            confidence=round(min(winner.confidence + 0.05, _method_ceiling(winner.method)), 4),
            method=winner.method,
            custom_category=winner.custom_category,
            rationale=f"{winner.rationale} Also: {other.rationale}",
            matched_terms=tuple(sorted({*winner.matched_terms, *other.matched_terms})),
            route_to=winner.route_to or other.route_to,
        )
    return sorted(best.values(), key=lambda item: (-item.confidence, str(item.category)))


_METHOD_RANK: Mapping[ClassificationMethod, int] = {
    ClassificationMethod.MANUAL: 5,
    ClassificationMethod.RULE: 4,
    ClassificationMethod.TEMPLATE: 3,
    ClassificationMethod.AI: 2,
    ClassificationMethod.STRUCTURE: 1,
    ClassificationMethod.KEYWORD: 0,
}
"""How much each method's verdict is worth against another's. A human's
label beats a rule; a rule beats a template; anything beats a term
count."""

_METHOD_CEILING: Mapping[ClassificationMethod, float] = {
    ClassificationMethod.MANUAL: 1.0,
    ClassificationMethod.RULE: 0.99,
    ClassificationMethod.TEMPLATE: 0.97,
    ClassificationMethod.AI: 0.92,
    ClassificationMethod.STRUCTURE: 0.88,
    ClassificationMethod.KEYWORD: 0.88,
}
"""The most any single method may claim. Corroboration raises confidence
and cannot lift a method past what its own evidence supports."""


def _method_rank(method: ClassificationMethod) -> int:
    return _METHOD_RANK.get(method, 0)


def _method_ceiling(method: ClassificationMethod) -> float:
    return _METHOD_CEILING.get(method, 0.88)


__all__ = [
    "CATEGORY_TERMS",
    "DEFAULT_MINIMUM_CONFIDENCE",
    "MAX_LABELS",
    "Classification",
    "ClassificationResult",
    "ClassificationRule",
    "ClassifierConfig",
    "DocumentTemplate",
    "classify",
    "term_weight",
]
