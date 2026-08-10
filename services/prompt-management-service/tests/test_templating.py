"""Tests for :mod:`app.templating.renderer`.

Pure module -- no database. The security assertions here are the point
of the whole file: a prompt template is user-authored by definition, so
the sandbox is what stands between an editable template and arbitrary
code execution.
"""

from __future__ import annotations

import pytest

from app.templating.renderer import (
    DEFAULT_MAX_DEPTH,
    RenderedPrompt,
    TemplateBundle,
    TemplateRenderError,
    TemplateSource,
    declared_variables,
    render,
    render_body,
    resolve_depth,
    validate_syntax,
)

# ---------------------------------------------------------------------------
# The sandbox -- the reason this module exists
# ---------------------------------------------------------------------------

SSTI_PAYLOADS = [
    "{{ ''.__class__.__mro__[1].__subclasses__() }}",
    "{{ ''.__class__.__base__.__subclasses__() }}",
    "{{ config.__class__.__init__.__globals__ }}",
    "{{ cycler.__init__.__globals__.os.popen('id').read() }}",
    "{{ ''.__class__.__mro__[1].__subclasses__()[0].__init__.__globals__ }}",
    "{{ self.__init__.__globals__ }}",
]


@pytest.mark.parametrize("payload", SSTI_PAYLOADS)
def test_sandbox_blocks_attribute_escape(payload: str) -> None:
    """Every classic SSTI payload must be refused, not rendered."""
    with pytest.raises(TemplateRenderError):
        render_body(payload, {})


def test_sandbox_blocks_escape_even_when_object_is_supplied() -> None:
    """Reaching through a *supplied* object must fail too.

    The dangerous case is not a bare literal but an object a caller
    legitimately passed in as a variable.
    """

    class Holder:
        secret = "s3cret"

    with pytest.raises(TemplateRenderError):
        render_body("{{ obj.__class__.__init__.__globals__ }}", {"obj": Holder()})


def test_ordinary_attribute_access_still_works() -> None:
    """The sandbox must not break legitimate templates."""
    result = render_body("{{ row.name }}", {"row": {"name": "Ada"}})
    assert result.body == "Ada"


# ---------------------------------------------------------------------------
# StrictUndefined
# ---------------------------------------------------------------------------


def test_missing_variable_raises_rather_than_rendering_empty() -> None:
    """A silently truncated prompt is worse than a loud failure."""
    with pytest.raises(TemplateRenderError, match="critical"):
        render_body("Do the thing. {{ critical }}", {})


def test_supplied_variable_renders() -> None:
    assert render_body("Hello {{ name }}!", {"name": "World"}).body == "Hello World!"


def test_empty_string_variable_is_not_treated_as_missing() -> None:
    """An explicit empty string is a value, not an absence."""
    assert render_body("[{{ x }}]", {"x": ""}).body == "[]"


# ---------------------------------------------------------------------------
# render_body basics
# ---------------------------------------------------------------------------


def test_conditional_section_true_branch() -> None:
    assert render_body("{% if flag %}YES{% else %}NO{% endif %}", {"flag": True}).body == "YES"


def test_conditional_section_false_branch() -> None:
    assert render_body("{% if flag %}YES{% else %}NO{% endif %}", {"flag": False}).body == "NO"


def test_loop_renders_each_item() -> None:
    result = render_body("{% for i in items %}{{ i }},{% endfor %}", {"items": [1, 2, 3]})
    assert result.body == "1,2,3,"


def test_render_body_reports_variables_used() -> None:
    result = render_body("{{ a }}{{ b }}", {"a": 1, "b": 2})
    assert result.variables_used == ("a", "b")


def test_render_body_depth_is_one() -> None:
    assert render_body("plain", {}).depth == 1


def test_trailing_newline_is_kept() -> None:
    """``keep_trailing_newline`` -- a prompt's final newline can matter
    to a model's own formatting."""
    assert render_body("line\n", {}).body == "line\n"


