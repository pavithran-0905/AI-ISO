"""Validation (docs/063 "VALIDATION").

Seven kinds of check over one extracted document, producing a report a
reviewer can act on rather than a single boolean.

**A rule that could not run is not a rule that passed.** The field it
checks may simply never have been extracted, and folding that into
``PASSED`` is precisely how an incomplete document reaches approval with
a clean report. Such rules record ``SKIPPED`` and are counted separately,
and a document with skipped rules is never called fully validated.

**Confidence is validated, not just carried.** An extraction can be
perfectly well-formed and still be a guess; the confidence-threshold
rules are what turn a low-confidence field into a review task instead of
a silent acceptance.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.models.enums import ValidationOutcome, ValidationRuleKind

DEFAULT_CONFIDENCE_THRESHOLD = 0.7
"""Below this a value is reported for review rather than accepted. Matches
``review_required_below_confidence`` in the service settings."""

DEFAULT_COMPLETENESS_TARGET = 0.8

_DUPLICATE_SHINGLE_SIZE = 3
"""Words per shingle for near-duplicate detection.

The size and the threshold have to be chosen together, because one
changed word invalidates *k* shingles on each side: for a document of
*S* shingles the similarity ceiling after a single edit is
``(S - k) / (S + k)``. At five words that is 0.68 for a thirty-word
document -- so a re-scan of the same page differing by one OCR error
would score below any sensible threshold and never be flagged, which is
the one case near-duplicate detection exists for. Three words puts the
same re-scan around 0.81."""


@dataclass(slots=True)
class Finding:
    """What one rule concluded about one document."""

    rule: str
    kind: ValidationRuleKind
    outcome: ValidationOutcome
    message: str
    field_name: str | None = None
    observed: str | None = None
    expected: str | None = None
    confidence: float | None = None

    @property
    def is_blocking(self) -> bool:
        return self.outcome is ValidationOutcome.FAILED


@dataclass(slots=True)
class ValidationReport:
    """Every finding about one document, and what they add up to."""

    findings: list[Finding] = field(default_factory=list)
    completeness: float = 0.0
    document_key: str | None = None

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def of_outcome(self, outcome: ValidationOutcome) -> list[Finding]:
        return [item for item in self.findings if item.outcome is outcome]

    @property
    def failures(self) -> list[Finding]:
        return self.of_outcome(ValidationOutcome.FAILED)

    @property
    def warnings(self) -> list[Finding]:
        return self.of_outcome(ValidationOutcome.WARNING)

    @property
    def skipped(self) -> list[Finding]:
        return self.of_outcome(ValidationOutcome.SKIPPED)

    @property
    def is_valid(self) -> bool:
        """Whether nothing failed. Warnings and skips do not block."""
        return not self.failures

    @property
    def is_complete(self) -> bool:
        """Whether every rule actually ran.

        Separate from :attr:`is_valid` on purpose: a document can have no
        failures precisely because half its rules never executed, and a
        caller auto-approving on ``is_valid`` alone would approve it.
        """
        return not self.skipped

    @property
    def requires_review(self) -> bool:
        return bool(self.failures or self.warnings or self.skipped)

    def summary(self) -> dict[str, int]:
        return {str(outcome): len(self.of_outcome(outcome)) for outcome in ValidationOutcome}


ValueSource = Mapping[str, object]
"""The extracted document as ``field -> value``."""

Checker = Callable[[object], bool]


@dataclass(frozen=True, slots=True)
class Rule:
    """One declarative check.

    Raises:
        ValueError: On construction of a rule that checks nothing -- a
            rule with no pattern, no predicate and no bounds silently
            passes every document, which is worse than having no rule at
            all because it looks like coverage.
    """

    name: str
    kind: ValidationRuleKind
    field_name: str | None = None
    required: bool = False
    pattern: str | None = None
    allowed: tuple[str, ...] = ()
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    predicate: Checker | None = None
    message: str | None = None
    severity: ValidationOutcome = ValidationOutcome.FAILED
    """What a violation counts as. A business rule that flags an unusual
    but legal value belongs at ``WARNING``, not ``FAILED``."""

    def __post_init__(self) -> None:
        if not any(
            (
                self.required,
                self.pattern,
                self.allowed,
                self.minimum is not None,
                self.maximum is not None,
                self.predicate,
            )
        ):
            raise ValueError(
                f"Rule {self.name!r} checks nothing: it has no pattern, allowed "
                "values, bounds, predicate, and is not marked required."
            )

    def check(self, values: ValueSource) -> Finding:
        """Apply this rule to *values*."""
        if self.field_name is None:
            return self._predicate_only(values)

        present = self.field_name in values
        raw = values.get(self.field_name)
        blank = raw is None or (isinstance(raw, str) and not raw.strip())

        if not present or blank:
            return self._absent(present=present)

        return self._present(raw)

    def _absent(self, *, present: bool) -> Finding:
        """The finding for a field that is missing or blank."""
        if self.required:
            return Finding(
                rule=self.name,
                kind=self.kind,
                outcome=ValidationOutcome.FAILED,
                message=self.message
                or (
                    f"{self.field_name!r} is required but was "
                    f"{'blank' if present else 'not extracted'}."
                ),
                field_name=self.field_name,
                observed="" if present else None,
            )
        return Finding(
            rule=self.name,
            kind=self.kind,
            outcome=ValidationOutcome.SKIPPED,
            message=f"{self.field_name!r} was not extracted, so {self.name!r} did not run.",
            field_name=self.field_name,
        )

    def _present(self, raw: object) -> Finding:
        """The finding for a field that holds a value."""
        text = str(raw).strip()
        problem = self._first_problem(raw, text)
        if problem is None:
            return Finding(
                rule=self.name,
                kind=self.kind,
                outcome=ValidationOutcome.PASSED,
                message=f"{self.field_name!r} satisfies {self.name!r}.",
                field_name=self.field_name,
                observed=text,
            )
        return Finding(
            rule=self.name,
            kind=self.kind,
            outcome=self.severity,
            message=self.message or problem[0],
            field_name=self.field_name,
            observed=text,
            expected=problem[1],
        )

    def _first_problem(self, raw: object, text: str) -> tuple[str, str] | None:
        """The first way *text* violates this rule, as (message, expected)."""
        if self.pattern and not re.fullmatch(self.pattern, text):
            return (
                f"{self.field_name!r} is {text!r}, which does not match {self.pattern!r}.",
                self.pattern,
            )
        if self.allowed and text.lower() not in {option.lower() for option in self.allowed}:
            return (
                f"{self.field_name!r} is {text!r}, which is not one of {list(self.allowed)}.",
                ", ".join(self.allowed),
            )
        bounds = self._bounds_problem(text)
        if bounds is not None:
            return bounds
        if self.predicate is not None and not self.predicate(raw):
            return (f"{self.field_name!r} is {text!r}, which fails {self.name!r}.", self.name)
        return None

    def _bounds_problem(self, text: str) -> tuple[str, str] | None:
        """How *text* violates the numeric bounds, if it does.

        A non-numeric value where bounds are declared is itself the
        violation: silently skipping the comparison would let ``"many"``
        pass a rule that says the count must be under ten.
        """
        if self.minimum is None and self.maximum is None:
            return None
        try:
            number = Decimal(text.replace(",", ""))
        except (InvalidOperation, ArithmeticError, ValueError):
            return (
                f"{self.field_name!r} is {text!r}, which is not a number and so "
                "cannot be range-checked.",
                "a number",
            )
        if self.minimum is not None and number < self.minimum:
            return (
                f"{self.field_name!r} is {text!r}, below the minimum {self.minimum}.",
                f">= {self.minimum}",
            )
        if self.maximum is not None and number > self.maximum:
            return (
                f"{self.field_name!r} is {text!r}, above the maximum {self.maximum}.",
                f"<= {self.maximum}",
            )
        return None

    def _predicate_only(self, values: ValueSource) -> Finding:
        """A whole-document rule, which needs no named field.

        What cross-field consistency looks like: "the end date is after
        the start date" belongs to neither field.
        """
        if self.predicate is None:
            return Finding(
                rule=self.name,
                kind=self.kind,
                outcome=ValidationOutcome.SKIPPED,
                message=f"{self.name!r} names no field and carries no predicate.",
            )
        try:
            satisfied = self.predicate(values)
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            # A predicate that blows up on the document's shape has not
            # judged it. Recording that as a pass hides the rule failing.
            return Finding(
                rule=self.name,
                kind=self.kind,
                outcome=ValidationOutcome.SKIPPED,
                message=f"{self.name!r} could not run on this document: {error}.",
            )
        return Finding(
            rule=self.name,
            kind=self.kind,
            outcome=ValidationOutcome.PASSED if satisfied else self.severity,
            message=self.message
            or (f"{self.name!r} holds." if satisfied else f"{self.name!r} does not hold."),
        )


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    """How validation behaves."""

    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    completeness_target: float = DEFAULT_COMPLETENESS_TARGET
    duplicate_similarity: float = 0.75
    """Chosen against ``_DUPLICATE_SHINGLE_SIZE``: high enough that two
    different forms sharing a template do not collide, low enough that a
    re-scan differing by an OCR error still trips it."""
    expected_fields: tuple[str, ...] = ()
    """The fields this kind of document ought to have. Completeness is
    measured against these rather than against whatever was extracted --
    a document missing half its fields would otherwise score 100%."""


def validate(
    values: ValueSource,
    rules: Sequence[Rule],
    *,
    config: ValidationConfig | None = None,
    confidences: Mapping[str, float] | None = None,
    known_documents: Mapping[str, str] | None = None,
    text: str | None = None,
) -> ValidationReport:
    """Run every check over one extracted document."""
    settings = config or ValidationConfig()
    report = ValidationReport()

    for rule in rules:
        report.add(rule.check(values))

    report.completeness = completeness(values, settings.expected_fields)
    if settings.expected_fields:
        report.add(_completeness_finding(report.completeness, settings))

    if confidences:
        for finding in _confidence_findings(confidences, settings):
            report.add(finding)

    if text is not None and known_documents:
        duplicate = find_duplicate(text, known_documents, settings.duplicate_similarity)
        report.add(_duplicate_finding(duplicate, settings))

    return report


def completeness(values: ValueSource, expected: Sequence[str]) -> float:
    """The fraction of *expected* fields that hold a value.

    Zero for an empty expectation rather than one: claiming a document is
    100% complete because nothing was expected of it is a number that
    reads as reassurance and carries none.
    """
    if not expected:
        return 0.0
    populated = sum(
        1
        for name in expected
        if name in values and values[name] is not None and str(values[name]).strip() != ""
    )
    return round(populated / len(expected), 4)


def _completeness_finding(score: float, config: ValidationConfig) -> Finding:
    passed = score >= config.completeness_target
    return Finding(
        rule="completeness",
        kind=ValidationRuleKind.COMPLETENESS,
        outcome=ValidationOutcome.PASSED if passed else ValidationOutcome.WARNING,
        message=(
            f"{score:.0%} of the expected fields were extracted "
            f"(target {config.completeness_target:.0%})."
        ),
        observed=f"{score}",
        expected=f">= {config.completeness_target}",
    )


def _confidence_findings(
    confidences: Mapping[str, float], config: ValidationConfig
) -> list[Finding]:
    """One finding per field whose extraction confidence is too low."""
    findings: list[Finding] = []
    for name, score in sorted(confidences.items()):
        if score >= config.confidence_threshold:
            continue
        findings.append(
            Finding(
                rule="confidence-threshold",
                kind=ValidationRuleKind.CONFIDENCE_THRESHOLD,
                outcome=ValidationOutcome.WARNING,
                message=(
                    f"{name!r} was extracted at {score:.2f} confidence, below the "
                    f"{config.confidence_threshold:.2f} threshold; it needs review."
                ),
                field_name=name,
                observed=f"{score}",
                expected=f">= {config.confidence_threshold}",
                confidence=score,
            )
        )
    return findings


# ---- duplicates -------------------------------------------------------------------


def shingles(text: str, size: int = _DUPLICATE_SHINGLE_SIZE) -> frozenset[str]:
    """Overlapping word n-grams of *text*, lowercased.

    Whole documents are compared through these rather than through their
    exact text, because a re-scan of the same page differs from the first
    by a handful of OCR errors and would otherwise look like a new
    document.
    """
    words = re.findall(r"[\w']+", text.lower())
    if len(words) < size:
        return frozenset([" ".join(words)]) if words else frozenset()
    return frozenset(
        " ".join(words[index : index + size]) for index in range(len(words) - size + 1)
    )


def similarity(left: str, right: str) -> float:
    """Jaccard similarity of two documents, on shingles."""
    first = shingles(left)
    second = shingles(right)
    if not first or not second:
        return 0.0
    return round(len(first & second) / len(first | second), 4)


def find_duplicate(
    text: str, known: Mapping[str, str], threshold: float
) -> tuple[str, float] | None:
    """The most similar known document above *threshold*, or ``None``."""
    best: tuple[str, float] | None = None
    for key, other in known.items():
        score = similarity(text, other)
        if score >= threshold and (best is None or score > best[1]):
            best = (key, score)
    return best


def _duplicate_finding(duplicate: tuple[str, float] | None, config: ValidationConfig) -> Finding:
    if duplicate is None:
        return Finding(
            rule="duplicate-detection",
            kind=ValidationRuleKind.DUPLICATE,
            outcome=ValidationOutcome.PASSED,
            message="No sufficiently similar document was found.",
            expected=f"< {config.duplicate_similarity}",
        )
    key, score = duplicate
    return Finding(
        rule="duplicate-detection",
        kind=ValidationRuleKind.DUPLICATE,
        # A warning rather than a failure: a genuine reissue of a form is
        # a legitimate document, and only a human knows which this is.
        outcome=ValidationOutcome.WARNING,
        message=f"This document is {score:.0%} similar to {key!r} and may be a duplicate.",
        observed=f"{score}",
        expected=f"< {config.duplicate_similarity}",
    )


# ---- rule builders ------------------------------------------------------------------


def required(name: str, *, kind: ValidationRuleKind = ValidationRuleKind.REQUIRED_FIELD) -> Rule:
    """A field that must be present and non-blank."""
    return Rule(name=f"{name}-required", kind=kind, field_name=name, required=True)


def matches(name: str, pattern: str, *, required_field: bool = False) -> Rule:
    """A field that must match *pattern* when present."""
    return Rule(
        name=f"{name}-format",
        kind=ValidationRuleKind.SCHEMA,
        field_name=name,
        pattern=pattern,
        required=required_field,
    )


def one_of(name: str, options: Sequence[str], *, required_field: bool = False) -> Rule:
    """A field restricted to a closed set of values."""
    return Rule(
        name=f"{name}-allowed",
        kind=ValidationRuleKind.SCHEMA,
        field_name=name,
        allowed=tuple(options),
        required=required_field,
    )


def between(
    name: str,
    *,
    low: Decimal | int | None = None,
    high: Decimal | int | None = None,
    required_field: bool = False,
) -> Rule:
    """A numeric field bounded above, below, or both."""
    return Rule(
        name=f"{name}-range",
        kind=ValidationRuleKind.SCHEMA,
        field_name=name,
        minimum=Decimal(low) if low is not None else None,
        maximum=Decimal(high) if high is not None else None,
        required=required_field,
    )


def business_rule(
    name: str,
    predicate: Checker,
    *,
    message: str | None = None,
    severity: ValidationOutcome = ValidationOutcome.FAILED,
) -> Rule:
    """A whole-document rule expressed as a predicate over its values."""
    return Rule(
        name=name,
        kind=ValidationRuleKind.BUSINESS_RULE,
        predicate=predicate,
        message=message,
        severity=severity,
    )


def consistency_rule(
    name: str,
    predicate: Checker,
    *,
    message: str | None = None,
    severity: ValidationOutcome = ValidationOutcome.FAILED,
) -> Rule:
    """A cross-field rule: two extracted values that must agree."""
    return Rule(
        name=name,
        kind=ValidationRuleKind.CONSISTENCY,
        predicate=predicate,
        message=message,
        severity=severity,
    )


def dates_in_order(earlier: str, later: str) -> Rule:
    """*earlier* must not fall after *later*.

    Skips rather than fails when either date is missing or unparseable,
    because "these two dates are out of order" is a claim that needs two
    dates to make.
    """

    def ordered(values: object) -> bool:
        mapping = values if isinstance(values, Mapping) else {}
        first = parse_date(mapping.get(earlier))
        second = parse_date(mapping.get(later))
        if first is None or second is None:
            raise ValueError(f"{earlier!r} or {later!r} is missing or is not a date")
        return first <= second

    return Rule(
        name=f"{earlier}-before-{later}",
        kind=ValidationRuleKind.CONSISTENCY,
        predicate=ordered,
        message=f"{earlier!r} must not fall after {later!r}.",
    )


_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d %B %Y", "%B %d, %Y")


def parse_date(value: object) -> date | None:
    """*value* as a date, or ``None`` if it is not one."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            # No timezone: a date on a form is a calendar date, and
            # attaching a zone to it would move it by a day for half the
            # world.
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def validate_many(
    documents: Iterable[tuple[str, ValueSource]],
    rules: Sequence[Rule],
    *,
    config: ValidationConfig | None = None,
) -> dict[str, ValidationReport]:
    """Validate a batch, keyed by document key."""
    return {key: validate(values, rules, config=config) for key, values in documents}


__all__ = [
    "DEFAULT_COMPLETENESS_TARGET",
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "Checker",
    "Finding",
    "Rule",
    "ValidationConfig",
    "ValidationReport",
    "ValueSource",
    "between",
    "business_rule",
    "completeness",
    "consistency_rule",
    "dates_in_order",
    "find_duplicate",
    "matches",
    "one_of",
    "parse_date",
    "required",
    "shingles",
    "similarity",
    "validate",
    "validate_many",
]
