"""Tests for :mod:`app.variables.resolution`.

Pure module -- the secret resolver is injected, which is exactly what
makes this testable without touching a vault.
"""

from __future__ import annotations

import pytest

from app.models.enums import VariableKind, VariableType
from app.security.redaction import REDACTION_PLACEHOLDER
from app.variables.resolution import (
    ResolutionResult,
    VariableResolutionError,
    VariableSpec,
    coerce,
    merge_by_precedence,
    precedence_rank,
    resolve,
    validate,
)

# ---------------------------------------------------------------------------
# coerce -- the boolean trap
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spelling", ["false", "FALSE", "False", "0", "no", "off", " off "])
def test_falsey_spellings_coerce_to_false(spelling: str) -> None:
    """``bool("false")`` is ``True`` in Python.

    Variables arrive from environment strings and JSON bodies where
    ``"false"`` is a very common way to mean False, so relying on
    ``bool()`` would invert the operator's intent silently.
    """
    assert coerce(spelling, VariableType.BOOLEAN) is False


@pytest.mark.parametrize("spelling", ["true", "TRUE", "1", "yes", "on"])
def test_truthy_spellings_coerce_to_true(spelling: str) -> None:
    assert coerce(spelling, VariableType.BOOLEAN) is True


def test_a_real_bool_passes_through() -> None:
    assert coerce(True, VariableType.BOOLEAN) is True
    assert coerce(False, VariableType.BOOLEAN) is False


def test_an_unrecognised_boolean_spelling_is_refused() -> None:
    with pytest.raises(VariableResolutionError, match="not a valid boolean"):
        coerce("maybe", VariableType.BOOLEAN)


@pytest.mark.parametrize(
    ("value", "value_type", "expected"),
    [
        (7, VariableType.STRING, "7"),
        ("7", VariableType.INTEGER, 7),
        ("1.5", VariableType.NUMBER, 1.5),
        (2, VariableType.NUMBER, 2.0),
        ([1, 2], VariableType.ARRAY, [1, 2]),
        ({"a": 1}, VariableType.OBJECT, {"a": 1}),
    ],
)
def test_coercion_by_type(value: object, value_type: VariableType, expected: object) -> None:
    assert coerce(value, value_type) == expected


@pytest.mark.parametrize(
    ("value", "value_type"),
    [
        ("abc", VariableType.INTEGER),
        ("abc", VariableType.NUMBER),
        ("not-a-list", VariableType.ARRAY),
        ([1], VariableType.OBJECT),
        ({"a": 1}, VariableType.ARRAY),
    ],
)
def test_uncoercible_values_are_refused(value: object, value_type: VariableType) -> None:
    with pytest.raises(VariableResolutionError):
        coerce(value, value_type)


def test_none_passes_through_uncoerced() -> None:
    """Absence is handled by the required/default logic, not here."""
    assert coerce(None, VariableType.INTEGER) is None


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_no_rules_means_no_errors() -> None:
    assert validate("x", "anything", {}) == []


@pytest.mark.parametrize(
    ("value", "rules", "fragment"),
    [
        (5, {"min": 10}, "below the minimum"),
        (50, {"max": 10}, "above the maximum"),
        ("ab", {"min_length": 5}, "length 2 is below"),
        ("abcdef", {"max_length": 3}, "length 6 is above"),
        ("wrong", {"enum": ["a", "b"]}, "is not one of"),
        ("abc", {"pattern": r"^\d+$"}, "does not match"),
    ],
)
def test_each_rule_reports_its_own_violation(
    value: object, rules: dict[str, object], fragment: str
) -> None:
    errors = validate("field", value, rules)
    assert len(errors) == 1
    assert fragment in errors[0]


@pytest.mark.parametrize(
    ("value", "rules"),
    [
        (10, {"min": 10}),
        (10, {"max": 10}),
        ("abcde", {"min_length": 5}),
        ("abc", {"max_length": 3}),
        ("a", {"enum": ["a", "b"]}),
        ("123", {"pattern": r"^\d+$"}),
    ],
)
def test_values_exactly_at_a_boundary_pass(value: object, rules: dict[str, object]) -> None:
    """Bounds are inclusive, not off-by-one exclusions."""
    assert validate("field", value, rules) == []


def test_every_violation_is_reported_not_just_the_first() -> None:
    """A caller fixing inputs wants the whole list, not one round trip
    per problem."""
    errors = validate("field", 999, {"max": 10, "enum": [1, 2]})
    assert len(errors) == 2


def test_an_empty_enum_list_imposes_no_constraint() -> None:
    assert validate("field", "anything", {"enum": []}) == []


def test_a_malformed_pattern_blames_the_declaration_not_the_value() -> None:
    """The prompt author wrote a bad regex; the caller's input is fine.
    Reporting it as a value error would send them debugging the wrong
    thing."""
    errors = validate("field", "abc", {"pattern": "([unclosed"})
    assert len(errors) == 1
    assert "validation pattern is invalid" in errors[0]