def test_syntax_error_is_wrapped() -> None:
    with pytest.raises(TemplateRenderError, match="syntax error"):
        render_body("Hello {{ unclosed", {})


def test_unknown_filter_is_wrapped_not_leaked() -> None:
    """Jinja2 raises this from its CODE GENERATOR, not its parser.

    Regression test for a real fix: guarding only ``parse()`` let a
    ``TemplateAssertionError`` escape as a raw Jinja2 exception.
    """
    with pytest.raises(TemplateRenderError, match="No filter named"):
        render_body("{{ x | no_such_filter }}", {"x": 1})


def test_rendered_body_over_the_ceiling_is_refused() -> None:
    """A runaway loop must not exhaust memory before reaching a model."""
    with pytest.raises(TemplateRenderError, match="runaway loop"):
        render_body("{% for i in range(1000) %}xxxxxxxxxx{% endfor %}", {}, max_length=100)


def test_body_exactly_at_the_ceiling_is_allowed() -> None:
    """The limit is a ceiling, not an off-by-one exclusion."""
    assert render_body("x" * 50, {}, max_length=50).body == "x" * 50


def test_a_self_recursive_macro_is_caught_rather_than_crashing() -> None:
    """The one runaway shape ``resolve_depth``'s graph walk cannot see.

    A macro calling itself never touches the parent/include graph, so
    only the render-time ``RecursionError`` guard catches it. Without
    that guard this would exhaust the interpreter stack and take the
    process down rather than failing one request.
    """
    body = "{% macro forever(n) %}{{ forever(n) }}{% endmacro %}{{ forever(1) }}"
    with pytest.raises(TemplateRenderError, match="recursed without terminating"):
        render_body(body, {})


# ---------------------------------------------------------------------------
# declared_variables / validate_syntax
# ---------------------------------------------------------------------------


def test_declared_variables_reports_the_iterable_not_the_loop_target() -> None:
    """``rows`` is undeclared; ``row`` is bound by the loop itself."""
    assert declared_variables("{% for row in rows %}{{ row.x }}{% endfor %}") == ("rows",)


def test_declared_variables_is_sorted_and_deduplicated() -> None:
    assert declared_variables("{{ b }}{{ a }}{{ b }}") == ("a", "b")


def test_declared_variables_empty_for_a_static_body() -> None:
    assert declared_variables("no variables here") == ()


def test_declared_variables_raises_on_invalid_syntax() -> None:
    with pytest.raises(TemplateRenderError):
        declared_variables("{% if %}")


def test_validate_syntax_returns_none_when_valid() -> None:
    assert validate_syntax("Hello {{ name }}") is None


def test_validate_syntax_returns_a_message_when_invalid() -> None:
    message = validate_syntax("Hello {{ unclosed")
    assert message is not None
    assert "syntax error" in message


def test_validate_syntax_catches_the_compile_stage_too() -> None:
    message = validate_syntax("{{ x | no_such_filter }}")
    assert message is not None
    assert "No filter named" in message


# ---------------------------------------------------------------------------
# TemplateBundle / resolve_depth
# ---------------------------------------------------------------------------


def _bundle(*sources: TemplateSource) -> TemplateBundle:
    bundle = TemplateBundle()
    for source in sources:
        bundle.add(source)
    return bundle


def test_bundle_as_loader_mapping() -> None:
    bundle = _bundle(TemplateSource(slug="a", body="A"), TemplateSource(slug="b", body="B"))
    assert bundle.as_loader_mapping() == {"a": "A", "b": "B"}


def test_resolve_depth_of_a_lone_template_is_one() -> None:
    assert resolve_depth(_bundle(TemplateSource(slug="a", body="A")), "a") == 1


def test_resolve_depth_counts_a_parent_chain() -> None:
    bundle = _bundle(
        TemplateSource(slug="child", body="C", parent_slug="parent"),
        TemplateSource(slug="parent", body="P"),
    )
    assert resolve_depth(bundle, "child") == 2


def test_resolve_depth_counts_includes() -> None:
    bundle = _bundle(
        TemplateSource(slug="main", body="M", included_slugs=("part",)),
        TemplateSource(slug="part", body="P"),
    )
    assert resolve_depth(bundle, "main") == 2


