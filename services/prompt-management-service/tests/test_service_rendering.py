"""Tests for :mod:`app.services.rendering` -- the read path every other
AI-IOS service actually calls.

Real PostgreSQL throughout: real prompts, real revisions, real template
inheritance and include chains, real variable declarations. Nothing is
stubbed, because most of what makes this module correct is *which rows it
gathers before rendering* -- a mocked repository would prove nothing
about that.

Two properties get the most attention here, because both are the kind of
bug that only shows up in production:

- **A draft must never resolve through** :meth:`RenderingService.render`.
  That is the whole reason ``render`` and ``preview`` are separate
  methods rather than one method with a flag.
- **The returned body and the recorded body must differ for a masked
  variable.** A secret has to reach the model to be useful and must never
  reach the execution history, so a test that only checked one of the two
  bodies would pass against a service that leaked into both.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio
from shared_core.exceptions.conflict import ConflictError
from shared_core.exceptions.not_found import NotFoundError
from shared_core.exceptions.validation import ValidationError

from app.models.enums import (
    PromptLifecycleStatus,
    VariableKind,
    VariableType,
    VersionBump,
)
from app.models.prompt import PromptVersion
from app.models.template import PromptTemplate, PromptVariable
from app.repositories.prompt import PromptRepository, PromptVersionRepository
from app.repositories.template import PromptTemplateRepository, PromptVariableRepository
from app.security.redaction import REDACTION_PLACEHOLDER
from app.services.prompt import PromptService
from app.services.rendering import RenderingService, declared_but_unused
from app.variables import resolution
from tests.conftest import MakePromptFn, MakePublishedFn

# No module-level asyncio mark: pytest-asyncio runs in "auto" mode here,
# and an explicit mark would also be applied to the pure-function
# ``declared_but_unused`` tests at the bottom, which are not coroutines.


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def make_template(templates_repo: PromptTemplateRepository, organization_id: uuid.UUID) -> Any:
    """Create one real template row."""

    async def _make(
        slug: str,
        body: str,
        *,
        locale: str = "en",
        parent: PromptTemplate | None = None,
        includes: list[str] | None = None,
    ) -> PromptTemplate:
        return await templates_repo.create(
            PromptTemplate(
                organization_id=organization_id,
                slug=slug,
                name=slug.replace("-", " ").title(),
                body=body,
                locale=locale,
                parent_template_id=parent.id if parent is not None else None,
                included_template_slugs=list(includes or []),
            )
        )

    return _make


@pytest.fixture
def declare_variable(variables_repo: PromptVariableRepository) -> Any:
    """Declare one variable on one revision."""

    async def _declare(
        version: PromptVersion,
        name: str,
        *,
        kind: VariableKind = VariableKind.RUNTIME,
        value_type: VariableType = VariableType.STRING,
        default_value: str | None = None,
        required: bool = True,
        secret_reference: str | None = None,
        computed_expression: str | None = None,
        validation_rules: dict[str, object] | None = None,
        is_masked: bool = False,
    ) -> PromptVariable:
        return await variables_repo.create(
            PromptVariable(
                organization_id=version.organization_id,
                prompt_version_id=version.id,
                name=name,
                kind=kind,
                value_type=value_type,
                default_value=default_value,
                required=required,
                secret_reference=secret_reference,
                computed_expression=computed_expression,
                validation_rules=dict(validation_rules or {}),
                is_masked=is_masked,
            )
        )

    return _declare


@pytest_asyncio.fixture
async def published(make_published: MakePublishedFn, declare_variable: Any) -> Any:
    """A published prompt whose one declared variable is ``name``."""
    prompt, version = await make_published("greeting")
    await declare_variable(version, "name")
    return prompt, version


# ---------------------------------------------------------------------------
# resolve() -- which prompts and revisions are reachable at all
# ---------------------------------------------------------------------------


async def test_resolve_returns_the_live_revision_of_a_published_prompt(
    rendering_service: RenderingService, published: Any, organization_id: uuid.UUID
) -> None:
    prompt, version = published

    found_prompt, found_version = await rendering_service.resolve(organization_id, "greeting")

    assert found_prompt.id == prompt.id
    assert found_version.id == version.id


async def test_resolve_refuses_an_unknown_slug(
    rendering_service: RenderingService, organization_id: uuid.UUID
) -> None:
    with pytest.raises(NotFoundError, match="No prompt with slug 'nope'"):
        await rendering_service.resolve(organization_id, "nope")


async def test_resolve_is_scoped_to_the_calling_tenant(
    rendering_service: RenderingService, published: Any
) -> None:
    """The slug exists -- just not in the organization asking for it."""
    with pytest.raises(NotFoundError):
        await rendering_service.resolve(uuid.uuid4(), "greeting")


@pytest.mark.parametrize(
    "status",
    [
        PromptLifecycleStatus.DRAFT,
        PromptLifecycleStatus.REVIEW,
        PromptLifecycleStatus.APPROVAL,
        PromptLifecycleStatus.ARCHIVED,
    ],
)
async def test_resolve_refuses_every_unpublished_status(
    rendering_service: RenderingService,
    prompts_repo: PromptRepository,
    published: Any,
    organization_id: uuid.UUID,
    status: PromptLifecycleStatus,
) -> None:
    """The load-bearing guard of this whole module: unreviewed,
    unapproved, unscanned text must not reach a model."""
    prompt, _version = published
    prompt.status = status
    await prompts_repo.update(prompt)

    with pytest.raises(ConflictError, match="only published or deprecated"):
        await rendering_service.resolve(organization_id, "greeting")


async def test_resolve_still_serves_a_deprecated_prompt(
    rendering_service: RenderingService,
    prompts_repo: PromptRepository,
    published: Any,
    organization_id: uuid.UUID,
) -> None:
    """Deprecation is a migration window, not a shutdown. A deprecated
    prompt that stopped rendering would break production rather than warn
    about it."""
    prompt, version = published
    prompt.status = PromptLifecycleStatus.DEPRECATED
    await prompts_repo.update(prompt)

    _found, found_version = await rendering_service.resolve(organization_id, "greeting")
    assert found_version.id == version.id


async def test_resolve_refuses_a_published_prompt_with_no_live_revision(
    rendering_service: RenderingService,
    versions_repo: PromptVersionRepository,
    published: Any,
    organization_id: uuid.UUID,
) -> None:
    """A state that should not exist, reported as a conflict rather than
    a ``None`` that would surface later as an attribute error."""
    prompt, _version = published
    await versions_repo.clear_current(prompt.id)

    with pytest.raises(ConflictError, match="has no live revision"):
        await rendering_service.resolve(organization_id, "greeting")


async def test_resolve_pins_a_named_historical_revision(
    rendering_service: RenderingService,
    prompt_service: PromptService,
    published: Any,
    organization_id: uuid.UUID,
) -> None:
    """Reproducibility: a caller can ask for the exact revision it was
    built against, not merely whatever is live now."""
    prompt, first = published
    second = await prompt_service.add_version(
        prompt, body="Hi {{ name }}", component=VersionBump.MINOR
    )
    await prompt_service.publish(prompt, second)

    _p, pinned = await rendering_service.resolve(
        organization_id, "greeting", version_number=first.version_number
    )
    assert pinned.id == first.id

    _p, live = await rendering_service.resolve(organization_id, "greeting")
    assert live.id == second.id


async def test_resolve_refuses_a_version_number_that_does_not_exist(
    rendering_service: RenderingService, published: Any, organization_id: uuid.UUID
) -> None:
    with pytest.raises(NotFoundError, match=r"has no version 9\.9\.9"):
        await rendering_service.resolve(organization_id, "greeting", version_number="9.9.9")


async def test_pinning_cannot_reach_a_revision_that_was_never_published(
    rendering_service: RenderingService,
    prompt_service: PromptService,
    published: Any,
    organization_id: uuid.UUID,
) -> None:
    """Pinning bypasses the status check on the *prompt*, never on the
    revision -- otherwise a version number would be a way around the
    review gate entirely."""
    prompt, _first = published
    draft = await prompt_service.add_version(
        prompt, body="Draft {{ name }}", component=VersionBump.MINOR
    )

    with pytest.raises(ConflictError, match="was never published"):
        await rendering_service.resolve(
            organization_id, "greeting", version_number=draft.version_number
        )


async def test_pinning_works_even_when_the_prompt_itself_is_archived(
    rendering_service: RenderingService,
    prompts_repo: PromptRepository,
    published: Any,
    organization_id: uuid.UUID,
) -> None:
    """A pinned revision is a reproducibility request about history, and
    archiving the prompt does not un-publish what already shipped."""
    prompt, version = published
    prompt.status = PromptLifecycleStatus.ARCHIVED
    await prompts_repo.update(prompt)

    _p, pinned = await rendering_service.resolve(
        organization_id, "greeting", version_number=version.version_number
    )
    assert pinned.id == version.id


# ---------------------------------------------------------------------------
# render() -- the production read path
# ---------------------------------------------------------------------------


async def test_render_substitutes_a_supplied_variable(
    rendering_service: RenderingService, published: Any, organization_id: uuid.UUID
) -> None:
    result = await rendering_service.render(organization_id, "greeting", {"name": "Ada"})

    assert result.body == "Hello Ada"
    assert result.variables_used == ("name",)
    assert result.prompt is not None
    assert result.prompt.slug == "greeting"


async def test_render_reports_the_revisions_own_token_estimate(
    rendering_service: RenderingService, published: Any, organization_id: uuid.UUID
) -> None:
    _prompt, version = published

    result = await rendering_service.render(organization_id, "greeting", {"name": "Ada"})

    assert result.estimated_tokens == version.estimated_tokens
    assert result.estimated_tokens > 0


async def test_render_refuses_a_missing_required_variable(
    rendering_service: RenderingService, published: Any, organization_id: uuid.UUID
) -> None:
    """Rendering under ``StrictUndefined`` would fail anyway; failing
    here names the variable instead of surfacing a Jinja2 internal."""
    with pytest.raises(ValidationError, match="could not be rendered"):
        await rendering_service.render(organization_id, "greeting", {})


async def test_render_refuses_a_variable_that_fails_its_own_rules(
    rendering_service: RenderingService,
    make_published: MakePublishedFn,
    declare_variable: Any,
    organization_id: uuid.UUID,
) -> None:
    _prompt, version = await make_published("bounded", body="Score {{ score }}")
    await declare_variable(
        version, "score", value_type=VariableType.INTEGER, validation_rules={"max": 10}
    )

    with pytest.raises(ValidationError, match="could not be rendered"):
        await rendering_service.render(organization_id, "bounded", {"score": 99})


async def test_render_uses_a_declared_default_when_nothing_is_supplied(
    rendering_service: RenderingService,
    make_published: MakePublishedFn,
    declare_variable: Any,
    organization_id: uuid.UUID,
) -> None:
    _prompt, version = await make_published("defaulted", body="Hello {{ name }}")
    await declare_variable(
        version, "name", kind=VariableKind.STATIC, default_value="there", required=False
    )

    result = await rendering_service.render(organization_id, "defaulted", {})
    assert result.body == "Hello there"


async def test_render_can_pin_a_version_number(
    rendering_service: RenderingService,
    prompt_service: PromptService,
    published: Any,
    declare_variable: Any,
    organization_id: uuid.UUID,
) -> None:
    prompt, first = published
    second = await prompt_service.add_version(
        prompt, body="Goodbye {{ name }}", component=VersionBump.MINOR
    )
    await prompt_service.publish(prompt, second)

    pinned = await rendering_service.render(
        organization_id, "greeting", {"name": "Ada"}, version_number=first.version_number
    )
    live = await rendering_service.render(organization_id, "greeting", {"name": "Ada"})

    assert pinned.body == "Hello Ada"
    assert live.body == "Goodbye Ada"


async def test_render_surfaces_a_template_failure_as_a_validation_error(
    rendering_service: RenderingService,
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    make_published: MakePublishedFn,
    organization_id: uuid.UUID,
) -> None:
    """A body that got into the database before the current validation --
    or through a direct write -- must fail as a caller-facing error, not
    a raw Jinja2 exception."""
    _prompt, version = await make_published("broken", body="ok")
    version.body = "Hello {{ name"
    await versions_repo.update(version)

    with pytest.raises(ValidationError, match="could not be rendered"):
        await rendering_service.render(organization_id, "broken", {"name": "Ada"})


async def test_render_refuses_output_longer_than_the_configured_limit(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    templates_repo: PromptTemplateRepository,
    variables_repo: PromptVariableRepository,
    make_published: MakePublishedFn,
    declare_variable: Any,
    organization_id: uuid.UUID,
) -> None:
    """The length cap is a real defence: a caller-supplied value expanded
    inside a loop is how one small request becomes a huge model bill."""
    _prompt, version = await make_published(
        "loopy", body="{% for _ in range(200) %}{{ filler }}{% endfor %}"
    )
    await declare_variable(version, "filler")

    service = RenderingService(
        prompts_repo, versions_repo, templates_repo, variables_repo, max_length=100
    )

    with pytest.raises(ValidationError, match="could not be rendered"):
        await service.render(organization_id, "loopy", {"filler": "x" * 10})


# ---------------------------------------------------------------------------
# Masking -- the returned body and the recorded body must differ
# ---------------------------------------------------------------------------


async def test_a_masked_variable_reaches_the_caller_but_not_the_record(
    rendering_service: RenderingService,
    make_published: MakePublishedFn,
    declare_variable: Any,
    organization_id: uuid.UUID,
) -> None:
    """The single most important assertion in this module. A secret has
    to reach the model to be useful and must never reach the execution
    history, so both bodies are checked -- one of them alone would pass
    against a service that leaked into both."""
    _prompt, version = await make_published("secretive", body="Token: {{ api_key }}")
    await declare_variable(version, "api_key", is_masked=True)

    result = await rendering_service.render(
        organization_id, "secretive", {"api_key": "sk-live-abc123"}
    )

    assert result.body == "Token: sk-live-abc123"
    assert result.masked_body == f"Token: {REDACTION_PLACEHOLDER}"
    assert "sk-live-abc123" not in result.masked_body
    assert result.masked_names == frozenset({"api_key"})


async def test_an_unmasked_variable_appears_in_both_bodies(
    rendering_service: RenderingService, published: Any, organization_id: uuid.UUID
) -> None:
    """Masking is opt-in; masking everything would make the recorded
    prompt useless for debugging."""
    result = await rendering_service.render(organization_id, "greeting", {"name": "Ada"})

    assert result.body == "Hello Ada"
    assert result.masked_body == "Hello Ada"
    assert result.masked_names == frozenset()


async def test_a_secret_reference_resolves_through_the_injected_resolver(
    rendering_service: RenderingService,
    make_published: MakePublishedFn,
    declare_variable: Any,
    organization_id: uuid.UUID,
) -> None:
    """A ``SECRET_REFERENCE`` variable stores only the lookup key, so the
    plaintext has no path into this service's own tables."""
    _prompt, version = await make_published("vaulted", body="Key: {{ api_key }}")
    await declare_variable(
        version,
        "api_key",
        kind=VariableKind.SECRET_REFERENCE,
        secret_reference="prod/openai",
        is_masked=True,
    )
    seen: list[str] = []

    def resolver(reference: str) -> str:
        seen.append(reference)
        return "sk-from-vault"

    result = await rendering_service.render(
        organization_id, "vaulted", {}, secret_resolver=resolver
    )

    assert seen == ["prod/openai"]
    assert result.body == "Key: sk-from-vault"
    assert result.masked_body == f"Key: {REDACTION_PLACEHOLDER}"


