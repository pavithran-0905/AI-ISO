"""Prompt retrieval and rendering -- the read path every other AI-IOS
service actually calls (docs/061 OBJECTIVE: "Every AI-generated
interaction SHALL retrieve prompts through this service").

Composes the templating renderer, the variable resolver, and the
database into one operation: resolve a prompt by slug, pull its live
revision, gather the templates that revision can reach, resolve and
validate its declared variables, and render.

**Only ``PUBLISHED`` and ``DEPRECATED`` prompts resolve.** A draft has
not been reviewed, approved, or scanned -- serving one to production
would let unreviewed text reach a model, which is precisely what this
service exists to prevent. Deprecated still resolves so existing
callers keep working while they migrate.

**The rendered prompt returned to a caller is the real one; the
rendered prompt *recorded* is masked.** Those must differ: a secret
has to reach the model to be useful, and must never reach the
execution history.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from shared_core.exceptions.conflict import ConflictError
from shared_core.exceptions.not_found import NotFoundError
from shared_core.exceptions.validation import ValidationError

from app.models.enums import PromptLifecycleStatus
from app.models.prompt import Prompt, PromptVersion
from app.models.template import PromptTemplate
from app.repositories.prompt import PromptRepository, PromptVersionRepository
from app.repositories.template import PromptTemplateRepository, PromptVariableRepository
from app.security.redaction import REDACTION_PLACEHOLDER
from app.templating import renderer
from app.variables import resolution

_RESOLVABLE_STATUSES = frozenset(
    {PromptLifecycleStatus.PUBLISHED, PromptLifecycleStatus.DEPRECATED}
)
"""Deprecated still resolves. A deprecated prompt that stopped
rendering would break production rather than warn about it -- the
whole point of deprecation is a migration window."""


@dataclass(slots=True)
class RenderedResult:
    """One rendered prompt, plus the masked copy safe to persist."""

    prompt: Prompt | None
    """``None`` for a :meth:`RenderingService.preview`, which renders a
    revision directly and never needs to resolve the owning prompt."""
    version: PromptVersion
    body: str
    """The real rendered text, including any resolved secret."""
    masked_body: str
    """The same text with every masked value replaced. This is what
    goes into ``prompt_executions.rendered_prompt``."""
    variables_used: tuple[str, ...] = ()
    masked_names: frozenset[str] = frozenset()
    estimated_tokens: int = 0
    warnings: list[str] = field(default_factory=list)


class RenderingService:
    """Resolves and renders prompts for the services that consume them."""

    def __init__(
        self,
        prompts: PromptRepository,
        versions: PromptVersionRepository,
        templates: PromptTemplateRepository,
        variables: PromptVariableRepository,
        *,
        max_depth: int = renderer.DEFAULT_MAX_DEPTH,
        max_length: int = renderer.DEFAULT_MAX_RENDERED_LENGTH,
    ) -> None:
        self._prompts = prompts
        self._versions = versions
        self._templates = templates
        self._variables = variables
        self._max_depth = max_depth
        self._max_length = max_length

    async def resolve(
        self, organization_id: UUID, slug: str, *, version_number: str | None = None
    ) -> tuple[Prompt, PromptVersion]:
        """Resolve *slug* to its live revision, or to a pinned one.

        Pinning by *version_number* bypasses the published-status check
        on the *prompt* but not on the revision: a caller that pins is
        explicitly asking for a specific historical revision, which is
        a legitimate reproducibility need, but it still may not reach
        an unpublished draft.

        Raises:
            NotFoundError: If no such prompt or revision exists here.
            ConflictError: If the prompt is not in a resolvable state,
                or the pinned revision was never published.
        """
        prompt = await self._prompts.get_by_slug(organization_id, slug)
        if prompt is None:
            raise NotFoundError(
                f"No prompt with slug {slug!r} in organization {organization_id!s}."
            )

        if version_number is not None:
            version = await self._versions.get_by_number(prompt.id, version_number)
            if version is None:
                raise NotFoundError(f"Prompt {slug!r} has no version {version_number}.")
            if version.published_at is None:
                raise ConflictError(
                    f"Version {version_number} of {slug!r} was never published and "
                    "cannot be resolved."
                )
            return prompt, version

        if prompt.status not in _RESOLVABLE_STATUSES:
            raise ConflictError(
                f"Prompt {slug!r} is {prompt.status!s}; only published or deprecated "
                "prompts can be resolved."
            )
        version = await self._versions.get_current(prompt.id)
        if version is None:
            raise ConflictError(f"Prompt {slug!r} is {prompt.status!s} but has no live revision.")
        return prompt, version

    async def render(
        self,
        organization_id: UUID,
        slug: str,
        variables: dict[str, Any] | None = None,
        *,
        version_number: str | None = None,
        secret_resolver: resolution.SecretResolver | None = None,
        locale: str = "en",
    ) -> RenderedResult:
        """Resolve and render one prompt.

        Raises:
            NotFoundError: If the prompt or pinned revision is absent.
            ConflictError: If the prompt is not resolvable.
            ValidationError: If a declared variable fails resolution or
                validation, or the template cannot render.
        """
        prompt, version = await self.resolve(organization_id, slug, version_number=version_number)
        specs = await self._variable_specs(version.id)
        resolved = resolution.resolve(specs, dict(variables or {}), secret_resolver=secret_resolver)
        if not resolved.ok:
            raise ValidationError(
                f"Prompt {slug!r} could not be rendered: {'; '.join(resolved.errors)}"
            )

        bundle = await self._bundle_for(version, organization_id, locale=locale)
        try:
            rendered = renderer.render(
                bundle,
                _version_slug(version),
                resolved.values,
                max_depth=self._max_depth,
                max_length=self._max_length,
            )
        except renderer.TemplateRenderError as exc:
            raise ValidationError(f"Prompt {slug!r} could not be rendered: {exc}") from exc

        masked_values = {
            name: (REDACTION_PLACEHOLDER if name in resolved.masked_names else value)
            for name, value in resolved.values.items()
        }
        masked = renderer.render(
            bundle,
            _version_slug(version),
            masked_values,
            max_depth=self._max_depth,
            max_length=self._max_length,
        )

        return RenderedResult(
            prompt=prompt,
            version=version,
            body=rendered.body,
            masked_body=masked.body,
            variables_used=rendered.variables_used,
            masked_names=frozenset(resolved.masked_names),
            estimated_tokens=version.estimated_tokens,
        )

    async def preview(
        self,
        version: PromptVersion,
        variables: dict[str, Any] | None = None,
        *,
        locale: str = "en",
    ) -> RenderedResult:
        """Render an arbitrary revision, published or not.

        The authoring path: someone editing a draft needs to see it
        rendered before it can possibly be approved. Distinct from
        :meth:`render`, which is the production read path and refuses
        drafts -- keeping them as separate methods is what stops a
        production caller reaching a draft by passing a flag.

        Secret references resolve to the placeholder rather than their
        real values: a preview is an authoring convenience and must not
        become a way to read secrets out of the vault.

        Raises:
            ValidationError: If the template cannot render.
        """
        specs = await self._variable_specs(version.id)
        supplied = dict(variables or {})
        resolved = resolution.resolve(
            specs, supplied, secret_resolver=lambda _ref: REDACTION_PLACEHOLDER
        )

        # A preview tolerates unresolved variables -- the point is to
        # see the shape of the prompt, and refusing to render because a
        # runtime value is absent would make preview useless during
        # authoring, which is exactly when it is needed.
        values = dict(resolved.values)
        for spec in specs:
            values.setdefault(spec.name, f"<{spec.name}>")

        bundle = await self._bundle_for(version, version.organization_id, locale=locale)
        try:
            rendered = renderer.render(
                bundle,
                _version_slug(version),
                values,
                max_depth=self._max_depth,
                max_length=self._max_length,
            )
        except renderer.TemplateRenderError as exc:
            raise ValidationError(f"This revision could not be previewed: {exc}") from exc

        return RenderedResult(
            prompt=None,
            version=version,
            body=rendered.body,
            masked_body=rendered.body,
            variables_used=rendered.variables_used,
            masked_names=frozenset(resolved.masked_names),
            estimated_tokens=version.estimated_tokens,
            warnings=list(resolved.errors),
        )

    async def _variable_specs(self, prompt_version_id: UUID) -> list[resolution.VariableSpec]:
        """Flatten one revision's declared variables into pure specs."""
        rows = await self._variables.list_for_version(prompt_version_id)
        return [
            resolution.VariableSpec(
                name=row.name,
                kind=row.kind,
                value_type=row.value_type,
                default_value=row.default_value,
                required=row.required,
                secret_reference=row.secret_reference,
                computed_expression=row.computed_expression,
                validation_rules=dict(row.validation_rules or {}),
                is_masked=row.is_masked,
            )
            for row in rows
        ]

    async def _bundle_for(
        self, version: PromptVersion, organization_id: UUID, *, locale: str
    ) -> renderer.TemplateBundle:
        """Gather every template this revision's render may reach.

        Resolved up front rather than lazily during the render, so a
        template cannot trigger database queries by name mid-render --
        see :mod:`app.templating.renderer` for the full reasoning.
        """
        bundle = renderer.TemplateBundle()
        parent_slug: str | None = None

        if version.template_id is not None:
            parent = await self._templates.require_in_org(organization_id, version.template_id)
            parent_slug = parent.slug
            await self._add_template(bundle, parent, organization_id, locale=locale, seen=set())

        bundle.add(
            renderer.TemplateSource(
                slug=_version_slug(version), body=version.body, parent_slug=parent_slug
            )
        )
        return bundle

    async def _add_template(
        self,
        bundle: renderer.TemplateBundle,
        template: PromptTemplate,
        organization_id: UUID,
        *,
        locale: str,
        seen: set[str],
    ) -> None:
        """Add *template* and everything it reaches into *bundle*.

        Tracks ``seen`` so a cyclic parent/include chain terminates
        here rather than recursing forever. The renderer refuses the
        cycle too, but a walk that hangs while *gathering* would never
        reach that check.
        """
        if template.slug in seen:
            return
        seen.add(template.slug)

        parent_slug: str | None = None
        if template.parent_template_id is not None:
            parent = await self._templates.require_in_org(
                organization_id, template.parent_template_id
            )
            parent_slug = parent.slug
            await self._add_template(bundle, parent, organization_id, locale=locale, seen=seen)

        included = tuple(template.included_template_slugs or ())
        bundle.add(
            renderer.TemplateSource(
                slug=template.slug,
                body=template.body,
                parent_slug=parent_slug,
                included_slugs=included,
            )
        )
        for slug in included:
            component = await self._templates.get_by_slug_any_locale(
                organization_id, slug, preferred_locale=locale
            )
            if component is None:
                # Left absent deliberately: the renderer reports a
                # missing include with the slug that is missing, which
                # is a far better error than one raised here without
                # the surrounding render context.
                continue
            await self._add_template(bundle, component, organization_id, locale=locale, seen=seen)


def _version_slug(version: PromptVersion) -> str:
    """The loader key one revision's own body is registered under.

    Namespaced by id so it can never collide with a real template slug
    -- a template literally named after a version id would otherwise
    shadow the body being rendered.
    """
    return f"__version__{version.id}"


def declared_but_unused(
    version_body: str, specs: Sequence[resolution.VariableSpec]
) -> tuple[str, ...]:
    """Variables a revision declares but its own template never uses.

    Not an error -- a variable may be declared ahead of the edit that
    will use it -- but worth surfacing, since the usual cause is a
    rename that updated the template and not the declaration.
    """
    used = {name.lower() for name in renderer.declared_variables(version_body)}
    return tuple(sorted(spec.name for spec in specs if spec.name.lower() not in used))


__all__ = ["RenderedResult", "RenderingService", "declared_but_unused"]