def test_numeric_rules_are_ignored_for_non_numeric_values() -> None:
    assert validate("field", "text", {"min": 5}) == []


# ---------------------------------------------------------------------------
# precedence
# ---------------------------------------------------------------------------


def test_precedence_order_is_most_specific_first() -> None:
    ranks = [
        precedence_rank(kind)
        for kind in (
            VariableKind.RUNTIME,
            VariableKind.PROJECT,
            VariableKind.ORGANIZATION,
            VariableKind.ENVIRONMENT,
            VariableKind.DYNAMIC,
            VariableKind.STATIC,
        )
    ]
    assert ranks == sorted(ranks)
    assert ranks == list(range(6))


@pytest.mark.parametrize("kind", [VariableKind.SECRET_REFERENCE, VariableKind.COMPUTED])
def test_non_supplied_kinds_rank_last(kind: VariableKind) -> None:
    """Neither has a *supplied* value competing for the slot -- one is
    fetched, the other derived."""
    assert precedence_rank(kind) == 6


def test_merge_picks_the_most_specific_supplied_value() -> None:
    candidates = {
        VariableKind.STATIC: "static",
        VariableKind.RUNTIME: "runtime",
        VariableKind.PROJECT: "project",
    }
    assert merge_by_precedence(candidates) == "runtime"


def test_merge_falls_through_to_the_least_specific_available() -> None:
    assert merge_by_precedence({VariableKind.STATIC: "static"}) == "static"


def test_merge_of_nothing_is_none() -> None:
    assert merge_by_precedence({}) is None


# ---------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------


def test_a_supplied_value_wins_over_the_default() -> None:
    specs = [VariableSpec(name="n", default_value="fallback")]
    assert resolve(specs, {"n": "supplied"}).values["n"] == "supplied"


def test_the_default_is_used_when_nothing_is_supplied() -> None:
    specs = [VariableSpec(name="n", default_value="fallback")]
    assert resolve(specs, {}).values["n"] == "fallback"


def test_a_required_variable_with_no_value_is_an_error() -> None:
    result = resolve([VariableSpec(name="n", required=True)], {})
    assert result.ok is False
    assert "required but not supplied" in result.errors[0]


def test_an_optional_variable_with_no_value_is_simply_absent() -> None:
    result = resolve([VariableSpec(name="n", required=False)], {})
    assert result.ok is True
    assert "n" not in result.values


def test_values_are_coerced_to_their_declared_type() -> None:
    specs = [VariableSpec(name="count", value_type=VariableType.INTEGER)]
    assert resolve(specs, {"count": "42"}).values["count"] == 42


def test_a_coercion_failure_is_reported_not_raised() -> None:
    specs = [VariableSpec(name="count", value_type=VariableType.INTEGER)]
    result = resolve(specs, {"count": "abc"})
    assert result.ok is False
    assert "not a valid integer" in result.errors[0]


def test_validation_rules_are_applied_to_resolved_values() -> None:
    specs = [
        VariableSpec(
            name="count", value_type=VariableType.INTEGER, validation_rules={"min": 1, "max": 5}
        )
    ]
    assert resolve(specs, {"count": "9"}).ok is False
    assert resolve(specs, {"count": "3"}).ok is True


def test_every_problem_accumulates_across_variables() -> None:
    specs = [
        VariableSpec(name="a", value_type=VariableType.INTEGER, validation_rules={"max": 1}),
        VariableSpec(name="b", validation_rules={"enum": ["x"]}),
        VariableSpec(name="c", required=True),
    ]
    result = resolve(specs, {"a": "99", "b": "wrong"})
    assert len(result.errors) == 3


def test_resolution_result_defaults() -> None:
    result = ResolutionResult()
    assert result.ok is True
    assert result.values == {}
    assert result.masked_names == set()


# ---------------------------------------------------------------------------
# secrets
# ---------------------------------------------------------------------------


def test_a_secret_resolves_through_the_injected_resolver() -> None:
    specs = [
        VariableSpec(
            name="token", kind=VariableKind.SECRET_REFERENCE, secret_reference="svc/api-key"
        )
    ]
    result = resolve(specs, {}, secret_resolver=lambda ref: f"resolved:{ref}")
    assert result.values["token"] == "resolved:svc/api-key"


def test_a_secret_name_is_always_masked() -> None:
    """Whether or not anyone remembered to tick ``is_masked``."""
    specs = [VariableSpec(name="token", kind=VariableKind.SECRET_REFERENCE, secret_reference="r")]
    result = resolve(specs, {}, secret_resolver=lambda _r: "value")
    assert result.masked_names == {"token"}


