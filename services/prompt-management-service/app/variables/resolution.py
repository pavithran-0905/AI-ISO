"""Variable resolution and validation (docs/061 "VARIABLE MANAGEMENT").

Resolves every declared variable for one prompt version into the value
set a render will actually use, applying the precedence between the
eight :class:`~app.models.enums.VariableKind` sources, validating each
against its own declared rules, and reporting which values must be
masked out of anything persisted afterwards.

**Secret resolution is injected, not performed here.** A
``SECRET_REFERENCE`` variable's value comes from a caller-supplied
resolver so this module stays pure and synchronously testable, and so
the only code that ever touches a secret's plaintext is the client that
fetched it. This module never stores one and always reports its name as
masked.

**Computed variables are evaluated in a sandbox.** They are Jinja2
expressions authored by the same people who author templates, so the
same reasoning applies as in :mod:`app.templating.renderer`: an
unsandboxed expression over user-authored content is a code-execution
path. ``shared_core.workflow.expressions`` already provides a vetted
sandboxed evaluator, so it is reused directly rather than rebuilt.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from shared_core.workflow.expressions import evaluate_expression

from app.models.enums import VariableKind, VariableType

SecretResolver = Callable[[str], str]
"""Resolves one secret reference to its plaintext. Supplied by the
caller; see this module's own docstring for why."""

_PRECEDENCE: tuple[VariableKind, ...] = (
    VariableKind.RUNTIME,
    VariableKind.PROJECT,
    VariableKind.ORGANIZATION,
    VariableKind.ENVIRONMENT,
    VariableKind.DYNAMIC,
    VariableKind.STATIC,
)
"""Most specific first. A runtime value supplied with the render request
beats a project default, which beats an organization default, which
beats a deployment-wide environment value. ``SECRET_REFERENCE`` and
``COMPUTED`` are absent deliberately -- neither has a *supplied* value
to rank, since one is fetched and the other is derived."""


class VariableResolutionError(Exception):
    """A variable could not be resolved or failed its own validation."""


@dataclass(frozen=True, slots=True)
class VariableSpec:
    """One declared variable, flattened out of its ORM row.

    A plain dataclass rather than the model itself so this engine is
    pure: it can be exercised with no database at all, which is what
    makes the precedence and validation rules cheap to test exhaustively.
    """

    name: str
    kind: VariableKind = VariableKind.STATIC
    value_type: VariableType = VariableType.STRING
    default_value: str | None = None
    required: bool = True
    secret_reference: str | None = None
    computed_expression: str | None = None
    validation_rules: dict[str, Any] = field(default_factory=dict)
    is_masked: bool = False