def test_resolve_depth_refuses_a_cycle() -> None:
    """Detected on a graph walk so the render cannot recurse into a
    stack overflow."""
    bundle = _bundle(
        TemplateSource(slug="a", body="A", parent_slug="b"),
        TemplateSource(slug="b", body="B", parent_slug="a"),
    )
    with pytest.raises(TemplateRenderError, match="cyclic"):
        resolve_depth(bundle, "a")


def test_resolve_depth_refuses_a_self_cycle() -> None:
    bundle = _bundle(TemplateSource(slug="a", body="A", parent_slug="a"))
    with pytest.raises(TemplateRenderError, match="cyclic"):
        resolve_depth(bundle, "a")


def test_resolve_depth_refuses_a_chain_deeper_than_the_limit() -> None:
    bundle = TemplateBundle()
    for index in range(6):
        bundle.add(TemplateSource(slug=f"t{index}", body="x", parent_slug=f"t{index + 1}"))
    bundle.add(TemplateSource(slug="t6", body="x"))
    with pytest.raises(TemplateRenderError, match="nests deeper"):
        resolve_depth(bundle, "t0", max_depth=3)


def test_resolve_depth_refuses_an_unknown_slug() -> None:
    with pytest.raises(TemplateRenderError, match="not available"):
        resolve_depth(TemplateBundle(), "missing")


def test_resolve_depth_refuses_a_dangling_reference() -> None:
    bundle = _bundle(TemplateSource(slug="a", body="A", parent_slug="gone"))
    with pytest.raises(TemplateRenderError, match="referenced but not available"):
        resolve_depth(bundle, "a")


def test_default_max_depth_is_exposed() -> None:
    assert DEFAULT_MAX_DEPTH == 10


# ---------------------------------------------------------------------------
# render() over a bundle -- inheritance and composition
# ---------------------------------------------------------------------------


def test_inheritance_renders_the_child_block() -> None:
    bundle = _bundle(
        TemplateSource(slug="base", body="[{% block c %}default{% endblock %}]"),
        TemplateSource(
            slug="child",
            body='{% extends "base" %}{% block c %}child-{{ v }}{% endblock %}',
            parent_slug="base",
        ),
    )
    result = render(bundle, "child", {"v": 1})
    assert result.body == "[child-1]"
    assert result.depth == 2


def test_inheritance_falls_back_to_the_parent_block() -> None:
    bundle = _bundle(
        TemplateSource(slug="base", body="[{% block c %}default{% endblock %}]"),
        TemplateSource(slug="child", body='{% extends "base" %}', parent_slug="base"),
    )
    assert render(bundle, "child", {}).body == "[default]"


def test_composition_includes_a_shared_component() -> None:
    bundle = _bundle(
        TemplateSource(slug="main", body='A{% include "part" %}C', included_slugs=("part",)),
        TemplateSource(slug="part", body="B"),
    )
    assert render(bundle, "main", {}).body == "ABC"


def test_included_component_sees_the_same_variables() -> None:
    bundle = _bundle(
        TemplateSource(slug="main", body='{% include "part" %}', included_slugs=("part",)),
        TemplateSource(slug="part", body="{{ who }}"),
    )
    assert render(bundle, "main", {"who": "Ada"}).body == "Ada"


def test_render_refuses_a_missing_include_at_render_time() -> None:
    """The bundle deliberately omits an unresolvable component so the
    renderer reports which slug is missing."""
    bundle = _bundle(TemplateSource(slug="main", body='{% include "gone" %}'))
    with pytest.raises(TemplateRenderError):
        render(bundle, "main", {})


def test_render_reports_the_rendered_prompt_shape() -> None:
    bundle = _bundle(TemplateSource(slug="a", body="{{ x }}"))
    result = render(bundle, "a", {"x": 1})
    assert isinstance(result, RenderedPrompt)
    assert result.variables_used == ("x",)
    assert result.truncated is False