async def test_a_secret_reference_without_a_resolver_fails_rather_than_renders_blank(
    rendering_service: RenderingService,
    make_published: MakePublishedFn,
    declare_variable: Any,
    organization_id: uuid.UUID,
) -> None:
    """Rendering an empty string where a credential belongs would send a
    silently broken prompt to the model."""
    _prompt, version = await make_published("unvaulted", body="Key: {{ api_key }}")
    await declare_variable(
        version, "api_key", kind=VariableKind.SECRET_REFERENCE, secret_reference="prod/openai"
    )

    with pytest.raises(ValidationError, match="could not be rendered"):
        await rendering_service.render(organization_id, "unvaulted", {})


# ---------------------------------------------------------------------------
# Template inheritance and composition
# ---------------------------------------------------------------------------


async def test_render_walks_a_parent_template_chain(
    rendering_service: RenderingService,
    versions_repo: PromptVersionRepository,
    make_published: MakePublishedFn,
    make_template: Any,
    declare_variable: Any,
    organization_id: uuid.UUID,
) -> None:
    """Inheritance across two levels, gathered before the render rather
    than resolved lazily by name mid-render."""
    grandparent = await make_template("layout", "[{% block content %}nothing{% endblock %}]")
    parent = await make_template(
        "framed",
        '{% extends "layout" %}{% block content %}<{% block inner %}?{% endblock %}>{% endblock %}',
        parent=grandparent,
    )

    _prompt, version = await make_published(
        "nested", body='{% extends "framed" %}{% block inner %}{{ name }}{% endblock %}'
    )
    version.template_id = parent.id
    await versions_repo.update(version)
    await declare_variable(version, "name")

    result = await rendering_service.render(organization_id, "nested", {"name": "Ada"})
    assert result.body == "[<Ada>]"