@dataclass(slots=True)
class ResolutionResult:
    """The values a render will use, and which of them must be masked."""

    values: dict[str, Any] = field(default_factory=dict)
    masked_names: set[str] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Whether every variable resolved and validated cleanly."""
        return not self.errors


_TRUE_SPELLINGS = frozenset({"true", "1", "yes", "on"})
_FALSE_SPELLINGS = frozenset({"false", "0", "no", "off"})


def _coerce_boolean(value: Any) -> bool:
    """Parse a boolean from its textual spellings.

    Variables arrive from environment strings and JSON bodies alike,
    where ``"false"`` is a very common way to mean ``False`` -- and
    plain ``bool("false")`` is ``True``, which is exactly the silent
    misconfiguration this exists to prevent.

    Raises:
        ValueError: If *value* is not a recognised boolean spelling.
    """
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in _TRUE_SPELLINGS:
        return True
    if lowered in _FALSE_SPELLINGS:
        return False
    raise ValueError(f"{value!r} is not a recognised boolean")


def _coerce_container(value: Any, value_type: VariableType) -> Any:
    """Pass through an already-correct array or object.

    Raises:
        ValueError: If *value* is not the declared container type.
    """
    expected = list if value_type == VariableType.ARRAY else dict
    if isinstance(value, expected):
        return value
    raise ValueError(f"{value!r} is not a {value_type!s}")


_SCALAR_COERCERS: dict[VariableType, Any] = {
    VariableType.STRING: str,
    VariableType.INTEGER: int,
    VariableType.NUMBER: float,
    VariableType.BOOLEAN: _coerce_boolean,
}


def coerce(value: Any, value_type: VariableType) -> Any:
    """Coerce *value* to its declared type.

    Raises:
        VariableResolutionError: If *value* cannot be coerced.
    """
    if value is None:
        return None
    coercer = _SCALAR_COERCERS.get(value_type)
    try:
        if coercer is not None:
            return coercer(value)
        return _coerce_container(value, value_type)
    except (TypeError, ValueError) as exc:
        raise VariableResolutionError(
            f"Value {value!r} is not a valid {value_type!s}: {exc}"
        ) from exc


def validate(name: str, value: Any, rules: dict[str, Any]) -> list[str]:
    """Check *value* against its declared rules ("Validation Rules").

    Returns every violation rather than the first: a caller fixing a
    prompt's inputs wants the whole list, not one round trip per
    problem.
    """
    errors: list[str] = []

    minimum = rules.get("min")
    if minimum is not None and isinstance(value, int | float) and value < minimum:
        errors.append(f"{name}: {value} is below the minimum of {minimum}.")

    maximum = rules.get("max")
    if maximum is not None and isinstance(value, int | float) and value > maximum:
        errors.append(f"{name}: {value} is above the maximum of {maximum}.")

    min_length = rules.get("min_length")
    if min_length is not None and hasattr(value, "__len__") and len(value) < min_length:
        errors.append(f"{name}: length {len(value)} is below the minimum of {min_length}.")

    max_length = rules.get("max_length")
    if max_length is not None and hasattr(value, "__len__") and len(value) > max_length:
        errors.append(f"{name}: length {len(value)} is above the maximum of {max_length}.")

    allowed = rules.get("enum")
    if isinstance(allowed, list) and allowed and value not in allowed:
        errors.append(f"{name}: {value!r} is not one of {allowed!r}.")

    pattern = rules.get("pattern")
    if isinstance(pattern, str) and pattern:
        try:
            if not re.search(pattern, str(value)):
                errors.append(f"{name}: {value!r} does not match the required pattern.")
        except re.error as exc:
            # A malformed pattern is the *declaration's* fault, not the
            # value's -- report it as such rather than blaming the input.
            errors.append(f"{name}: its declared validation pattern is invalid ({exc}).")

    return errors


def resolve(
    specs: Sequence[VariableSpec],
    supplied: dict[str, Any],
    *,
    secret_resolver: SecretResolver | None = None,
) -> ResolutionResult:
    """Resolve every declared variable into the value set a render uses.

    Ordering is deliberate: plain variables resolve first, then secrets,
    then computed expressions last -- a computed variable's expression
    can reference any already-resolved value, which is the whole point
    of having them.

    Never raises for a bad value. Every problem accumulates into
    ``result.errors`` so a caller sees all of them at once; only a
    caller that *wants* an exception checks ``result.ok``.
    """
    result = ResolutionResult()
    computed: list[VariableSpec] = []

    for spec in specs:
        if spec.kind == VariableKind.COMPUTED:
            computed.append(spec)
            continue
        if spec.is_masked or spec.kind == VariableKind.SECRET_REFERENCE:
            result.masked_names.add(spec.name)

        if spec.kind == VariableKind.SECRET_REFERENCE:
            _resolve_secret(spec, result, secret_resolver)
            continue

        _resolve_plain(spec, supplied, result)

    for spec in computed:
        if spec.is_masked:
            result.masked_names.add(spec.name)
        _resolve_computed(spec, result)

    return result


def _resolve_secret(
    spec: VariableSpec, result: ResolutionResult, secret_resolver: SecretResolver | None
) -> None:
    """Resolve one ``SECRET_REFERENCE`` through the injected resolver."""
    if not spec.secret_reference:
        result.errors.append(
            f"{spec.name}: declared as a secret reference but carries no reference."
        )
        return
    if secret_resolver is None:
        result.errors.append(
            f"{spec.name}: a secret reference cannot be resolved without a secret resolver."
        )
        return
    try:
        result.values[spec.name] = secret_resolver(spec.secret_reference)
    except Exception as exc:
        result.errors.append(f"{spec.name}: its secret could not be resolved ({exc}).")


def _resolve_plain(spec: VariableSpec, supplied: dict[str, Any], result: ResolutionResult) -> None:
    """Resolve one ordinary variable from *supplied* or its own default."""
    raw = supplied.get(spec.name, spec.default_value)
    if raw is None:
        if spec.required:
            result.errors.append(f"{spec.name}: required but not supplied and has no default.")
        return

    try:
        value = coerce(raw, spec.value_type)
    except VariableResolutionError as exc:
        result.errors.append(str(exc))
        return

    result.errors.extend(validate(spec.name, value, spec.validation_rules))
    result.values[spec.name] = value


def _resolve_computed(spec: VariableSpec, result: ResolutionResult) -> None:
    """Evaluate one computed expression against already-resolved values."""
    if not spec.computed_expression:
        result.errors.append(f"{spec.name}: declared as computed but carries no expression.")
        return
    try:
        value = evaluate_expression(spec.computed_expression, dict(result.values))
    except Exception as exc:
        result.errors.append(f"{spec.name}: its computed expression failed ({exc}).")
        return

    result.errors.extend(validate(spec.name, value, spec.validation_rules))
    result.values[spec.name] = value


def precedence_rank(kind: VariableKind) -> int:
    """How specific *kind* is, lower being more specific.

    Kinds outside the supplied-value precedence list rank last, since
    they are not competing for the same slot.
    """
    try:
        return _PRECEDENCE.index(kind)
    except ValueError:
        return len(_PRECEDENCE)


def merge_by_precedence(candidates: dict[VariableKind, Any]) -> Any:
    """Pick the most specific supplied value for one variable.

    Returns ``None`` when nothing was supplied at any level.
    """
    if not candidates:
        return None
    best = min(candidates, key=precedence_rank)
    return candidates[best]


__all__ = [
    "ResolutionResult",
    "SecretResolver",
    "VariableResolutionError",
    "VariableSpec",
    "coerce",
    "merge_by_precedence",
    "precedence_rank",
    "resolve",
    "validate",
]