def test_a_secret_without_a_resolver_is_an_error_not_a_silent_blank() -> None:
    specs = [VariableSpec(name="token", kind=VariableKind.SECRET_REFERENCE, secret_reference="r")]
    result = resolve(specs, {})
    assert result.ok is False
    assert "without a secret resolver" in result.errors[0]


def test_a_secret_reference_kind_with_no_reference_is_an_error() -> None:
    specs = [VariableSpec(name="token", kind=VariableKind.SECRET_REFERENCE)]
    result = resolve(specs, {}, secret_resolver=lambda _r: "value")
    assert result.ok is False
    assert "carries no reference" in result.errors[0]


def test_a_failing_resolver_is_reported_not_propagated() -> None:
    def explode(_reference: str) -> str:
        raise RuntimeError("vault unreachable")

    specs = [VariableSpec(name="token", kind=VariableKind.SECRET_REFERENCE, secret_reference="r")]
    result = resolve(specs, {}, secret_resolver=explode)
    assert result.ok is False
    assert "vault unreachable" in result.errors[0]


def test_an_explicitly_masked_plain_variable_is_masked_too() -> None:
    specs = [VariableSpec(name="pii", is_masked=True, default_value="x")]
    assert resolve(specs, {}).masked_names == {"pii"}


# ---------------------------------------------------------------------------
# computed variables
# ---------------------------------------------------------------------------


def test_a_computed_variable_sees_already_resolved_values() -> None:
    """Computed resolve LAST, which is the whole point of having them."""
    specs = [
        VariableSpec(name="first", default_value="Ada"),
        VariableSpec(name="last", default_value="Lovelace"),
        VariableSpec(
            name="full",
            kind=VariableKind.COMPUTED,
            computed_expression='first ~ " " ~ last',
        ),
    ]
    assert resolve(specs, {}).values["full"] == "Ada Lovelace"


def test_a_computed_variable_declared_first_still_resolves_last() -> None:
    specs = [
        VariableSpec(name="doubled", kind=VariableKind.COMPUTED, computed_expression="base * 2"),
        VariableSpec(name="base", value_type=VariableType.INTEGER, default_value="21"),
    ]
    assert resolve(specs, {}).values["doubled"] == 42


def test_a_computed_kind_with_no_expression_is_an_error() -> None:
    result = resolve([VariableSpec(name="c", kind=VariableKind.COMPUTED)], {})
    assert result.ok is False
    assert "carries no expression" in result.errors[0]


def test_a_failing_expression_is_reported_not_propagated() -> None:
    specs = [
        VariableSpec(name="c", kind=VariableKind.COMPUTED, computed_expression="missing_name + 1")
    ]
    result = resolve(specs, {})
    assert result.ok is False
    assert "computed expression failed" in result.errors[0]


def test_a_computed_variable_is_validated_like_any_other() -> None:
    specs = [
        VariableSpec(name="base", value_type=VariableType.INTEGER, default_value="99"),
        VariableSpec(
            name="c",
            kind=VariableKind.COMPUTED,
            computed_expression="base",
            validation_rules={"max": 10},
        ),
    ]
    assert resolve(specs, {}).ok is False


def test_a_computed_variable_can_be_masked() -> None:
    specs = [
        VariableSpec(name="base", default_value="x"),
        VariableSpec(
            name="c", kind=VariableKind.COMPUTED, computed_expression="base", is_masked=True
        ),
    ]
    assert "c" in resolve(specs, {}).masked_names


def test_a_computed_expression_cannot_escape_the_sandbox() -> None:
    """Computed expressions are authored by the same people who author
    templates, so the same code-execution reasoning applies."""
    specs = [
        VariableSpec(
            name="c",
            kind=VariableKind.COMPUTED,
            computed_expression="''.__class__.__mro__",
        )
    ]
    result = resolve(specs, {})
    assert result.ok is False


# ---------------------------------------------------------------------------
# end to end
# ---------------------------------------------------------------------------


def test_a_realistic_mixed_resolution() -> None:
    specs = [
        VariableSpec(name="topic", required=True),
        VariableSpec(
            name="count",
            value_type=VariableType.INTEGER,
            default_value="3",
            validation_rules={"min": 1, "max": 5},
        ),
        VariableSpec(name="token", kind=VariableKind.SECRET_REFERENCE, secret_reference="svc/key"),
        VariableSpec(
            name="header",
            kind=VariableKind.COMPUTED,
            computed_expression='topic ~ " (" ~ count ~ ")"',
        ),
    ]
    result = resolve(specs, {"topic": "AI"}, secret_resolver=lambda _r: REDACTION_PLACEHOLDER)
    assert result.ok is True
    assert result.values["topic"] == "AI"
    assert result.values["count"] == 3
    assert result.values["header"] == "AI (3)"
    assert result.masked_names == {"token"}