async def test_render_pulls_in_an_included_shared_component(
    rendering_service: RenderingService,
    versions_repo: PromptVersionRepository,
    make_published: MakePublishedFn,
    make_template: Any,
    organization_id: uuid.UUID,
) -> None:
    await make_template("signature", "-- The Team")
    parent = await make_template(
        "with-signature",
        '{% block body %}{% endblock %}\n{% include "signature" %}',
        includes=["signature"],
    )

    _prompt, version = await make_published(
        "composed", body='{% extends "with-signature" %}{% block body %}Hi{% endblock %}'
    )
    version.template_id = parent.id
    await versions_repo.update(version)

    result = await rendering_service.render(organization_id, "composed", {})
    assert result.body == "Hi\n-- The Team"


async def test_a_missing_include_fails_with_the_slug_that_is_missing(
    rendering_service: RenderingService,
    versions_repo: PromptVersionRepository,
    make_published: MakePublishedFn,
    make_template: Any,
    organization_id: uuid.UUID,
) -> None:
    """Left absent from the bundle deliberately: the renderer reports the
    missing slug with the surrounding render context, which beats an
    error raised blind during gathering."""
    parent = await make_template(
        "needs-missing", '{% include "never-created" %}', includes=["never-created"]
    )

    _prompt, version = await make_published("incomplete", body='{% extends "needs-missing" %}')
    version.template_id = parent.id
    await versions_repo.update(version)

    with pytest.raises(ValidationError, match="never-created"):
        await rendering_service.render(organization_id, "incomplete", {})


