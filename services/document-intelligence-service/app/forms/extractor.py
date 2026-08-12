"""Form and key-value extraction (docs/063 "FORM EXTRACTION").

A form is a document whose meaning is in its labelled fields rather than
its prose, and reading one means answering three questions per field:
what is it called, what kind of thing is it, and what does it say.

**A blank field is a finding, not a gap.** "Signature: ______" and a
document with no signature line at all are different states, and
collapsing them loses exactly the fact a reviewer of a change request or
a consent form is looking for. Blank fields are extracted with an empty
value and ``is_blank`` set, never dropped.

**A checkbox reports what it is, not what it means.** Whether an unticked
"Approved" box means rejected or means not-yet-reviewed depends on the
form, so this module reports ``checked=False`` and leaves the reading to
validation rules that know the form.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from app.models.enums import ExtractionMethod, FormFieldKind

MAX_LABEL_LENGTH = 60
"""Beyond this a "label" is a sentence that happens to contain a colon."""

MAX_VALUE_WORDS = 12
"""A field value is a value. Longer than this it is prose, and treating
prose as a field value silently turns a paragraph into a data point."""

MIN_BLANK_RUN = 3
"""Underscores or dots in a row that mean "write here" rather than
punctuation."""

_CHECKED_MARKS = frozenset("xX✓✔☑■●•✅")
_UNCHECKED_MARKS = frozenset(" ☐□○◌-")

_BOX = re.compile(r"[\[\(\{](?P<mark>.?)[\]\)\}]")
_BOX_GLYPH = re.compile(r"(?P<mark>[☐☑☒✅✓✔■□○●])")
_BLANK_RUN = re.compile(r"(?:_{3,}|\.{3,}|…+|-{5,})")

_LABEL = rf"[A-Za-z][A-Za-z0-9 \t/()&'#-]{{0,{MAX_LABEL_LENGTH - 1}}}"
_KEY_VALUE = re.compile(
    rf"^[ \t]*(?![0-9]{{2,}})(?P<label>{_LABEL}?)(?<![0-9])[ \t]*[:=][ \t]*"
    rf"(?P<value>.*?)[ \t]*$"
)
"""``label: value``, with a label that does not end in a digit.

