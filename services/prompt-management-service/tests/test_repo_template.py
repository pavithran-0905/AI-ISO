"""Repository tests for :mod:`app.repositories.template`.

Every query method is exercised against real PostgreSQL with both a row
that *should* match and a row that should *not*, so a filter that was
silently dropped fails here rather than in production.

Foreign keys are enforced, so a variable's parent revision -- and that
revision's own parent prompt -- are seeded for real rather than pointed
at an invented UUID.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from shared_core.exceptions.not_found import NotFoundError

from app.models.enums import PromptCategory, PromptType, VariableKind
from app.models.prompt import Prompt, PromptVersion
from app.models.template import (
    PromptCategoryRecord,
    PromptTag,
    PromptTemplate,
    PromptVariable,
)
from app.repositories.prompt import PromptRepository, PromptVersionRepository
from app.repositories.template import (
    PromptCategoryRepository,
    PromptTagRepository,
    PromptTemplateRepository,
    PromptVariableRepository,
)
from tests.conftest import ago


async def seed_template(
    repo: PromptTemplateRepository, organization_id: uuid.UUID, slug: str, **overrides: Any
) -> PromptTemplate:
    """A minimally-populated :class:`PromptTemplate` in *organization_id*."""
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "slug": slug,
        "name": slug.replace("-", " ").title(),
        "body": f"Body of {slug}",
    }
    fields.update(overrides)
    return await repo.create(PromptTemplate(**fields))


async def seed_prompt(
    repo: PromptRepository, organization_id: uuid.UUID, slug: str, **overrides: Any
) -> Prompt:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "slug": slug,
        "name": slug.replace("-", " ").title(),
        "prompt_type": PromptType.SYSTEM,
    }
    fields.update(overrides)
    return await repo.create(Prompt(**fields))


async def seed_version(
    repo: PromptVersionRepository,
    organization_id: uuid.UUID,
    prompt_id: uuid.UUID,
    version_number: str = "1.0.0",
) -> PromptVersion:
    return await repo.create(
        PromptVersion(
            organization_id=organization_id,
            prompt_id=prompt_id,
            version_number=version_number,
            body=f"Body of {version_number}",
        )
    )


async def seed_variable(
    repo: PromptVariableRepository,
    organization_id: uuid.UUID,
    prompt_version_id: uuid.UUID,
    name: str,
    **overrides: Any,
) -> PromptVariable:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "prompt_version_id": prompt_version_id,
        "name": name,
    }
    fields.update(overrides)
    return await repo.create(PromptVariable(**fields))


async def seed_tag(
    repo: PromptTagRepository,
    organization_id: uuid.UUID,
    prompt_id: uuid.UUID,
    tag: str,
    **overrides: Any,
) -> PromptTag:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "prompt_id": prompt_id,
        "tag": tag,
    }
    fields.update(overrides)
    return await repo.create(PromptTag(**fields))


async def seed_category(
    repo: PromptCategoryRepository, organization_id: uuid.UUID, slug: str, **overrides: Any
) -> PromptCategoryRecord:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "slug": slug,
        "name": slug.replace("-", " ").title(),
    }
    fields.update(overrides)
    return await repo.create(PromptCategoryRecord(**fields))


# ---- PromptTemplateRepository.require_in_org --------------------------------


async def test_template_require_in_org_never_returns_another_tenants_row(
    templates_repo: PromptTemplateRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    mine = await seed_template(templates_repo, organization_id, "shared-slug")
    theirs = await seed_template(templates_repo, other_org, "shared-slug")
    assert mine.id != theirs.id

    assert (await templates_repo.require_in_org(organization_id, mine.id)).id == mine.id
    assert (await templates_repo.require_in_org(other_org, theirs.id)).id == theirs.id

    with pytest.raises(NotFoundError):
        await templates_repo.require_in_org(organization_id, theirs.id)
    with pytest.raises(NotFoundError):
        await templates_repo.require_in_org(other_org, mine.id)


async def test_template_require_in_org_raises_for_an_id_that_exists_nowhere(
    templates_repo: PromptTemplateRepository, organization_id: uuid.UUID
) -> None:
    with pytest.raises(NotFoundError):
        await templates_repo.require_in_org(organization_id, uuid.uuid4())


async def test_template_require_in_org_skips_a_soft_deleted_row(
    templates_repo: PromptTemplateRepository, organization_id: uuid.UUID
) -> None:
    kept = await seed_template(templates_repo, organization_id, "kept")
    gone = await seed_template(templates_repo, organization_id, "gone")
    await templates_repo.delete(gone.id)

    assert (await templates_repo.require_in_org(organization_id, kept.id)).id == kept.id
    with pytest.raises(NotFoundError):
        await templates_repo.require_in_org(organization_id, gone.id)
    assert await templates_repo.get_by_slug(organization_id, "gone") is None
    assert [row.id for row in await templates_repo.list_for_org(organization_id)] == [kept.id]


# ---- PromptTemplateRepository.get_by_slug -----------------------------------


async def test_get_by_slug_treats_locale_as_part_of_the_natural_key(
    templates_repo: PromptTemplateRepository, organization_id: uuid.UUID
) -> None:
    """The same slug in two languages is two distinct templates."""
    english = await seed_template(templates_repo, organization_id, "greeting", locale="en")
    french = await seed_template(templates_repo, organization_id, "greeting", locale="fr")
    assert english.id != french.id

    found_en = await templates_repo.get_by_slug(organization_id, "greeting", locale="en")
    found_fr = await templates_repo.get_by_slug(organization_id, "greeting", locale="fr")
    assert found_en is not None
    assert found_fr is not None
    assert found_en.id == english.id
    assert found_fr.id == french.id

    assert await templates_repo.get_by_slug(organization_id, "greeting", locale="de") is None
    assert await templates_repo.get_by_slug(organization_id, "no-such-slug") is None


async def test_get_by_slug_defaults_to_english_and_stays_inside_one_tenant(
    templates_repo: PromptTemplateRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    mine = await seed_template(templates_repo, organization_id, "footer", locale="en")
    theirs = await seed_template(templates_repo, other_org, "footer", locale="en")

    default_locale = await templates_repo.get_by_slug(organization_id, "footer")
    assert default_locale is not None
    assert default_locale.id == mine.id
    assert default_locale.id != theirs.id

    theirs_found = await templates_repo.get_by_slug(other_org, "footer")
    assert theirs_found is not None
    assert theirs_found.id == theirs.id


# ---- PromptTemplateRepository.get_by_slug_any_locale ------------------------


async def test_get_by_slug_any_locale_prefers_the_exact_locale(
    templates_repo: PromptTemplateRepository, organization_id: uuid.UUID
) -> None:
    english = await seed_template(templates_repo, organization_id, "banner", locale="en")
    french = await seed_template(templates_repo, organization_id, "banner", locale="fr")

    exact = await templates_repo.get_by_slug_any_locale(
        organization_id, "banner", preferred_locale="fr"
    )
    assert exact is not None
    assert exact.id == french.id
    assert exact.id != english.id


async def test_get_by_slug_any_locale_falls_back_when_the_translation_is_missing(
    templates_repo: PromptTemplateRepository, organization_id: uuid.UUID
) -> None:
    """An untranslated shared component still resolves rather than
    failing the whole render."""
    only_english = await seed_template(templates_repo, organization_id, "disclaimer", locale="en")

    fallback = await templates_repo.get_by_slug_any_locale(
        organization_id, "disclaimer", preferred_locale="ja"
    )
    assert fallback is not None
    assert fallback.id == only_english.id


async def test_get_by_slug_any_locale_returns_none_for_an_unknown_slug_or_tenant(
    templates_repo: PromptTemplateRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    await seed_template(templates_repo, other_org, "theirs-only", locale="fr")

    assert await templates_repo.get_by_slug_any_locale(organization_id, "theirs-only") is None
    assert await templates_repo.get_by_slug_any_locale(organization_id, "never-existed") is None


# ---- PromptTemplateRepository.list_for_org ----------------------------------


async def test_template_list_for_org_is_newest_first_and_excludes_other_tenants(
    templates_repo: PromptTemplateRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    oldest = await seed_template(templates_repo, organization_id, "oldest", created_at=ago(300))
    middle = await seed_template(templates_repo, organization_id, "middle", created_at=ago(200))
    newest = await seed_template(templates_repo, organization_id, "newest", created_at=ago(100))
    await seed_template(templates_repo, other_org, "theirs", created_at=ago(150))

    listed = await templates_repo.list_for_org(organization_id)
    assert [row.id for row in listed] == [newest.id, middle.id, oldest.id]


async def test_template_list_for_org_honours_limit_and_offset(
    templates_repo: PromptTemplateRepository, organization_id: uuid.UUID
) -> None:
    oldest = await seed_template(templates_repo, organization_id, "t-oldest", created_at=ago(300))
    middle = await seed_template(templates_repo, organization_id, "t-middle", created_at=ago(200))
    newest = await seed_template(templates_repo, organization_id, "t-newest", created_at=ago(100))

    assert [row.id for row in await templates_repo.list_for_org(organization_id, limit=2)] == [
        newest.id,
        middle.id,
    ]
    assert [
        row.id for row in await templates_repo.list_for_org(organization_id, limit=2, offset=1)
    ] == [middle.id, oldest.id]
    assert await templates_repo.list_for_org(organization_id, offset=3) == []


async def test_template_list_for_org_of_an_empty_tenant_is_empty(
    templates_repo: PromptTemplateRepository, organization_id: uuid.UUID
) -> None:
    await seed_template(templates_repo, organization_id, "only-mine")
    assert await templates_repo.list_for_org(uuid.uuid4()) == []


# ---- PromptTemplateRepository.list_shared_components ------------------------


async def test_list_shared_components_returns_only_the_reusable_ones(
    templates_repo: PromptTemplateRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    shared = await seed_template(
        templates_repo, organization_id, "shared-header", is_shared_component=True
    )
    also_shared = await seed_template(
        templates_repo, organization_id, "shared-footer", is_shared_component=True
    )
    private = await seed_template(
        templates_repo, organization_id, "private-body", is_shared_component=False
    )
    theirs = await seed_template(
        templates_repo, other_org, "their-header", is_shared_component=True
    )

    rows = await templates_repo.list_shared_components(organization_id)
    assert {row.id for row in rows} == {shared.id, also_shared.id}
    assert {private.id, theirs.id}.isdisjoint({row.id for row in rows})


async def test_list_shared_components_is_empty_when_nothing_is_reusable(
    templates_repo: PromptTemplateRepository, organization_id: uuid.UUID
) -> None:
    await seed_template(templates_repo, organization_id, "solo", is_shared_component=False)
    assert await templates_repo.list_shared_components(organization_id) == []


# ---- PromptVariableRepository.list_for_version ------------------------------


async def test_variable_list_for_version_is_alphabetical_and_scoped_to_one_revision(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    variables_repo: PromptVariableRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "with-variables")
    first_version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    second_version = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")

    zulu = await seed_variable(variables_repo, organization_id, first_version.id, "zulu")
    alpha = await seed_variable(variables_repo, organization_id, first_version.id, "alpha")
    mike = await seed_variable(variables_repo, organization_id, first_version.id, "mike")
    other = await seed_variable(variables_repo, organization_id, second_version.id, "alpha")

    rows = await variables_repo.list_for_version(first_version.id)
    assert [row.id for row in rows] == [alpha.id, mike.id, zulu.id]
    assert other.id not in {row.id for row in rows}
    assert await variables_repo.list_for_version(uuid.uuid4()) == []


# ---- PromptVariableRepository.get_by_name -----------------------------------


async def test_variable_get_by_name_matches_one_revisions_own_declaration_only(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    variables_repo: PromptVariableRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "named-variables")
    first_version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    second_version = await seed_version(versions_repo, organization_id, prompt.id, "2.0.0")
    mine = await seed_variable(variables_repo, organization_id, first_version.id, "customer")
    theirs = await seed_variable(variables_repo, organization_id, second_version.id, "customer")

    found = await variables_repo.get_by_name(first_version.id, "customer")
    assert found is not None
    assert found.id == mine.id
    assert found.id != theirs.id
    assert await variables_repo.get_by_name(first_version.id, "unknown") is None


# ---- PromptVariableRepository.list_masked_names -----------------------------


async def test_list_masked_names_includes_every_secret_reference_even_when_unmasked(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    variables_repo: PromptVariableRepository,
    organization_id: uuid.UUID,
) -> None:
    """A secret is masked whether or not anyone ticked the box."""
    prompt = await seed_prompt(prompts_repo, organization_id, "masked-variables")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")

    await seed_variable(variables_repo, organization_id, version.id, "explicitly", is_masked=True)
    await seed_variable(
        variables_repo,
        organization_id,
        version.id,
        "unticked-secret",
        kind=VariableKind.SECRET_REFERENCE,
        secret_reference="vault://api-key",
        is_masked=False,
    )
    await seed_variable(
        variables_repo,
        organization_id,
        version.id,
        "ticked-secret",
        kind=VariableKind.SECRET_REFERENCE,
        secret_reference="vault://token",
        is_masked=True,
    )
    await seed_variable(variables_repo, organization_id, version.id, "plain", is_masked=False)

    assert await variables_repo.list_masked_names(version.id) == {
        "explicitly",
        "unticked-secret",
        "ticked-secret",
    }


async def test_list_masked_names_is_empty_when_nothing_is_sensitive(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    variables_repo: PromptVariableRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "nothing-masked")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    sibling = await seed_version(versions_repo, organization_id, prompt.id, "2.0.0")
    await seed_variable(variables_repo, organization_id, version.id, "public")
    await seed_variable(variables_repo, organization_id, sibling.id, "secret", is_masked=True)

    assert await variables_repo.list_masked_names(version.id) == set()
    assert await variables_repo.list_masked_names(uuid.uuid4()) == set()


# ---- PromptCategoryRepository -----------------------------------------------


async def test_category_get_by_slug_resolves_within_one_tenant_only(
    categories_repo: PromptCategoryRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    mine = await seed_category(categories_repo, organization_id, "runbooks")
    theirs = await seed_category(categories_repo, other_org, "runbooks")

    found = await categories_repo.get_by_slug(organization_id, "runbooks")
    assert found is not None
    assert found.id == mine.id

    found_other = await categories_repo.get_by_slug(other_org, "runbooks")
    assert found_other is not None
    assert found_other.id == theirs.id

    assert await categories_repo.get_by_slug(organization_id, "no-such-category") is None


async def test_category_list_for_org_is_ordered_by_name_and_excludes_other_tenants(
    categories_repo: PromptCategoryRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    zeta = await seed_category(categories_repo, organization_id, "zeta", name="Zeta")
    alpha = await seed_category(categories_repo, organization_id, "alpha", name="Alpha")
    mid = await seed_category(
        categories_repo, organization_id, "mid", name="Mid", base_category=PromptCategory.SECURITY
    )
    theirs = await seed_category(categories_repo, other_org, "theirs", name="Aaa Theirs")

    rows = await categories_repo.list_for_org(organization_id)
    assert [row.id for row in rows] == [alpha.id, mid.id, zeta.id]
    assert theirs.id not in {row.id for row in rows}
    assert await categories_repo.list_for_org(uuid.uuid4()) == []


# ---- PromptTagRepository.list_for_prompt ------------------------------------


async def test_tag_list_for_prompt_is_alphabetical_and_scoped_to_one_prompt(
    prompts_repo: PromptRepository,
    tags_repo: PromptTagRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "tagged")
    sibling = await seed_prompt(prompts_repo, organization_id, "tagged-sibling")
    security = await seed_tag(tags_repo, organization_id, prompt.id, "security")
    audit = await seed_tag(tags_repo, organization_id, prompt.id, "audit")
    other = await seed_tag(tags_repo, organization_id, sibling.id, "audit")

    rows = await tags_repo.list_for_prompt(prompt.id)
    assert [row.id for row in rows] == [audit.id, security.id]
    assert other.id not in {row.id for row in rows}
    assert await tags_repo.list_for_prompt(uuid.uuid4()) == []


# ---- PromptTagRepository.list_prompt_ids_with_tag ---------------------------


async def test_list_prompt_ids_with_tag_matches_one_tag_in_one_tenant(
    prompts_repo: PromptRepository,
    tags_repo: PromptTagRepository,
    organization_id: uuid.UUID,
) -> None:
    other_org = uuid.uuid4()
    first = await seed_prompt(prompts_repo, organization_id, "first")
    second = await seed_prompt(prompts_repo, organization_id, "second")
    unrelated = await seed_prompt(prompts_repo, organization_id, "unrelated")
    theirs = await seed_prompt(prompts_repo, other_org, "theirs")

    await seed_tag(tags_repo, organization_id, first.id, "compliance")
    await seed_tag(tags_repo, organization_id, second.id, "compliance")
    await seed_tag(tags_repo, organization_id, unrelated.id, "performance")
    await seed_tag(tags_repo, other_org, theirs.id, "compliance")

    assert set(await tags_repo.list_prompt_ids_with_tag(organization_id, "compliance")) == {
        first.id,
        second.id,
    }
    assert await tags_repo.list_prompt_ids_with_tag(organization_id, "performance") == [
        unrelated.id
    ]
    assert await tags_repo.list_prompt_ids_with_tag(other_org, "compliance") == [theirs.id]
    assert await tags_repo.list_prompt_ids_with_tag(organization_id, "never-applied") == []


# ---- PromptTagRepository.delete_for_prompt ----------------------------------


async def test_delete_for_prompt_reports_how_many_tags_it_removed(
    prompts_repo: PromptRepository,
    tags_repo: PromptTagRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "retagged")
    sibling = await seed_prompt(prompts_repo, organization_id, "retagged-sibling")
    for tag in ("alpha", "beta", "gamma"):
        await seed_tag(tags_repo, organization_id, prompt.id, tag)
    kept = await seed_tag(tags_repo, organization_id, sibling.id, "alpha")

    assert await tags_repo.delete_for_prompt(prompt.id) == 3

    assert await tags_repo.list_for_prompt(prompt.id) == []
    assert [row.id for row in await tags_repo.list_for_prompt(sibling.id)] == [kept.id]
    assert await tags_repo.list_prompt_ids_with_tag(organization_id, "alpha") == [sibling.id]


async def test_delete_for_prompt_reports_zero_for_an_untagged_prompt(
    prompts_repo: PromptRepository,
    tags_repo: PromptTagRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "untagged")
    assert await tags_repo.delete_for_prompt(prompt.id) == 0
    assert await tags_repo.delete_for_prompt(uuid.uuid4()) == 0


async def test_delete_for_prompt_frees_the_tag_to_be_applied_again(
    prompts_repo: PromptRepository,
    tags_repo: PromptTagRepository,
    organization_id: uuid.UUID,
) -> None:
    """A hard delete, not a soft one -- ``uq_prompt_tag`` would reject
    the re-application otherwise."""
    prompt = await seed_prompt(prompts_repo, organization_id, "recycled")
    await seed_tag(tags_repo, organization_id, prompt.id, "security")

    assert await tags_repo.delete_for_prompt(prompt.id) == 1

    reapplied = await seed_tag(tags_repo, organization_id, prompt.id, "security")
    assert [row.id for row in await tags_repo.list_for_prompt(prompt.id)] == [reapplied.id]