async def test_gathering_terminates_on_a_cyclic_include_chain(
    rendering_service: RenderingService,
    templates_repo: PromptTemplateRepository,
    versions_repo: PromptVersionRepository,
    make_published: MakePublishedFn,
    make_template: Any,
    organization_id: uuid.UUID,
) -> None:
    """The renderer refuses the cycle too, but a *gather* that hung would
    never reach that check -- so the walk tracks what it has seen."""
    first = await make_template("ping", '{% include "pong" %}', includes=["pong"])
    second = await make_template("pong", "pong!", includes=["ping"])
    first.included_template_slugs = ["pong"]
    second.included_template_slugs = ["ping"]
    await templates_repo.update(second)

    _prompt, version = await make_published("cyclic", body='{% extends "ping" %}')
    version.template_id = first.id
    await versions_repo.update(version)

    # Terminating at all is the assertion; whether the render then
    # succeeds or is refused is the renderer's own decision.
    with pytest.raises(ValidationError):
        await rendering_service.render(organization_id, "cyclic", {})


async def test_a_parent_template_from_another_tenant_is_unreachable(
    rendering_service: RenderingService,
    templates_repo: PromptTemplateRepository,
    versions_repo: PromptVersionRepository,
    make_published: MakePublishedFn,
    organization_id: uuid.UUID,
) -> None:
    """``require_in_org`` is what stops one tenant's revision rendering
    another tenant's template body."""
    foreign = await templates_repo.create(
        PromptTemplate(
            organization_id=uuid.uuid4(),
            slug="theirs",
            name="Theirs",
            body="[{% block content %}{% endblock %}]",
        )
    )

    _prompt, version = await make_published("borrower", body="mine")
    version.template_id = foreign.id
    await versions_repo.update(version)

    with pytest.raises(NotFoundError):
        await rendering_service.render(organization_id, "borrower", {})