The trailing-digit guard is what stops a clock reading. "The incident
began at 09:14" splits at that colon into a label ending "09" and a
value beginning "14", and without the guard every timestamp in a log
becomes a form field.
"""
_SIGNATURE_LABEL = re.compile(
    r"\b(signature|signed(?:\s+by)?|authoris(?:ed|ation)|authoriz(?:ed|ation)|"
    r"approved\s+by|witness|initials?)\b",
    re.IGNORECASE,
)
_DATE_LABEL = re.compile(
    r"\b(date|dated|on|effective|expiry|expires|due|deadline)\b", re.IGNORECASE
)
_NUMBER_LABEL = re.compile(
    r"\b(number|no\.?|qty|quantity|amount|total|count|id|reference|ref)\b", re.IGNORECASE
)
_DATE_VALUE = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})$"
)
_NUMBER_VALUE = re.compile(r"^[\s$£€¥]*-?[\d,]+(?:\.\d+)?\s*%?$")
_SELECTION_VALUE = re.compile(
    r"^(yes|no|y|n|true|false|n/?a|none|approved|rejected|pending)$", re.IGNORECASE
)

_HANDWRITING_HINT = re.compile(
    r"\b(handwritten|hand-written|in\s+(?:your|block)\s+(?:own\s+)?(?:hand|capitals))\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class FormField:
    """One labelled field on a form."""

    label: str
    value: str = ""
    kind: FormFieldKind = FormFieldKind.TEXT
    confidence: float = 0.0
    method: ExtractionMethod = ExtractionMethod.PATTERN
    checked: bool | None = None
    """Tri-state on purpose: ``None`` means "not a box", which is not the
    same claim as an unticked one."""
    page_number: int | None = None
    line_number: int | None = None
    is_blank: bool = False
    is_required: bool = False
    normalized_label: str = ""
    options: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(slots=True)
class FormExtractionResult:
    """Every field found on one document, with the summary a reviewer reads."""

    fields: list[FormField] = field(default_factory=list)
    template_name: str | None = None
    template_confidence: float = 0.0
    method: ExtractionMethod = ExtractionMethod.PATTERN
    unmatched_required: list[str] = field(default_factory=list)

    @property
    def field_count(self) -> int:
        return len(self.fields)

    @property
    def blank_count(self) -> int:
        return sum(1 for item in self.fields if item.is_blank)

    @property
    def confidence(self) -> float:
        """The mean field confidence, floored by anything missing.

        A form whose every found field is certain but which is missing a
        required one is not a certain reading of that form, and averaging
        only what was found would report it as one.
        """
        if not self.fields:
            return 0.0
        mean = sum(item.confidence for item in self.fields) / len(self.fields)
        if self.unmatched_required:
            penalty = len(self.unmatched_required) / (
                len(self.fields) + len(self.unmatched_required)
            )
            mean *= 1.0 - penalty
        return round(mean, 4)

    @property
    def is_complete(self) -> bool:
        return not self.unmatched_required and not any(
            item.is_blank and item.is_required for item in self.fields
        )

    def get(self, label: str) -> FormField | None:
        """The field with *label*, matched loosely, or ``None``."""
        wanted = normalize_label(label)
        return next((item for item in self.fields if item.normalized_label == wanted), None)

    def as_mapping(self) -> dict[str, str]:
        """Fields as a plain label-to-value dictionary."""
        return {item.label: item.value for item in self.fields}

    def errors(self) -> list[str]:
        """Every validation error across every field, labelled."""
        collected = [f"{item.label}: {message}" for item in self.fields for message in item.errors]
        collected.extend(f"{label}: required field is missing" for label in self.unmatched_required)
        return collected


@dataclass(frozen=True, slots=True)
class FieldRule:
    """What one field on a known form must look like."""

    label: str
    kind: FormFieldKind = FormFieldKind.TEXT
    required: bool = False
    pattern: str | None = None
    allowed: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()

    def matches_label(self, normalized: str) -> bool:
        return normalized == normalize_label(self.label) or normalized in {
            normalize_label(alias) for alias in self.aliases
        }

    def validate(self, value: str, *, blank: bool) -> list[str]:
        """Every way *value* fails this rule."""
        problems: list[str] = []
        if blank or not value:
            if self.required:
                problems.append("required field is blank")
            return problems
        if self.pattern and not re.fullmatch(self.pattern, value):
            problems.append(f"value {value!r} does not match {self.pattern!r}")
        if self.allowed and value.strip().lower() not in {
            option.lower() for option in self.allowed
        }:
            problems.append(f"value {value!r} is not one of {list(self.allowed)}")
        return problems


@dataclass(frozen=True, slots=True)
class FormTemplate:
    """A known form, so its fields can be validated rather than guessed."""

    name: str
    rules: tuple[FieldRule, ...]
    identifiers: tuple[str, ...] = ()
    """Phrases that identify this form in the document text."""

    @property
    def required_labels(self) -> list[str]:
        return [rule.label for rule in self.rules if rule.required]


@dataclass(frozen=True, slots=True)
class FormConfig:
    """How form extraction behaves."""

    minimum_confidence: float = 0.4
    detect_checkboxes: bool = True
    detect_signatures: bool = True
    keep_blank_fields: bool = True
    max_value_words: int = MAX_VALUE_WORDS


def normalize_label(label: str) -> str:
    """A label reduced to what makes two spellings of it the same one.

    Accents are folded, punctuation dropped, case and spacing flattened,
    so "Requester's E-Mail" and "requester s email" collide -- which is
    what makes template matching work across documents that were typed
    by different people.
    """
    folded = unicodedata.normalize("NFKD", label)
    stripped = "".join(char for char in folded if not unicodedata.combining(char))
    cleaned = re.sub(r"[^a-z0-9]+", " ", stripped.lower())
    return cleaned.strip()


def extract_fields(
    text: str,
    *,
    config: FormConfig | None = None,
    templates: Sequence[FormTemplate] = (),
    page_number: int | None = None,
) -> FormExtractionResult:
    """Every field on *text*, validated against a matching template.

    Checkbox lines are read before key-value lines because "[x] Approved:
    yes" is a box whose label happens to contain a colon, and reading it
    as a key-value pair would throw the tick away.

    A field's value is what is on its own line. A "Notes:" block wrapping
    onto following lines yields only the first, because the alternative
    -- swallowing lines until the next label -- absorbs the whole rest of
    a document whenever the last field is a free-text one. Callers that
    need the block want the layout analyser's regions instead.
    """
    settings = config or FormConfig()
    result = FormExtractionResult()
    if not text.strip():
        return result

    for index, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        found = _read_line(line, settings)
        if found is None:
            continue
        found.line_number = index
        found.page_number = page_number
        result.fields.append(found)

    if not settings.keep_blank_fields:
        result.fields = [item for item in result.fields if not item.is_blank]
    result.fields = [
        item for item in result.fields if item.confidence >= settings.minimum_confidence
    ]

    template = _match_template(text, result.fields, templates)
    if template is not None:
        _apply_template(result, template)
    return result


def _read_line(line: str, config: FormConfig) -> FormField | None:
    """The one field on *line*, or ``None`` if it holds none."""
    if config.detect_checkboxes:
        box = _read_checkbox(line)
        if box is not None:
            return box
    return _read_key_value(line, config)


def _read_checkbox(line: str) -> FormField | None:
    """A ticked or unticked box, or ``None``.

    Bracket boxes are tried before glyph boxes because "[x]" contains no
    glyph and a glyph box contains no brackets, and because a line of
    prose is far likelier to contain a lone bullet than a bracketed
    single character.
    """
    match = _BOX.search(line)
    if match is not None:
        mark = match.group("mark")
        label = line[: match.start()] + line[match.end() :]
        checked = _is_checked(mark)
        if checked is None:
            return None
        return _checkbox_field(label, checked, confidence=0.92)

    glyph = _BOX_GLYPH.search(line)
    if glyph is not None:
        checked = _is_checked(glyph.group("mark"))
        if checked is None:  # pragma: no cover -- the class only holds known marks
            return None
        label = line[: glyph.start()] + line[glyph.end() :]
        return _checkbox_field(label, checked, confidence=0.88)
    return None


def _is_checked(mark: str) -> bool | None:
    """Whether *mark* is a tick, a blank box, or not a box mark at all."""
    if mark in _CHECKED_MARKS:
        return True
    if mark == "" or mark in _UNCHECKED_MARKS:
        return False
    return None


def _checkbox_field(label: str, checked: bool, *, confidence: float) -> FormField | None:
    """Build a checkbox field, or ``None`` if there is no label to attach."""
    text = _clean_label(label)
    if not text:
        return None
    return FormField(
        label=text,
        value="checked" if checked else "unchecked",
        kind=FormFieldKind.CHECKBOX,
        checked=checked,
        confidence=confidence,
        method=ExtractionMethod.PATTERN,
        normalized_label=normalize_label(text),
    )


def _read_key_value(line: str, config: FormConfig) -> FormField | None:
    """A ``label: value`` pair, or ``None``."""
    match = _KEY_VALUE.match(line)
    if match is None:
        return None
    label = _clean_label(match.group("label"))
    if not label:
        return None

    raw = match.group("value").strip()
    blank_run = bool(_BLANK_RUN.search(raw)) or (not raw)
    value = _BLANK_RUN.sub(" ", raw).strip()
    if value and len(value.split()) > config.max_value_words:
        return None

    kind = _classify_field(label, value, config)
    is_blank = not value
    return FormField(
        label=label,
        value=value,
        kind=kind,
        confidence=_confidence(kind, value, blank=is_blank, ruled=blank_run),
        method=ExtractionMethod.PATTERN,
        is_blank=is_blank,
        normalized_label=normalize_label(label),
    )


def _clean_label(text: str) -> str:
    """A label with leading bullets, numbering and stray punctuation gone."""
    # The en and em dashes are here because documents genuinely use them
    # as bullets; they are the character being stripped, not a typo for
    # a hyphen.
    stripped = re.sub(r"^[\s\-*•–—]*(?:\d+[.)]\s*)?", "", text).strip()  # noqa: RUF001
    stripped = _BLANK_RUN.sub(" ", stripped).strip(" \t:=.-")
    return stripped[:MAX_LABEL_LENGTH].strip()


def _classify_field(label: str, value: str, config: FormConfig) -> FormFieldKind:
    """What kind of field this is, from its label and its value.

    A present value settles it, because a field labelled "Reference"
    holding ``2024-03-01`` is a date whatever its label says -- and,
    equally, one labelled "Change ID" holding ``CHG-004821`` is text
    however strongly the word "ID" suggests a number. Label hints about
    the *type* of value therefore only run on a blank field, where there
    is no value to contradict them; that is the unfilled-form case they
    exist for.

    Signature and handwriting hints are different: they describe how the
    field is filled rather than what it holds, so they apply either way.
    """
    if config.detect_signatures and _SIGNATURE_LABEL.search(label):
        return FormFieldKind.SIGNATURE
    if _HANDWRITING_HINT.search(label):
        return FormFieldKind.HANDWRITTEN
    if value:
        return next(
            (kind for pattern, kind in _VALUE_KINDS if pattern.match(value)),
            FormFieldKind.TEXT,
        )
    return next(
        (kind for pattern, kind in _LABEL_KINDS if pattern.search(label)),
        FormFieldKind.TEXT,
    )


_VALUE_KINDS: tuple[tuple[re.Pattern[str], FormFieldKind], ...] = (
    (_DATE_VALUE, FormFieldKind.DATE),
    (_NUMBER_VALUE, FormFieldKind.NUMBER),
    (_SELECTION_VALUE, FormFieldKind.SELECTION),
)

_LABEL_KINDS: tuple[tuple[re.Pattern[str], FormFieldKind], ...] = (
    (_DATE_LABEL, FormFieldKind.DATE),
    (_NUMBER_LABEL, FormFieldKind.NUMBER),
)


_KIND_CONFIDENCE: Mapping[FormFieldKind, float] = {
    FormFieldKind.DATE: 0.9,
    FormFieldKind.NUMBER: 0.85,
    FormFieldKind.SELECTION: 0.88,
    FormFieldKind.SIGNATURE: 0.8,
    FormFieldKind.HANDWRITTEN: 0.7,
    FormFieldKind.CHECKBOX: 0.92,
    FormFieldKind.TEXT: 0.72,
}


def _confidence(kind: FormFieldKind, value: str, *, blank: bool, ruled: bool) -> float:
    """How sure the reading of one field is.

    A blank field is still confidently *found* when the document drew a
    rule for it -- "Signature: ______" is unambiguous evidence that the
    field exists -- so the blank penalty is small there and larger where
    the label simply trailed off into nothing.
    """
    score = _KIND_CONFIDENCE.get(kind, 0.7)
    if blank:
        score -= 0.05 if ruled else 0.2
    elif not value:  # pragma: no cover -- blank is defined as an empty value
        score -= 0.2
    return round(max(min(score, 0.99), 0.0), 4)


# ---- templates --------------------------------------------------------------------


_TEMPLATE_MATCH_FLOOR = 0.5
"""Half a template's fields must be present before the document is called
an instance of it. Below that the "match" is coincidence."""

_IDENTIFIER_BONUS = 0.25
"""What a form naming itself in its own text is worth. Enough to break a
tie, not enough to make a form with none of the right fields match."""


def _match_template(
    text: str, fields: Sequence[FormField], templates: Sequence[FormTemplate]
) -> FormTemplate | None:
    """The template this document is an instance of, or ``None``.

    Scored on how many of the template's fields are actually present, so
    two templates that share an identifier phrase are separated by their
    field sets rather than by declaration order.
    """
    if not templates:
        return None
    present = {item.normalized_label for item in fields}
    lowered = text.lower()
    best: tuple[float, FormTemplate] | None = None
    for template in templates:
        if not template.rules:
            continue
        matched = sum(
            1 for rule in template.rules if any(rule.matches_label(label) for label in present)
        )
        score = matched / len(template.rules)
        if template.identifiers and any(
            phrase.lower() in lowered for phrase in template.identifiers
        ):
            score += _IDENTIFIER_BONUS
        if score >= _TEMPLATE_MATCH_FLOOR and (best is None or score > best[0]):
            best = (score, template)
    return best[1] if best else None


def _apply_template(result: FormExtractionResult, template: FormTemplate) -> None:
    """Label the result with *template* and validate every field against it."""
    result.template_name = template.name
    result.method = ExtractionMethod.TEMPLATE
    matched_rules: set[str] = set()

    for item in result.fields:
        rule = next(
            (
                candidate
                for candidate in template.rules
                if candidate.matches_label(item.normalized_label)
            ),
            None,
        )
        if rule is None:
            continue
        matched_rules.add(rule.label)
        item.is_required = rule.required
        item.method = ExtractionMethod.TEMPLATE
        # The template names the field, so its declared kind beats a kind
        # guessed from a value the field may not even hold yet.
        if rule.kind is not FormFieldKind.TEXT:
            item.kind = rule.kind
        elif rule.allowed:
            # A closed list of permitted values is what a selection is,
            # whichever kind the rule bothered to declare.
            item.kind = FormFieldKind.SELECTION
        item.options = list(rule.allowed)
        item.errors = rule.validate(item.value, blank=item.is_blank)
        item.confidence = round(min(item.confidence + 0.08, 0.99), 4)

    result.unmatched_required = [
        rule.label for rule in template.rules if rule.required and rule.label not in matched_rules
    ]
    covered = len(matched_rules) / len(template.rules)
    result.template_confidence = round(covered, 4)


def extract_key_values(text: str, *, config: FormConfig | None = None) -> dict[str, str]:
    """Just the populated ``label: value`` pairs, as a dictionary.

    The convenience form for callers that want the data rather than the
    form. Blank fields are omitted here because a dictionary cannot carry
    the distinction between blank and absent -- callers that need it want
    :func:`extract_fields`.
    """
    result = extract_fields(text, config=config)
    return {item.label: item.value for item in result.fields if not item.is_blank}


def merge_pages(results: Iterable[FormExtractionResult]) -> FormExtractionResult:
    """One result for a form that spans several pages.

    A field repeated on a later page wins only if the earlier one was
    blank: continuation pages routinely reprint a header field, and a
    reprint that is blank must not erase the value from page one.
    """
    merged = FormExtractionResult()
    index: dict[str, FormField] = {}
    for result in results:
        merged.template_name = merged.template_name or result.template_name
        merged.template_confidence = max(merged.template_confidence, result.template_confidence)
        for item in result.fields:
            existing = index.get(item.normalized_label)
            if existing is None:
                index[item.normalized_label] = item
                merged.fields.append(item)
            elif existing.is_blank and not item.is_blank:
                merged.fields[merged.fields.index(existing)] = item
                index[item.normalized_label] = item
    merged.unmatched_required = [
        label
        for label in dict.fromkeys(name for result in results for name in result.unmatched_required)
        if normalize_label(label) not in index
    ]
    return merged


__all__ = [
    "MAX_LABEL_LENGTH",
    "MAX_VALUE_WORDS",
    "FieldRule",
    "FormConfig",
    "FormExtractionResult",
    "FormField",
    "FormTemplate",
    "extract_fields",
    "extract_key_values",
    "merge_pages",
    "normalize_label",
]
