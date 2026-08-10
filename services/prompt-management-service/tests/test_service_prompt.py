"""Prompt lifecycle service tests (:mod:`app.services.prompt`).

Everything runs against real PostgreSQL through the real repositories,
with a real :class:`~tests.conftest.RecordingPublisher`. Nothing is
mocked, and since this service calls no model provider every outcome is
deterministic enough to assert exactly.

**The invariant these tests exist to protect is that published text is
immutable.** ``rollback`` must move a pointer and never restore or
rewrite a body, ``add_version`` must bump from the highest version
rather than the live one, and variable declarations must be copied
forward rather than shared -- each of which is a way the invariant
could quietly stop being true without any single test failing unless it
is asserted directly.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from shared_core.exceptions.conflict import ConflictError
from shared_core.exceptions.validation import ValidationError

from app.models.enums import (
    AuditAction,
    PromptCategory,
    PromptLifecycleStatus,
    PromptType,
    PromptVersionStatus,
    SharingScope,
    TemplateFormat,
    VariableKind,
    VariableType,
    VersionBump,
)
from app.models.prompt import Prompt, PromptVersion
from app.models.template import PromptVariable
from app.optimization.tokens import estimate_tokens
from app.repositories.analytics import PromptAuditRepository
from app.repositories.prompt import PromptRepository, PromptVersionRepository
from app.repositories.template import PromptVariableRepository
from app.services.prompt import PromptService
from tests.conftest import MakePromptFn, MakePublishedFn, RecordingPublisher


async def audit_actions(repo: PromptAuditRepository, organization_id: uuid.UUID) -> list[str]:
    """Every audit action recorded for *organization_id*, newest first."""
    return [str(row.action) for row in await repo.list_for_org(organization_id)]


async def declare(
    repo: PromptVariableRepository, version: PromptVersion, name: str, **overrides: Any
) -> PromptVariable:
    """Declare one variable on *version*."""
    fields: dict[str, Any] = {
        "organization_id": version.organization_id,
        "prompt_version_id": version.id,
        "name": name,
    }
    fields.update(overrides)
    return await repo.create(PromptVariable(**fields))


# ---- create ------------------------------------------------------------------


async def test_create_registers_the_prompt_and_its_own_first_draft_together(
    prompt_service: PromptService,
    versions_repo: PromptVersionRepository,
    audit_repo: PromptAuditRepository,
    publisher: RecordingPublisher,
    organization_id: uuid.UUID,
) -> None:
    prompt, version = await prompt_service.create(
        organization_id=organization_id,
        slug="greeting",
        name="Greeting",
        prompt_type=PromptType.SYSTEM,
        body="Hello {{ name }}",
        created_by="author-1",
    )

    assert prompt.slug == "greeting"
    assert prompt.status == PromptLifecycleStatus.DRAFT
    assert prompt.current_version_number is None
    assert prompt.execution_count == 0

    assert version.prompt_id == prompt.id
    assert version.version_number == "1.0.0"
    assert version.status == PromptVersionStatus.DRAFT
    assert version.is_current is False
    assert version.published_at is None
    assert version.created_by == "author-1"
    assert version.estimated_tokens == estimate_tokens("Hello {{ name }}")

    assert await versions_repo.get_current(prompt.id) is None
    assert publisher.names == ["PromptCreated"]
    assert publisher.events[0].payload == {"prompt_id": str(prompt.id), "slug": "greeting"}
    assert await audit_actions(audit_repo, organization_id) == [str(AuditAction.PROMPT_CREATED)]


async def test_create_stores_every_identity_field_it_is_given(
    prompt_service: PromptService, organization_id: uuid.UUID
) -> None:
    prompt, version = await prompt_service.create(
        organization_id=organization_id,
        slug="compliance-check",
        name="Compliance Check",
        prompt_type=PromptType.VALIDATION,
        body="# Check {{ target }}",
        description="Validates a change request.",
        category=PromptCategory.COMPLIANCE,
        sharing_scope=SharingScope.ORGANIZATION,
        template_format=TemplateFormat.MARKDOWN,
        owner_id="owner-7",
        tags=["compliance", "change"],
    )

    assert prompt.prompt_type == PromptType.VALIDATION
    assert prompt.category == PromptCategory.COMPLIANCE
    assert prompt.sharing_scope == SharingScope.ORGANIZATION
    assert prompt.description == "Validates a change request."
    assert prompt.owner_id == "owner-7"
    assert prompt.tags == ["compliance", "change"]
    assert version.template_format == TemplateFormat.MARKDOWN


async def test_create_refuses_a_slug_already_registered_in_the_same_organization(
    prompt_service: PromptService,
    prompts_repo: PromptRepository,
    publisher: RecordingPublisher,
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
) -> None:
    await make_prompt("greeting")

    with pytest.raises(ConflictError, match="already registered"):
        await prompt_service.create(
            organization_id=organization_id,
            slug="greeting",
            name="Another Greeting",
            prompt_type=PromptType.USER,
            body="Hi",
        )

    assert publisher.names == ["PromptCreated"]
    assert len(await prompts_repo.list_for_org(organization_id)) == 1


async def test_the_same_slug_is_free_in_a_different_organization(
    prompt_service: PromptService, make_prompt: MakePromptFn
) -> None:
    prompt, _version = await make_prompt("greeting")
    other_org = uuid.uuid4()

    clone, _clone_version = await prompt_service.create(
        organization_id=other_org,
        slug="greeting",
        name="Greeting",
        prompt_type=PromptType.SYSTEM,
        body="Hello",
    )
    assert clone.id != prompt.id
    assert clone.organization_id == other_org


async def test_create_refuses_an_invalid_template_at_draft_time(
    prompt_service: PromptService,
    prompts_repo: PromptRepository,
    publisher: RecordingPublisher,
    organization_id: uuid.UUID,
) -> None:
    """Checked when the draft is saved, not when a caller renders it.

    A body Jinja2 cannot compile is broken for every future render, and
    nothing at all should be persisted for it.
    """
    with pytest.raises(ValidationError, match="not a valid template"):
        await prompt_service.create(
            organization_id=organization_id,
            slug="broken",
            name="Broken",
            prompt_type=PromptType.SYSTEM,
            body="Hello {{ name",
        )

    assert await prompts_repo.get_by_slug(organization_id, "broken") is None
    assert publisher.names == []


# ---- update ------------------------------------------------------------------


async def test_update_changes_only_the_fields_supplied(
    prompt_service: PromptService,
    audit_repo: PromptAuditRepository,
    publisher: RecordingPublisher,
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
) -> None:
    prompt, _version = await make_prompt(
        "greeting", description="Original", tags=["a"], owner_id="owner-1"
    )

    updated = await prompt_service.update(
        prompt,
        name="Renamed",
        category=PromptCategory.AI_ASSISTANT,
        tags=["b", "c"],
        updated_by="editor-1",
    )

    assert updated.name == "Renamed"
    assert updated.category == PromptCategory.AI_ASSISTANT
    assert updated.tags == ["b", "c"]
    assert updated.description == "Original"
    assert updated.owner_id == "owner-1"
    assert updated.sharing_scope == SharingScope.PRIVATE

    assert publisher.names == ["PromptCreated", "PromptUpdated"]
    assert publisher.events[-1].payload == {"prompt_id": str(prompt.id), "slug": "greeting"}
    assert str(AuditAction.PROMPT_UPDATED) in await audit_actions(audit_repo, organization_id)


async def test_update_sets_description_owner_and_sharing_scope(
    prompt_service: PromptService, make_prompt: MakePromptFn
) -> None:
    prompt, _version = await make_prompt("greeting")

    updated = await prompt_service.update(
        prompt,
        description="Now documented",
        sharing_scope=SharingScope.SHARED,
        owner_id="owner-9",
    )

    assert updated.description == "Now documented"
    assert updated.sharing_scope == SharingScope.SHARED
    assert updated.owner_id == "owner-9"


async def test_update_has_no_way_to_touch_the_prompt_text(
    prompt_service: PromptService, make_prompt: MakePromptFn
) -> None:
    """Text lives in immutable revisions, so ``update`` deliberately has
    no parameter for it -- passing one is a ``TypeError``, not a silent
    no-op."""
    prompt, version = await make_prompt("greeting")

    with pytest.raises(TypeError):
        await prompt_service.update(prompt, body="Rewritten")

    assert version.body == "Hello {{ name }}"


# ---- add_version -------------------------------------------------------------


async def test_add_version_bumps_from_the_highest_version_not_the_live_pointer(
    prompt_service: PromptService,
    versions_repo: PromptVersionRepository,
    make_published: MakePublishedFn,
) -> None:
    """After a rollback the live pointer and the highest version differ.

    Bumping from the live pointer would generate ``1.0.1`` a second
    time and collide with a version that already exists.
    """
    prompt, first = await make_published("greeting")
    second = await prompt_service.add_version(
        prompt, body="Hi {{ name }}", component=VersionBump.MINOR
    )
    prompt = await prompt_service.publish(prompt, second)
    prompt = await prompt_service.rollback(prompt, to_version_number=first.version_number)

    assert prompt.current_version_number == "1.0.0"
    highest = await versions_repo.get_by_number(prompt.id, "1.1.0")
    assert highest is not None

    third = await prompt_service.add_version(prompt, body="Hey {{ name }}")
    assert third.version_number == "1.1.1"
    assert third.status == PromptVersionStatus.DRAFT
    assert {row.version_number for row in await versions_repo.list_for_prompt(prompt.id)} == {
        "1.0.0",
        "1.1.0",
        "1.1.1",
    }


@pytest.mark.parametrize(
    ("component", "expected"),
    [(VersionBump.PATCH, "1.0.1"), (VersionBump.MINOR, "1.1.0"), (VersionBump.MAJOR, "2.0.0")],
)
async def test_add_version_advances_the_requested_component(
    prompt_service: PromptService,
    make_prompt: MakePromptFn,
    component: VersionBump,
    expected: str,
) -> None:
    prompt, _version = await make_prompt("greeting")
    added = await prompt_service.add_version(prompt, body="Hi {{ name }}", component=component)
    assert added.version_number == expected


async def test_add_version_records_its_own_metadata_and_announces_the_draft(
    prompt_service: PromptService,
    audit_repo: PromptAuditRepository,
    publisher: RecordingPublisher,
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
) -> None:
    prompt, _version = await make_prompt("greeting")

    added = await prompt_service.add_version(
        prompt,
        body="Hi {{ name }}, welcome.",
        changelog="Warmer wording.",
        template_format=TemplateFormat.MARKDOWN,
        model_hint="claude-sonnet",
        created_by="author-2",
    )

    assert added.changelog == "Warmer wording."
    assert added.template_format == TemplateFormat.MARKDOWN
    assert added.model_hint == "claude-sonnet"
    assert added.created_by == "author-2"
    assert added.estimated_tokens == estimate_tokens("Hi {{ name }}, welcome.")
    assert added.is_current is False

    assert publisher.names == ["PromptCreated", "PromptUpdated"]
    assert publisher.events[-1].payload == {
        "prompt_id": str(prompt.id),
        "version_number": "1.0.1",
    }
    assert str(AuditAction.VERSION_CREATED) in await audit_actions(audit_repo, organization_id)


async def test_add_version_copies_variable_declarations_forward_as_independent_rows(
    prompt_service: PromptService,
    variables_repo: PromptVariableRepository,
    make_prompt: MakePromptFn,
) -> None:
    """Copied, never shared.

    Variables are per revision precisely so approving one version is not
    retroactively changed by a later one -- which only holds if editing
    the new revision's declarations cannot reach back to the old rows.
    """
    prompt, first = await make_prompt("greeting")
    original = await declare(
        variables_repo,
        first,
        "name",
        description="Who to greet",
        kind=VariableKind.RUNTIME,
        value_type=VariableType.STRING,
        default_value="world",
        required=False,
        validation_rules={"min_length": 2},
        is_masked=True,
    )

    second = await prompt_service.add_version(prompt, body="Hi {{ name }}")
    copied_rows = await variables_repo.list_for_version(second.id)
    assert len(copied_rows) == 1
    copied = copied_rows[0]

    assert copied.id != original.id
    assert copied.prompt_version_id == second.id
    assert copied.name == "name"
    assert copied.description == "Who to greet"
    assert copied.kind == VariableKind.RUNTIME
    assert copied.value_type == VariableType.STRING
    assert copied.default_value == "world"
    assert copied.required is False
    assert copied.validation_rules == {"min_length": 2}
    assert copied.is_masked is True

    copied.default_value = "everyone"
    copied.validation_rules = {"min_length": 5}
    await variables_repo.update(copied)

    untouched = await variables_repo.get_by_name(first.id, "name")
    assert untouched is not None
    assert untouched.default_value == "world"
    assert untouched.validation_rules == {"min_length": 2}


async def test_add_version_copies_secret_and_computed_declarations_too(
    prompt_service: PromptService,
    variables_repo: PromptVariableRepository,
    make_prompt: MakePromptFn,
) -> None:
    prompt, first = await make_prompt("greeting")
    await declare(
        variables_repo,
        first,
        "api_key",
        kind=VariableKind.SECRET_REFERENCE,
        secret_reference="vault://keys/api",
    )
    await declare(
        variables_repo,
        first,
        "shout",
        kind=VariableKind.COMPUTED,
        computed_expression="name | upper",
    )

    second = await prompt_service.add_version(prompt, body="Hi {{ name }}")
    copied = {row.name: row for row in await variables_repo.list_for_version(second.id)}

    assert set(copied) == {"api_key", "shout"}
    assert copied["api_key"].secret_reference == "vault://keys/api"
    assert copied["shout"].computed_expression == "name | upper"


async def test_carry_variables_false_starts_the_new_revision_with_none_declared(
    prompt_service: PromptService,
    variables_repo: PromptVariableRepository,
    make_prompt: MakePromptFn,
) -> None:
    prompt, first = await make_prompt("greeting")
    await declare(variables_repo, first, "name")

    second = await prompt_service.add_version(prompt, body="Hi {{ name }}", carry_variables=False)

    assert await variables_repo.list_for_version(second.id) == []
    assert len(await variables_repo.list_for_version(first.id)) == 1


async def test_add_version_carries_variables_from_the_highest_revision(
    prompt_service: PromptService,
    variables_repo: PromptVariableRepository,
    make_prompt: MakePromptFn,
) -> None:
    """The source of the copy is the revision being bumped *from*."""
    prompt, first = await make_prompt("greeting")
    await declare(variables_repo, first, "name")

    second = await prompt_service.add_version(prompt, body="Hi {{ name }}")
    await declare(variables_repo, second, "salutation")

    third = await prompt_service.add_version(prompt, body="Hey {{ name }}")
    assert {row.name for row in await variables_repo.list_for_version(third.id)} == {
        "name",
        "salutation",
    }


async def test_a_service_without_a_variable_repository_simply_carries_nothing(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    audit_repo: PromptAuditRepository,
    variables_repo: PromptVariableRepository,
    publisher: RecordingPublisher,
    organization_id: uuid.UUID,
) -> None:
    """``variables`` is optional on the constructor, so the copy is a
    no-op rather than an attribute error when it is absent."""
    service = PromptService(prompts_repo, versions_repo, audit_repo, publish_event=publisher)
    prompt, first = await service.create(
        organization_id=organization_id,
        slug="greeting",
        name="Greeting",
        prompt_type=PromptType.SYSTEM,
        body="Hello {{ name }}",
    )
    await variables_repo.create(
        PromptVariable(organization_id=organization_id, prompt_version_id=first.id, name="name")
    )

    second = await service.add_version(prompt, body="Hi {{ name }}")
    assert await variables_repo.list_for_version(second.id) == []


async def test_add_version_refuses_an_archived_prompt(
    prompt_service: PromptService,
    versions_repo: PromptVersionRepository,
    make_prompt: MakePromptFn,
) -> None:
    prompt, _version = await make_prompt("greeting")
    prompt = await prompt_service.archive(prompt)

    with pytest.raises(ConflictError, match="archived"):
        await prompt_service.add_version(prompt, body="Hi {{ name }}")

    assert len(await versions_repo.list_for_prompt(prompt.id)) == 1


async def test_add_version_refuses_an_invalid_template(
    prompt_service: PromptService,
    versions_repo: PromptVersionRepository,
    make_prompt: MakePromptFn,
) -> None:
    prompt, _version = await make_prompt("greeting")

    with pytest.raises(ValidationError, match="not a valid template"):
        await prompt_service.add_version(prompt, body="Hi {% for %}")

    assert len(await versions_repo.list_for_prompt(prompt.id)) == 1


# ---- publish -----------------------------------------------------------------


async def test_publish_promotes_one_revision_and_demotes_whatever_was_live(
    prompt_service: PromptService,
    versions_repo: PromptVersionRepository,
    audit_repo: PromptAuditRepository,
    publisher: RecordingPublisher,
    make_published: MakePublishedFn,
    organization_id: uuid.UUID,
) -> None:
    prompt, first = await make_published("greeting")
    assert first.status == PromptVersionStatus.PUBLISHED
    assert first.is_current is True
    assert first.published_at is not None
    assert prompt.status == PromptLifecycleStatus.PUBLISHED
    assert prompt.current_version_number == "1.0.0"

    second = await prompt_service.add_version(prompt, body="Hi {{ name }}")
    prompt = await prompt_service.publish(prompt, second, published_by="releaser-1")

    live = await versions_repo.get_current(prompt.id)
    assert live is not None
    assert live.id == second.id
    assert live.published_by == "releaser-1"
    assert first.is_current is False
    assert first.status == PromptVersionStatus.SUPERSEDED
    assert prompt.current_version_number == "1.0.1"

    assert publisher.names == [
        "PromptCreated",
        "PromptPublished",
        "PromptUpdated",
        "PromptPublished",
    ]
    assert publisher.events[-1].payload == {
        "prompt_id": str(prompt.id),
        "slug": "greeting",
        "version_number": "1.0.1",
    }
    assert str(AuditAction.PUBLISHED) in await audit_actions(audit_repo, organization_id)


async def test_publish_refuses_a_revision_belonging_to_another_prompt(
    prompt_service: PromptService, make_prompt: MakePromptFn
) -> None:
    mine, _my_version = await make_prompt("mine")
    _theirs, their_version = await make_prompt("theirs")

    with pytest.raises(ConflictError, match="does not belong to prompt"):
        await prompt_service.publish(mine, their_version)

    assert mine.status == PromptLifecycleStatus.DRAFT


async def test_publish_refuses_a_rolled_back_revision(
    prompt_service: PromptService, make_published: MakePublishedFn
) -> None:
    """A withdrawn revision must be re-drafted, never re-promoted."""
    prompt, first = await make_published("greeting")
    second = await prompt_service.add_version(prompt, body="Hi {{ name }}")
    prompt = await prompt_service.publish(prompt, second)
    prompt = await prompt_service.rollback(prompt, to_version_number="1.0.0")
    assert second.status == PromptVersionStatus.ROLLED_BACK

    with pytest.raises(ConflictError, match="rolled back"):
        await prompt_service.publish(prompt, second)

    assert prompt.current_version_number == first.version_number


# ---- rollback ----------------------------------------------------------------


async def test_rollback_moves_the_pointer_and_never_rewrites_the_withdrawn_text(
    prompt_service: PromptService,
    versions_repo: PromptVersionRepository,
    audit_repo: PromptAuditRepository,
    publisher: RecordingPublisher,
    make_published: MakePublishedFn,
    organization_id: uuid.UUID,
) -> None:
    """The whole point of the identity/revision split.

    Rolling back must leave the withdrawn revision's body byte-for-byte
    intact, so "this is the wording that was approved" stays true a year
    later.
    """
    prompt, first = await make_published("greeting", body="Hello {{ name }}")
    second_body = "Greetings, {{ name }}! Delighted to meet you.\n"
    second = await prompt_service.add_version(prompt, body=second_body)
    prompt = await prompt_service.publish(prompt, second)

    prompt = await prompt_service.rollback(
        prompt, to_version_number="1.0.0", rolled_back_by="operator-1"
    )

    withdrawn = await versions_repo.get_by_number(prompt.id, "1.0.1")
    assert withdrawn is not None
    assert withdrawn.body == second_body
    assert withdrawn.status == PromptVersionStatus.ROLLED_BACK
    assert withdrawn.is_current is False
    assert withdrawn.published_at is not None

    live = await versions_repo.get_current(prompt.id)
    assert live is not None
    assert live.id == first.id
    assert live.body == "Hello {{ name }}"
    assert live.status == PromptVersionStatus.PUBLISHED
    assert prompt.status == PromptLifecycleStatus.PUBLISHED
    assert prompt.current_version_number == "1.0.0"

    assert publisher.names[-1] == "PromptPublished"
    assert publisher.events[-1].payload == {
        "prompt_id": str(prompt.id),
        "slug": "greeting",
        "version_number": "1.0.0",
        "rolled_back": True,
    }
    assert str(AuditAction.ROLLED_BACK) in await audit_actions(audit_repo, organization_id)


async def test_rollback_summarises_which_revision_was_withdrawn(
    prompt_service: PromptService,
    audit_repo: PromptAuditRepository,
    make_published: MakePublishedFn,
    organization_id: uuid.UUID,
) -> None:
    prompt, _first = await make_published("greeting")
    second = await prompt_service.add_version(prompt, body="Hi {{ name }}")
    prompt = await prompt_service.publish(prompt, second)

    prompt = await prompt_service.rollback(prompt, to_version_number="1.0.0")

    rows = await audit_repo.list_for_org(organization_id)
    rolled = [row for row in rows if row.action == AuditAction.ROLLED_BACK]
    assert len(rolled) == 1
    assert rolled[0].summary == "Prompt 'greeting' rolled back to 1.0.0 from 1.0.1."


async def test_rollback_works_when_no_revision_is_currently_live(
    prompt_service: PromptService,
    versions_repo: PromptVersionRepository,
    audit_repo: PromptAuditRepository,
    make_published: MakePublishedFn,
    organization_id: uuid.UUID,
) -> None:
    """There is nothing to mark withdrawn, so the summary says so."""
    prompt, first = await make_published("greeting")
    await versions_repo.clear_current(prompt.id)

    prompt = await prompt_service.rollback(prompt, to_version_number=first.version_number)

    live = await versions_repo.get_current(prompt.id)
    assert live is not None
    assert live.id == first.id
    rolled = [
        row
        for row in await audit_repo.list_for_org(organization_id)
        if row.action == AuditAction.ROLLED_BACK
    ]
    assert rolled[0].summary == "Prompt 'greeting' rolled back to 1.0.0."


async def test_rollback_refuses_a_version_that_does_not_exist(
    prompt_service: PromptService, make_published: MakePublishedFn
) -> None:
    prompt, _first = await make_published("greeting")

    with pytest.raises(ConflictError, match=r"has no version 9\.9\.9"):
        await prompt_service.rollback(prompt, to_version_number="9.9.9")


async def test_rollback_refuses_a_revision_that_was_never_published(
    prompt_service: PromptService, make_published: MakePublishedFn
) -> None:
    """There is nothing to roll back *to* -- the draft was never live."""
    prompt, _first = await make_published("greeting")
    draft = await prompt_service.add_version(prompt, body="Hi {{ name }}")

    with pytest.raises(ConflictError, match="never published"):
        await prompt_service.rollback(prompt, to_version_number=draft.version_number)

    assert prompt.current_version_number == "1.0.0"


async def test_rollback_refuses_the_revision_that_is_already_live(
    prompt_service: PromptService, make_published: MakePublishedFn
) -> None:
    prompt, first = await make_published("greeting")

    with pytest.raises(ConflictError, match="already the live revision"):
        await prompt_service.rollback(prompt, to_version_number=first.version_number)


# ---- submit_for_review / deprecate / archive ---------------------------------


async def test_only_a_draft_may_enter_review(
    prompt_service: PromptService, make_prompt: MakePromptFn, make_published: MakePublishedFn
) -> None:
    draft, _version = await make_prompt("draft-prompt")
    in_review = await prompt_service.submit_for_review(draft)
    assert in_review.status == PromptLifecycleStatus.REVIEW

    with pytest.raises(ConflictError, match="not draft"):
        await prompt_service.submit_for_review(in_review)

    published, _published_version = await make_published("published-prompt")
    with pytest.raises(ConflictError, match="not draft"):
        await prompt_service.submit_for_review(published)


async def test_deprecate_keeps_the_prompt_around_and_announces_it(
    prompt_service: PromptService,
    prompts_repo: PromptRepository,
    audit_repo: PromptAuditRepository,
    publisher: RecordingPublisher,
    make_published: MakePublishedFn,
    organization_id: uuid.UUID,
) -> None:
    prompt, _version = await make_published("greeting")

    deprecated = await prompt_service.deprecate(prompt, deprecated_by="operator-1")

    assert deprecated.status == PromptLifecycleStatus.DEPRECATED
    still_there = await prompts_repo.get_by_slug(organization_id, "greeting")
    assert still_there is not None
    assert still_there.id == prompt.id

    assert publisher.names[-1] == "PromptDeprecated"
    assert publisher.events[-1].payload == {"prompt_id": str(prompt.id), "slug": "greeting"}
    assert str(AuditAction.DEPRECATED) in await audit_actions(audit_repo, organization_id)


async def test_deprecate_refuses_an_archived_prompt(
    prompt_service: PromptService, make_prompt: MakePromptFn
) -> None:
    prompt, _version = await make_prompt("greeting")
    prompt = await prompt_service.archive(prompt)

    with pytest.raises(ConflictError, match="already archived"):
        await prompt_service.deprecate(prompt)


async def test_archive_is_terminal_and_soft_deletes_the_row(
    prompt_service: PromptService,
    prompts_repo: PromptRepository,
    audit_repo: PromptAuditRepository,
    publisher: RecordingPublisher,
    make_published: MakePublishedFn,
    organization_id: uuid.UUID,
) -> None:
    prompt, _version = await make_published("greeting")

    archived = await prompt_service.archive(prompt, archived_by="operator-1")

    assert archived.status == PromptLifecycleStatus.ARCHIVED
    assert await prompts_repo.get_by_slug(organization_id, "greeting") is None
    assert await prompts_repo.list_for_org(organization_id) == []
    assert str(AuditAction.ARCHIVED) in await audit_actions(audit_repo, organization_id)
    assert "PromptDeprecated" not in publisher.names


# ---- clone -------------------------------------------------------------------


async def test_clone_starts_a_fresh_draft_at_1_0_0_recording_its_provenance(
    prompt_service: PromptService,
    audit_repo: PromptAuditRepository,
    publisher: RecordingPublisher,
    make_published: MakePublishedFn,
    organization_id: uuid.UUID,
) -> None:
    source, _version = await make_published(
        "greeting", body="Hello {{ name }}", tags=["greeting"], description="Says hello."
    )

    clone, clone_version = await prompt_service.clone(
        source, new_slug="greeting-copy", cloned_by="cloner-1"
    )

    assert clone.id != source.id
    assert clone.slug == "greeting-copy"
    assert clone.name == "Test Prompt (copy)"
    assert clone.status == PromptLifecycleStatus.DRAFT
    assert clone.current_version_number is None
    assert clone.forked_from_prompt_id == source.id
    assert clone.organization_id == organization_id
    assert clone.description == "Says hello."
    assert clone.tags == ["greeting"]
    assert clone.owner_id == "cloner-1"

    assert clone_version.version_number == "1.0.0"
    assert clone_version.status == PromptVersionStatus.DRAFT
    assert clone_version.body == "Hello {{ name }}"
    assert clone_version.prompt_id == clone.id

    assert publisher.names[-1] == "PromptCreated"
    assert str(AuditAction.CLONED) in await audit_actions(audit_repo, organization_id)


async def test_clone_copies_the_live_text_not_the_newest_draft(
    prompt_service: PromptService, make_published: MakePublishedFn
) -> None:
    source, _first = await make_published("greeting", body="Hello {{ name }}")
    await prompt_service.add_version(source, body="An unapproved rewrite {{ name }}")

    _clone, clone_version = await prompt_service.clone(source, new_slug="greeting-copy")

    assert clone_version.body == "Hello {{ name }}"


async def test_clone_of_a_draft_falls_back_to_its_only_revision(
    prompt_service: PromptService, make_prompt: MakePromptFn
) -> None:
    """A draft has no live revision, but it does have text worth copying."""
    source, first = await make_prompt("greeting", body="Hello {{ name }}")

    _clone, clone_version = await prompt_service.clone(source, new_slug="greeting-copy")

    assert clone_version.body == first.body
    assert clone_version.version_number == "1.0.0"


async def test_clone_refuses_a_slug_already_taken_in_the_target_organization(
    prompt_service: PromptService, make_published: MakePublishedFn, make_prompt: MakePromptFn
) -> None:
    source, _version = await make_published("greeting")
    await make_prompt("greeting-copy")

    with pytest.raises(ConflictError, match="already registered in that organization"):
        await prompt_service.clone(source, new_slug="greeting-copy")


async def test_clone_can_land_in_another_organization(
    prompt_service: PromptService,
    prompts_repo: PromptRepository,
    make_published: MakePublishedFn,
    organization_id: uuid.UUID,
) -> None:
    source, _version = await make_published("greeting", body="Hello {{ name }}")
    other_org = uuid.uuid4()

    clone, clone_version = await prompt_service.clone(
        source, new_slug="greeting", target_organization_id=other_org
    )

    assert clone.organization_id == other_org
    assert clone_version.organization_id == other_org
    assert clone.forked_from_prompt_id == source.id
    mine = await prompts_repo.get_by_slug(organization_id, "greeting")
    assert mine is not None
    assert mine.id == source.id


async def test_clone_refuses_a_prompt_with_no_revision_at_all(
    prompt_service: PromptService, prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    bare = await prompts_repo.create(
        Prompt(
            organization_id=organization_id,
            slug="bare",
            name="Bare",
            prompt_type=PromptType.SYSTEM,
        )
    )

    with pytest.raises(ConflictError, match="no revision to clone"):
        await prompt_service.clone(bare, new_slug="bare-copy")


# ---- mark_reviewed -----------------------------------------------------------


async def test_mark_reviewed_stamps_the_moment_the_review_happened(
    prompt_service: PromptService, make_published: MakePublishedFn
) -> None:
    prompt, _version = await make_published("greeting")
    assert prompt.last_reviewed_at is None

    reviewed = await prompt_service.mark_reviewed(prompt)

    assert reviewed.last_reviewed_at is not None
    first_stamp = reviewed.last_reviewed_at
    reviewed = await prompt_service.mark_reviewed(reviewed)
    assert reviewed.last_reviewed_at is not None
    assert reviewed.last_reviewed_at >= first_stamp