async def test_an_included_component_falls_back_across_locales(
    rendering_service: RenderingService,
    versions_repo: PromptVersionRepository,
    make_published: MakePublishedFn,
    make_template: Any,
    organization_id: uuid.UUID,
) -> None:
    """A shared component that has not been translated yet should still
    resolve, rather than failing the whole render over a missing
    locale."""
    await make_template("footer", "EN footer", locale="en")
    parent = await make_template(
        "localised", '{% include "footer" %}', locale="en", includes=["footer"]
    )

    _prompt, version = await make_published("fr-caller", body='{% extends "localised" %}')
    version.template_id = parent.id
    await versions_repo.update(version)

    result = await rendering_service.render(organization_id, "fr-caller", {}, locale="fr")
    assert result.body == "EN footer"


async def test_a_localised_component_is_preferred_when_it_exists(
    rendering_service: RenderingService,
    versions_repo: PromptVersionRepository,
    make_published: MakePublishedFn,
    make_template: Any,
    organization_id: uuid.UUID,
) -> None:
    await make_template("greetingpart", "Hello", locale="en")
    await make_template("greetingpart", "Bonjour", locale="fr")
    parent = await make_template(
        "wrapper", '{% include "greetingpart" %}', locale="en", includes=["greetingpart"]
    )

    _prompt, version = await make_published("locale-aware", body='{% extends "wrapper" %}')
    version.template_id = parent.id
    await versions_repo.update(version)

    french = await rendering_service.render(organization_id, "locale-aware", {}, locale="fr")
    english = await rendering_service.render(organization_id, "locale-aware", {}, locale="en")

    assert french.body == "Bonjour"
    assert english.body == "Hello"


