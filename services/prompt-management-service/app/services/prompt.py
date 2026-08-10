"""Prompt lifecycle (docs/061 "PROMPT LIFECYCLE", "VERSION MANAGEMENT").

Draft, Review, Approval, Published, Deprecated, Archived, plus the
Rollback, Clone, and Fork transitions.

**The invariant this whole service protects: published text is
immutable.** Every edit creates a new :class:`~app.models.prompt
.PromptVersion`; nothing ever rewrites a revision that reached
``PUBLISHED``. That is what makes "this is the wording that was
approved" true a year later, and it is why :meth:`PromptService.rollback`
moves a pointer rather than restoring text.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from shared_core.exceptions.conflict import ConflictError
from shared_core.exceptions.validation import ValidationError

from app.events.prompt_events import (
    PromptCreatedEvent,
    PromptDeprecatedEvent,
    PromptPublishedEvent,
    PromptUpdatedEvent,
)
from app.models.analytics import PromptAudit
from app.models.enums import (
    AuditAction,
    PromptCategory,
    PromptLifecycleStatus,
    PromptType,
    PromptVersionStatus,
    SharingScope,
    TemplateFormat,
    VersionBump,
)
from app.models.prompt import Prompt, PromptVersion
from app.models.template import PromptVariable
from app.optimization.tokens import estimate_tokens
from app.repositories.analytics import PromptAuditRepository
from app.repositories.prompt import PromptRepository, PromptVersionRepository
from app.repositories.template import PromptVariableRepository
from app.templating.renderer import validate_syntax
from app.types import EventPublisher
from app.versioning import semver

_SOURCE_SERVICE = "prompt-management-service"


class PromptService:
    """Registers prompts and moves them through their own lifecycle."""

    def __init__(
        self,
        prompts: PromptRepository,
        versions: PromptVersionRepository,
        audit: PromptAuditRepository,
        *,
        publish_event: EventPublisher,
        variables: PromptVariableRepository | None = None,
    ) -> None:
        self._prompts = prompts
        self._versions = versions
        self._audit = audit
        self._publish_event = publish_event
        self._variables = variables

    async def create(
        self,
        *,
        organization_id: UUID,
        slug: str,
        name: str,
        prompt_type: PromptType,
        body: str,
        description: str | None = None,
        category: PromptCategory = PromptCategory.CUSTOM,
        sharing_scope: SharingScope = SharingScope.PRIVATE,
        template_format: TemplateFormat = TemplateFormat.PLAIN_TEXT,
        owner_id: str | None = None,
        tags: list[str] | None = None,
        created_by: str | None = None,
    ) -> tuple[Prompt, PromptVersion]:
        """Register a prompt and its own first draft revision together.

        A prompt with no revision has no text and cannot be rendered,
        so there is no useful intermediate state where one exists
        without the other.

        Raises:
            ConflictError: If *slug* is already registered here.
            ValidationError: If *body* is not a valid template.
        """
        if await self._prompts.get_by_slug(organization_id, slug) is not None:
            raise ConflictError(f"Prompt slug {slug!r} is already registered in this organization.")
        self._require_valid_template(body)

        prompt = await self._prompts.create(
            Prompt(
                organization_id=organization_id,
                slug=slug,
                name=name,
                description=description,
                prompt_type=prompt_type,
                category=category,
                status=PromptLifecycleStatus.DRAFT,
                sharing_scope=sharing_scope,
                owner_id=owner_id,
                tags=list(tags or []),
            )
        )
        version = await self._versions.create(
            PromptVersion(
                organization_id=organization_id,
                prompt_id=prompt.id,
                version_number=semver.INITIAL_VERSION,
                status=PromptVersionStatus.DRAFT,
                body=body,
                template_format=template_format,
                estimated_tokens=estimate_tokens(body),
                authored_by=created_by,
            )
        )
        await self._record(
            prompt,
            action=AuditAction.PROMPT_CREATED,
            actor_id=created_by,
            summary=f"Prompt {slug!r} created at {semver.INITIAL_VERSION}.",
        )
        await self._publish_event(
            PromptCreatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"prompt_id": str(prompt.id), "slug": slug},
            )
        )
        return prompt, version

    async def update(
        self,
        prompt: Prompt,
        *,
        name: str | None = None,
        description: str | None = None,
        category: PromptCategory | None = None,
        sharing_scope: SharingScope | None = None,
        owner_id: str | None = None,
        tags: list[str] | None = None,
        updated_by: str | None = None,
    ) -> Prompt:
        """Update a prompt's own identity fields. ``None`` leaves one alone.

        Deliberately cannot touch the prompt *text* -- that lives in
        immutable revisions and changes only through
        :meth:`add_version`.
        """
        if name is not None:
            prompt.name = name
        if description is not None:
            prompt.description = description
        if category is not None:
            prompt.category = category
        if sharing_scope is not None:
            prompt.sharing_scope = sharing_scope
        if owner_id is not None:
            prompt.owner_id = owner_id
        if tags is not None:
            prompt.tags = list(tags)

        prompt = await self._prompts.update(prompt)
        await self._record(
            prompt,
            action=AuditAction.PROMPT_UPDATED,
            actor_id=updated_by,
            summary=f"Prompt {prompt.slug!r} metadata updated.",
        )
        await self._publish_event(
            PromptUpdatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=prompt.organization_id,
                payload={"prompt_id": str(prompt.id), "slug": prompt.slug},
            )
        )
        return prompt

    async def add_version(
        self,
        prompt: Prompt,
        *,
        body: str,
        component: VersionBump = VersionBump.PATCH,
        changelog: str | None = None,
        template_format: TemplateFormat = TemplateFormat.PLAIN_TEXT,
        model_hint: str | None = None,
        created_by: str | None = None,
        carry_variables: bool = True,
    ) -> PromptVersion:
        """Add a new draft revision, bumping from the highest existing one.

        Bumps from the **highest** version, not the currently-published
        one: after a rollback those differ, and bumping from the live
        pointer would generate a number that already exists.

        Variable declarations are **copied forward** from the revision
        being bumped from, unless *carry_variables* is false. Variables
        are stored per revision so that approving one version is not
        retroactively changed by a later version adding a variable --
        but that would otherwise mean every new revision starts with
        none declared, and a one-word wording tweak would fail to
        render until the author re-declared everything by hand.

        Raises:
            ConflictError: If *prompt* is archived.
            ValidationError: If *body* is not a valid template.
        """
        if prompt.status == PromptLifecycleStatus.ARCHIVED:
            raise ConflictError(
                f"Prompt {prompt.slug!r} is archived; restore it before adding a revision."
            )
        self._require_valid_template(body)

        existing = await self._versions.list_for_prompt(prompt.id)
        highest = (
            semver.sort_versions([row.version_number for row in existing])[-1] if existing else None
        )
        source = next((row for row in existing if row.version_number == highest), None)
        version = await self._versions.create(
            PromptVersion(
                organization_id=prompt.organization_id,
                prompt_id=prompt.id,
                version_number=semver.next_version(highest, component),
                status=PromptVersionStatus.DRAFT,
                body=body,
                template_format=template_format,
                changelog=changelog,
                model_hint=model_hint,
                estimated_tokens=estimate_tokens(body),
                authored_by=created_by,
            )
        )
        if carry_variables and source is not None:
            await self._copy_variables(source.id, version)

        await self._record(
            prompt,
            action=AuditAction.VERSION_CREATED,
            actor_id=created_by,
            summary=f"Prompt {prompt.slug!r} drafted {version.version_number}.",
        )
        await self._publish_event(
            PromptUpdatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=prompt.organization_id,
                payload={
                    "prompt_id": str(prompt.id),
                    "version_number": version.version_number,
                },
            )
        )
        return version

    async def publish(
        self, prompt: Prompt, version: PromptVersion, *, published_by: str | None = None
    ) -> Prompt:
        """Make *version* the live revision of *prompt*.

        Demotes whatever was live first, so exactly one revision is
        ever ``is_current``.

        Raises:
            ConflictError: If *version* does not belong to *prompt*, or
                has already been rolled back.
        """
        self._require_owned(prompt, version)
        if version.status == PromptVersionStatus.ROLLED_BACK:
            raise ConflictError(
                f"Version {version.version_number} was rolled back; draft a new revision instead."
            )

        await self._versions.clear_current(prompt.id)
        version.status = PromptVersionStatus.PUBLISHED
        version.is_current = True
        version.published_at = datetime.now(UTC)
        version.published_by = published_by
        await self._versions.update(version)

        prompt.status = PromptLifecycleStatus.PUBLISHED
        prompt.current_version_number = version.version_number
        prompt = await self._prompts.update(prompt)

        await self._record(
            prompt,
            action=AuditAction.PUBLISHED,
            actor_id=published_by,
            summary=f"Prompt {prompt.slug!r} published {version.version_number}.",
        )
        await self._publish_event(
            PromptPublishedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=prompt.organization_id,
                payload={
                    "prompt_id": str(prompt.id),
                    "slug": prompt.slug,
                    "version_number": version.version_number,
                },
            )
        )
        return prompt

    async def rollback(
        self, prompt: Prompt, *, to_version_number: str, rolled_back_by: str | None = None
    ) -> Prompt:
        """Point *prompt* back at an earlier revision.

        Moves the live pointer; it does not restore or rewrite text.
        The revision being rolled *away from* is marked
        ``ROLLED_BACK`` so its history records that it was withdrawn
        rather than merely superseded by something newer.

        Raises:
            ConflictError: If the target revision does not exist, was
                never published, or is already live.
        """
        target = await self._versions.get_by_number(prompt.id, to_version_number)
        if target is None:
            raise ConflictError(f"Prompt {prompt.slug!r} has no version {to_version_number}.")
        if target.published_at is None:
            raise ConflictError(
                f"Version {to_version_number} was never published, so there is nothing "
                "to roll back to."
            )
        if target.is_current:
            raise ConflictError(f"Version {to_version_number} is already the live revision.")

        withdrawn = await self._versions.get_current(prompt.id)
        await self._versions.clear_current(prompt.id)
        if withdrawn is not None:
            withdrawn.status = PromptVersionStatus.ROLLED_BACK
            await self._versions.update(withdrawn)

        target.status = PromptVersionStatus.PUBLISHED
        target.is_current = True
        await self._versions.update(target)

        prompt.status = PromptLifecycleStatus.PUBLISHED
        prompt.current_version_number = target.version_number
        prompt = await self._prompts.update(prompt)

        await self._record(
            prompt,
            action=AuditAction.ROLLED_BACK,
            actor_id=rolled_back_by,
            summary=(
                f"Prompt {prompt.slug!r} rolled back to {to_version_number}"
                + (f" from {withdrawn.version_number}." if withdrawn else ".")
            ),
        )
        await self._publish_event(
            PromptPublishedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=prompt.organization_id,
                payload={
                    "prompt_id": str(prompt.id),
                    "slug": prompt.slug,
                    "version_number": target.version_number,
                    "rolled_back": True,
                },
            )
        )
        return prompt

    async def submit_for_review(self, prompt: Prompt) -> Prompt:
        """Move a draft into review.

        Raises:
            ConflictError: If *prompt* is not currently a draft.
        """
        if prompt.status != PromptLifecycleStatus.DRAFT:
            raise ConflictError(
                f"Prompt {prompt.slug!r} is {prompt.status!s}, not draft; cannot submit for review."
            )
        prompt.status = PromptLifecycleStatus.REVIEW
        return await self._prompts.update(prompt)

    async def deprecate(self, prompt: Prompt, *, deprecated_by: str | None = None) -> Prompt:
        """Mark a prompt deprecated.

        It stays resolvable so existing callers keep working -- a
        deprecated prompt that stopped rendering would break production
        rather than warn about it.

        Raises:
            ConflictError: If *prompt* is archived.
        """
        if prompt.status == PromptLifecycleStatus.ARCHIVED:
            raise ConflictError(f"Prompt {prompt.slug!r} is already archived.")
        prompt.status = PromptLifecycleStatus.DEPRECATED
        prompt = await self._prompts.update(prompt)
        await self._record(
            prompt,
            action=AuditAction.DEPRECATED,
            actor_id=deprecated_by,
            summary=f"Prompt {prompt.slug!r} deprecated.",
        )
        await self._publish_event(
            PromptDeprecatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=prompt.organization_id,
                payload={"prompt_id": str(prompt.id), "slug": prompt.slug},
            )
        )
        return prompt

    async def archive(self, prompt: Prompt, *, archived_by: str | None = None) -> Prompt:
        """Archive a prompt and soft-delete it.

        Terminal: an archived prompt no longer resolves and cannot gain
        new revisions.
        """
        prompt.status = PromptLifecycleStatus.ARCHIVED
        prompt = await self._prompts.update(prompt)
        await self._record(
            prompt,
            action=AuditAction.ARCHIVED,
            actor_id=archived_by,
            summary=f"Prompt {prompt.slug!r} archived.",
        )
        await self._prompts.delete(prompt.id)
        return prompt

    async def clone(
        self,
        prompt: Prompt,
        *,
        new_slug: str,
        target_organization_id: UUID | None = None,
        cloned_by: str | None = None,
    ) -> tuple[Prompt, PromptVersion]:
        """Copy a prompt's live text into a new, independently owned prompt.

        Records ``forked_from_prompt_id`` so provenance survives, but
        the copy is otherwise unlinked: it starts as a fresh draft at
        ``1.0.0`` and its later edits never touch the original.

        Raises:
            ConflictError: If *new_slug* is taken in the target
                organization, or *prompt* has no revision to copy.
        """
        organization_id = target_organization_id or prompt.organization_id
        if await self._prompts.get_by_slug(organization_id, new_slug) is not None:
            raise ConflictError(
                f"Prompt slug {new_slug!r} is already registered in that organization."
            )
        source = await self._versions.get_current(prompt.id)
        if source is None:
            versions = await self._versions.list_for_prompt(prompt.id)
            if not versions:
                raise ConflictError(f"Prompt {prompt.slug!r} has no revision to clone.")
            source = versions[0]

        clone, version = await self.create(
            organization_id=organization_id,
            slug=new_slug,
            name=f"{prompt.name} (copy)",
            prompt_type=prompt.prompt_type,
            body=source.body,
            description=prompt.description,
            category=prompt.category,
            template_format=source.template_format,
            owner_id=cloned_by or prompt.owner_id,
            tags=list(prompt.tags),
            created_by=cloned_by,
        )
        clone.forked_from_prompt_id = prompt.id
        clone = await self._prompts.update(clone)
        await self._record(
            clone,
            action=AuditAction.CLONED,
            actor_id=cloned_by,
            summary=f"Prompt {new_slug!r} cloned from {prompt.slug!r}.",
        )
        return clone, version

    async def mark_reviewed(self, prompt: Prompt) -> Prompt:
        """Stamp *prompt* as reviewed now ("GOVERNANCE": Review Cycle)."""
        prompt.last_reviewed_at = datetime.now(UTC)
        return await self._prompts.update(prompt)

    async def _copy_variables(self, from_version_id: UUID, to_version: PromptVersion) -> None:
        """Copy one revision's variable declarations onto a new one.

        Copies rather than shares rows, so editing the new revision's
        declarations can never reach back and alter what an already-
        approved revision requires -- which is the entire reason
        variables are per-revision in the first place.
        """
        if self._variables is None:
            return
        for row in await self._variables.list_for_version(from_version_id):
            await self._variables.create(
                PromptVariable(
                    organization_id=to_version.organization_id,
                    prompt_version_id=to_version.id,
                    name=row.name,
                    description=row.description,
                    kind=row.kind,
                    value_type=row.value_type,
                    default_value=row.default_value,
                    required=row.required,
                    secret_reference=row.secret_reference,
                    computed_expression=row.computed_expression,
                    validation_rules=dict(row.validation_rules or {}),
                    is_masked=row.is_masked,
                )
            )

    @staticmethod
    def _require_valid_template(body: str) -> None:
        """Refuse a body Jinja2 cannot parse.

        Checked at draft time rather than at render time: a template
        that cannot compile is broken for every future render, and
        finding that out when a production caller resolves the prompt
        is far too late.

        Raises:
            ValidationError: If *body* is not a valid template.
        """
        error = validate_syntax(body)
        if error is not None:
            raise ValidationError(f"The prompt body is not a valid template. {error}")

    @staticmethod
    def _require_owned(prompt: Prompt, version: PromptVersion) -> None:
        """Refuse a revision belonging to a different prompt.

        Raises:
            ConflictError: If *version* is not *prompt*'s own.
        """
        if version.prompt_id != prompt.id:
            raise ConflictError(
                f"Version {version.version_number} does not belong to prompt {prompt.slug!r}."
            )

    async def _record(
        self, prompt: Prompt, *, action: AuditAction, summary: str, actor_id: str | None
    ) -> None:
        """Append one audit row for a lifecycle transition."""
        await self._audit.create(
            PromptAudit(
                organization_id=prompt.organization_id,
                action=action,
                entity_type="prompt",
                entity_id=prompt.id,
                entity_reference=prompt.slug,
                actor_id=actor_id,
                occurred_at=datetime.now(UTC),
                summary=summary,
            )
        )


__all__ = ["PromptService"]