async def test_a_version_body_cannot_be_shadowed_by_a_template_named_after_it(
    rendering_service: RenderingService,
    published: Any,
    make_template: Any,
    organization_id: uuid.UUID,
) -> None:
    """The revision's own body is registered under a namespaced key
    precisely so a template row cannot take its place."""
    _prompt, version = published
    await make_template(f"__version__{version.id}", "HIJACKED")

    result = await rendering_service.render(organization_id, "greeting", {"name": "Ada"})
    assert result.body == "Hello Ada"


# ---------------------------------------------------------------------------
# preview() -- the authoring path
# ---------------------------------------------------------------------------


async def test_preview_renders_a_draft_that_render_would_refuse(
    rendering_service: RenderingService,
    make_prompt: MakePromptFn,
    declare_variable: Any,
    organization_id: uuid.UUID,
) -> None:
    """Someone editing a draft has to see it rendered before it can
    possibly be approved."""
    _prompt, version = await make_prompt("unpublished")
    await declare_variable(version, "name")

    result = await rendering_service.preview(version, {"name": "Ada"})

    assert result.body == "Hello Ada"
    with pytest.raises(ConflictError):
        await rendering_service.render(organization_id, "unpublished", {"name": "Ada"})


async def test_preview_leaves_the_prompt_unset(
    rendering_service: RenderingService, make_prompt: MakePromptFn, declare_variable: Any
) -> None:
    """A preview renders a revision directly and never resolves the
    owning prompt, so claiming one would be a lie."""
    _prompt, version = await make_prompt("previewed")
    await declare_variable(version, "name")

    assert (await rendering_service.preview(version)).prompt is None


async def test_preview_still_fails_on_a_variable_that_was_never_declared(
    rendering_service: RenderingService, make_prompt: MakePromptFn
) -> None:
    """Preview's placeholder substitution walks the *declared* specs, so
    an undeclared variable still fails -- which is right: that is exactly
    what the security scanner flags as HIGH, because every production
    render of it would fail under ``StrictUndefined``. Papering over it
    here would hide the problem until publish."""
    _prompt, version = await make_prompt("undeclared", body="Hello {{ nobody_declared_me }}")

    with pytest.raises(ValidationError, match="nobody_declared_me"):
        await rendering_service.preview(version)


async def test_preview_substitutes_a_placeholder_for_an_unsupplied_variable(
    rendering_service: RenderingService, make_prompt: MakePromptFn, declare_variable: Any
) -> None:
    """Refusing to render because a runtime value is absent would make
    preview useless during authoring -- exactly when it is needed."""
    _prompt, version = await make_prompt("shapely")
    await declare_variable(version, "name")

    result = await rendering_service.preview(version, {})

    assert result.body == "Hello <name>"
    assert result.warnings


async def test_preview_never_reads_a_real_secret_out_of_the_vault(
    rendering_service: RenderingService, make_prompt: MakePromptFn, declare_variable: Any
) -> None:
    """A preview is an authoring convenience. If it resolved secrets for
    real, anyone who could author a draft could read the vault by
    rendering ``{{ api_key }}``."""
    _prompt, version = await make_prompt("peeking", body="Key: {{ api_key }}")
    await declare_variable(
        version,
        "api_key",
        kind=VariableKind.SECRET_REFERENCE,
        secret_reference="prod/openai",
        is_masked=True,
    )

    result = await rendering_service.preview(version)

    assert result.body == f"Key: {REDACTION_PLACEHOLDER}"
    assert result.masked_body == result.body


async def test_preview_masked_and_real_bodies_are_the_same(
    rendering_service: RenderingService, make_prompt: MakePromptFn, declare_variable: Any
) -> None:
    """Nothing sensitive was resolved, so there is nothing to mask -- and
    a preview is never persisted as an execution record anyway."""
    _prompt, version = await make_prompt("mirrored")
    await declare_variable(version, "name", is_masked=True)

    result = await rendering_service.preview(version, {"name": "Ada"})
    assert result.body == result.masked_body


async def test_preview_refuses_a_body_it_cannot_parse(
    rendering_service: RenderingService, make_prompt: MakePromptFn, versions_repo: Any
) -> None:
    _prompt, version = await make_prompt("unparseable")
    version.body = "{% if %}"
    await versions_repo.update(version)

    with pytest.raises(ValidationError, match="could not be previewed"):
        await rendering_service.preview(version)


async def test_preview_walks_template_inheritance_too(
    rendering_service: RenderingService,
    versions_repo: PromptVersionRepository,
    make_prompt: MakePromptFn,
    make_template: Any,
) -> None:
    """Otherwise a draft extending a template would preview as an error
    the author could not act on."""
    parent = await make_template("draft-layout", "[{% block content %}{% endblock %}]")

    _prompt, version = await make_prompt(
        "draft-nested", body='{% extends "draft-layout" %}{% block content %}Hi{% endblock %}'
    )
    version.template_id = parent.id
    await versions_repo.update(version)

    assert (await rendering_service.preview(version)).body == "[Hi]"


async def test_preview_reports_a_supplied_value_over_the_placeholder(
    rendering_service: RenderingService, make_prompt: MakePromptFn, declare_variable: Any
) -> None:
    _prompt, version = await make_prompt("partly", body="{{ a }}/{{ b }}")
    await declare_variable(version, "a")
    await declare_variable(version, "b")

    result = await rendering_service.preview(version, {"a": "given"})
    assert result.body == "given/<b>"


# ---------------------------------------------------------------------------
# declared_but_unused
# ---------------------------------------------------------------------------


def _spec(name: str) -> resolution.VariableSpec:
    return resolution.VariableSpec(name=name)


def test_declared_but_unused_finds_a_variable_the_body_never_mentions() -> None:
    """The usual cause is a rename that updated the template and not the
    declaration."""
    assert declared_but_unused("Hello {{ name }}", [_spec("name"), _spec("nickname")]) == (
        "nickname",
    )


def test_declared_but_unused_is_empty_when_every_variable_is_used() -> None:
    assert declared_but_unused("{{ a }} {{ b }}", [_spec("a"), _spec("b")]) == ()


def test_declared_but_unused_matches_case_insensitively() -> None:
    """A declaration differing from the template only in case is a
    rename that half-landed, not an unused variable."""
    assert declared_but_unused("Hello {{ Name }}", [_spec("name")]) == ()


def test_declared_but_unused_returns_names_sorted() -> None:
    """Stable output, so a caller rendering the list does not see it
    reorder between runs."""
    assert declared_but_unused(
        "nothing here", [_spec("zebra"), _spec("apple"), _spec("mango")]
    ) == ("apple", "mango", "zebra")


def test_declared_but_unused_handles_a_body_with_no_variables_at_all() -> None:
    assert declared_but_unused("static text", [_spec("unused")]) == ("unused",)


def test_declared_but_unused_ignores_a_variable_used_only_inside_a_conditional() -> None:
    """Jinja2's own undeclared-variable analysis walks conditional
    branches, so a variable used only in an ``{% if %}`` still counts."""
    assert declared_but_unused("{% if flag %}{{ inner }}{% endif %}", [_spec("inner")]) == ()
