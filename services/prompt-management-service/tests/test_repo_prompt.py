"""Repository tests for :mod:`app.repositories.prompt`.

Every query method is exercised against real PostgreSQL with both a row
that *should* match and a row that should *not*, so a filter that was
silently dropped fails here rather than in production.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    PromptCategory,
    PromptLifecycleStatus,
    PromptType,
    PromptVersionStatus,
)
from app.models.prompt import Prompt, PromptVersion
from app.repositories.prompt import PromptRepository, PromptVersionRepository
from tests.conftest import ago, utcnow


def make_prompt_row(organization_id: uuid.UUID, slug: str, **overrides: Any) -> Prompt:
    """A minimally-populated :class:`Prompt` in *organization_id*."""
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "slug": slug,
        "name": slug.replace("-", " ").title(),
        "prompt_type": PromptType.SYSTEM,
    }
    fields.update(overrides)
    return Prompt(**fields)


def make_version_row(
    organization_id: uuid.UUID, prompt_id: uuid.UUID, version_number: str, **overrides: Any
) -> PromptVersion:
    """A minimally-populated :class:`PromptVersion` of *prompt_id*."""
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "prompt_id": prompt_id,
        "version_number": version_number,
        "body": f"Body of {version_number}",
    }
    fields.update(overrides)
    return PromptVersion(**fields)


async def seed_prompt(
    repo: PromptRepository, organization_id: uuid.UUID, slug: str, **overrides: Any
) -> Prompt:
    return await repo.create(make_prompt_row(organization_id, slug, **overrides))


# ---- PromptRepository.require_in_org ----------------------------------------


async def test_require_in_org_never_returns_another_tenants_identically_shaped_row(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    mine = await seed_prompt(prompts_repo, organization_id, "shared-slug")
    theirs = await seed_prompt(prompts_repo, other_org, "shared-slug")
    assert mine.id != theirs.id

    assert (await prompts_repo.require_in_org(organization_id, mine.id)).id == mine.id
    assert (await prompts_repo.require_in_org(other_org, theirs.id)).id == theirs.id

    with pytest.raises(NotFoundError):
        await prompts_repo.require_in_org(organization_id, theirs.id)
    with pytest.raises(NotFoundError):
        await prompts_repo.require_in_org(other_org, mine.id)


async def test_require_in_org_raises_for_an_id_that_exists_nowhere(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    with pytest.raises(NotFoundError):
        await prompts_repo.require_in_org(organization_id, uuid.uuid4())


async def test_require_in_org_and_get_by_slug_skip_soft_deleted_rows(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    kept = await seed_prompt(prompts_repo, organization_id, "kept")
    gone = await seed_prompt(prompts_repo, organization_id, "gone")
    await prompts_repo.delete(gone.id)

    assert (await prompts_repo.require_in_org(organization_id, kept.id)).id == kept.id
    with pytest.raises(NotFoundError):
        await prompts_repo.require_in_org(organization_id, gone.id)
    assert await prompts_repo.get_by_slug(organization_id, "gone") is None
    assert [row.id for row in await prompts_repo.list_for_org(organization_id)] == [kept.id]


# ---- PromptRepository.get_by_slug -------------------------------------------


async def test_get_by_slug_resolves_within_one_tenant_only(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    mine = await seed_prompt(prompts_repo, organization_id, "greeting")
    theirs = await seed_prompt(prompts_repo, other_org, "greeting")

    found = await prompts_repo.get_by_slug(organization_id, "greeting")
    assert found is not None
    assert found.id == mine.id

    found_other = await prompts_repo.get_by_slug(other_org, "greeting")
    assert found_other is not None
    assert found_other.id == theirs.id

    assert await prompts_repo.get_by_slug(organization_id, "no-such-slug") is None


# ---- PromptRepository.list_for_org ------------------------------------------


async def test_list_for_org_returns_newest_first_and_excludes_other_tenants(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    oldest = await seed_prompt(prompts_repo, organization_id, "oldest", created_at=ago(300))
    middle = await seed_prompt(prompts_repo, organization_id, "middle", created_at=ago(200))
    newest = await seed_prompt(prompts_repo, organization_id, "newest", created_at=ago(100))
    await seed_prompt(prompts_repo, other_org, "theirs", created_at=ago(150))

    listed = await prompts_repo.list_for_org(organization_id)
    assert [row.id for row in listed] == [newest.id, middle.id, oldest.id]


async def test_list_for_org_filters_by_type_category_and_status_independently(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    target = await seed_prompt(
        prompts_repo,
        organization_id,
        "target",
        prompt_type=PromptType.AGENT,
        category=PromptCategory.SECURITY,
        status=PromptLifecycleStatus.PUBLISHED,
    )
    await seed_prompt(
        prompts_repo,
        organization_id,
        "decoy",
        prompt_type=PromptType.USER,
        category=PromptCategory.REPORTING,
        status=PromptLifecycleStatus.DRAFT,
    )

    by_type = await prompts_repo.list_for_org(organization_id, prompt_type=PromptType.AGENT)
    assert [row.id for row in by_type] == [target.id]

    by_category = await prompts_repo.list_for_org(organization_id, category=PromptCategory.SECURITY)
    assert [row.id for row in by_category] == [target.id]

    by_status = await prompts_repo.list_for_org(
        organization_id, status=PromptLifecycleStatus.PUBLISHED
    )
    assert [row.id for row in by_status] == [target.id]

    combined = await prompts_repo.list_for_org(
        organization_id,
        prompt_type=PromptType.AGENT,
        category=PromptCategory.REPORTING,
    )
    assert combined == []


async def test_list_for_org_honours_limit_and_offset(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    oldest = await seed_prompt(prompts_repo, organization_id, "p-oldest", created_at=ago(300))
    middle = await seed_prompt(prompts_repo, organization_id, "p-middle", created_at=ago(200))
    newest = await seed_prompt(prompts_repo, organization_id, "p-newest", created_at=ago(100))

    assert [row.id for row in await prompts_repo.list_for_org(organization_id, limit=2)] == [
        newest.id,
        middle.id,
    ]
    assert [
        row.id for row in await prompts_repo.list_for_org(organization_id, limit=2, offset=1)
    ] == [middle.id, oldest.id]
    assert await prompts_repo.list_for_org(organization_id, offset=3) == []


async def test_list_for_org_of_an_empty_tenant_is_empty(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    await seed_prompt(prompts_repo, organization_id, "only-mine")
    assert await prompts_repo.list_for_org(uuid.uuid4()) == []


# ---- PromptRepository.search ------------------------------------------------


async def test_search_covers_slug_name_and_description_but_not_other_tenants(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    by_slug = await seed_prompt(prompts_repo, organization_id, "alpha-prompt", name="Nondescript")
    by_name = await seed_prompt(prompts_repo, organization_id, "b-prompt", name="Zeta Wording")
    by_description = await seed_prompt(
        prompts_repo, organization_id, "c-prompt", name="Plain", description="contains needle here"
    )
    await seed_prompt(prompts_repo, other_org, "alpha-prompt", name="Zeta Wording")

    assert [row.id for row in await prompts_repo.search_in_org(organization_id, "alpha")] == [
        by_slug.id
    ]
    assert [row.id for row in await prompts_repo.search_in_org(organization_id, "zeta")] == [
        by_name.id
    ]
    assert [row.id for row in await prompts_repo.search_in_org(organization_id, "needle")] == [
        by_description.id
    ]
    assert await prompts_repo.search_in_org(organization_id, "unmatchable-term") == []


async def test_search_escapes_like_wildcards_rather_than_expanding_them(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    literal = await seed_prompt(prompts_repo, organization_id, "pct", name="100% Coverage")
    await seed_prompt(prompts_repo, organization_id, "no-pct", name="100X Coverage")

    assert [row.id for row in await prompts_repo.search_in_org(organization_id, "100%")] == [
        literal.id
    ]


async def test_search_with_a_blank_query_filters_nothing_and_respects_limit(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    first = await seed_prompt(prompts_repo, organization_id, "s-one")
    second = await seed_prompt(prompts_repo, organization_id, "s-two")
    await seed_prompt(prompts_repo, other_org, "s-three")

    assert {row.id for row in await prompts_repo.search_in_org(organization_id, "   ")} == {
        first.id,
        second.id,
    }
    assert len(await prompts_repo.search_in_org(organization_id, "", limit=1)) == 1


# ---- PromptRepository.list_due_for_review -----------------------------------


async def test_list_due_for_review_treats_a_null_last_reviewed_at_as_due(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    cutoff = utcnow()
    never = await seed_prompt(
        prompts_repo,
        organization_id,
        "never-reviewed",
        status=PromptLifecycleStatus.PUBLISHED,
        last_reviewed_at=None,
    )
    fresh = await seed_prompt(
        prompts_repo,
        organization_id,
        "recently-reviewed",
        status=PromptLifecycleStatus.PUBLISHED,
        last_reviewed_at=cutoff.replace() + (cutoff - cutoff) + _one_minute(),
    )

    due = await prompts_repo.list_due_for_review(cutoff)
    assert [row.id for row in due] == [never.id]
    assert fresh.id not in {row.id for row in due}


def _one_minute() -> timedelta:
    return timedelta(minutes=1)


async def test_list_due_for_review_includes_exactly_at_the_cutoff(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    cutoff = utcnow()
    at_cutoff = await seed_prompt(
        prompts_repo,
        organization_id,
        "at-cutoff",
        status=PromptLifecycleStatus.PUBLISHED,
        last_reviewed_at=cutoff,
    )
    just_after = await seed_prompt(
        prompts_repo,
        organization_id,
        "just-after",
        status=PromptLifecycleStatus.PUBLISHED,
        last_reviewed_at=cutoff + _one_minute(),
    )

    due = await prompts_repo.list_due_for_review(cutoff)
    assert [row.id for row in due] == [at_cutoff.id]
    assert just_after.id not in {row.id for row in due}


async def test_list_due_for_review_orders_nulls_first_then_oldest_and_skips_unpublished(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    cutoff = utcnow()
    stale = await seed_prompt(
        prompts_repo,
        organization_id,
        "stale",
        status=PromptLifecycleStatus.PUBLISHED,
        last_reviewed_at=ago(7_200),
    )
    borderline = await seed_prompt(
        prompts_repo,
        organization_id,
        "borderline",
        status=PromptLifecycleStatus.PUBLISHED,
        last_reviewed_at=ago(60),
    )
    never = await seed_prompt(
        prompts_repo,
        organization_id,
        "never",
        status=PromptLifecycleStatus.PUBLISHED,
        last_reviewed_at=None,
    )
    draft = await seed_prompt(
        prompts_repo,
        organization_id,
        "draft-never-reviewed",
        status=PromptLifecycleStatus.DRAFT,
        last_reviewed_at=None,
    )
    archived = await seed_prompt(
        prompts_repo,
        organization_id,
        "archived-stale",
        status=PromptLifecycleStatus.ARCHIVED,
        last_reviewed_at=ago(7_200),
    )

    due = await prompts_repo.list_due_for_review(cutoff)
    assert [row.id for row in due] == [never.id, stale.id, borderline.id]
    assert {draft.id, archived.id}.isdisjoint({row.id for row in due})

    assert [row.id for row in await prompts_repo.list_due_for_review(cutoff, limit=2)] == [
        never.id,
        stale.id,
    ]


async def test_list_due_for_review_is_empty_when_everything_is_fresh(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    cutoff = ago(3_600)
    await seed_prompt(
        prompts_repo,
        organization_id,
        "fresh",
        status=PromptLifecycleStatus.PUBLISHED,
        last_reviewed_at=utcnow(),
    )
    assert await prompts_repo.list_due_for_review(cutoff) == []


# ---- PromptRepository.list_expired ------------------------------------------


async def test_list_expired_includes_exactly_at_the_moment_and_excludes_null_expiry(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    moment = utcnow()
    already = await seed_prompt(
        prompts_repo,
        organization_id,
        "already-expired",
        status=PromptLifecycleStatus.PUBLISHED,
        expires_at=moment - _one_minute(),
    )
    at_moment = await seed_prompt(
        prompts_repo,
        organization_id,
        "expires-now",
        status=PromptLifecycleStatus.PUBLISHED,
        expires_at=moment,
    )
    later = await seed_prompt(
        prompts_repo,
        organization_id,
        "expires-later",
        status=PromptLifecycleStatus.PUBLISHED,
        expires_at=moment + _one_minute(),
    )
    never = await seed_prompt(
        prompts_repo,
        organization_id,
        "never-expires",
        status=PromptLifecycleStatus.PUBLISHED,
        expires_at=None,
    )
    draft = await seed_prompt(
        prompts_repo,
        organization_id,
        "draft-expired",
        status=PromptLifecycleStatus.DRAFT,
        expires_at=moment - _one_minute(),
    )

    expired = await prompts_repo.list_expired(moment)
    assert {row.id for row in expired} == {already.id, at_moment.id}
    assert {later.id, never.id, draft.id}.isdisjoint({row.id for row in expired})

    limited = await prompts_repo.list_expired(moment, limit=1)
    assert len(limited) == 1
    assert limited[0].id in {already.id, at_moment.id}


async def test_list_expired_is_empty_when_nothing_has_lapsed(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    await seed_prompt(
        prompts_repo,
        organization_id,
        "future",
        status=PromptLifecycleStatus.PUBLISHED,
        expires_at=utcnow() + _one_minute(),
    )
    assert await prompts_repo.list_expired(utcnow()) == []


# ---- PromptRepository.list_organization_ids ---------------------------------


async def test_list_organization_ids_collapses_duplicates_and_honours_limit(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    await seed_prompt(prompts_repo, organization_id, "one")
    await seed_prompt(prompts_repo, organization_id, "two")
    await seed_prompt(prompts_repo, other_org, "three")

    assert set(await prompts_repo.list_organization_ids()) == {organization_id, other_org}
    assert len(await prompts_repo.list_organization_ids(limit=1)) == 1


# ---- PromptRepository.list_in_window ----------------------------------------


async def test_list_in_window_is_inclusive_of_since_and_exclusive_of_until(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    since = ago(3_600)
    until = ago(1_800)

    at_since = await seed_prompt(prompts_repo, organization_id, "at-since", created_at=since)
    inside = await seed_prompt(prompts_repo, organization_id, "inside", created_at=ago(2_400))
    at_until = await seed_prompt(prompts_repo, organization_id, "at-until", created_at=until)
    before = await seed_prompt(prompts_repo, organization_id, "before", created_at=ago(7_200))
    await seed_prompt(prompts_repo, other_org, "other-org-inside", created_at=ago(2_400))

    rows = await prompts_repo.list_in_window(organization_id, since=since, until=until)
    assert {row.id for row in rows} == {at_since.id, inside.id}
    assert {at_until.id, before.id}.isdisjoint({row.id for row in rows})


async def test_list_in_window_of_an_empty_window_is_empty(
    prompts_repo: PromptRepository, organization_id: uuid.UUID
) -> None:
    await seed_prompt(prompts_repo, organization_id, "outside", created_at=ago(10))
    rows = await prompts_repo.list_in_window(organization_id, since=ago(7_200), until=ago(3_600))
    assert rows == []


# ---- PromptVersionRepository.require_in_org ---------------------------------


async def test_version_require_in_org_never_crosses_the_tenant_boundary(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    organization_id: uuid.UUID,
) -> None:
    other_org = uuid.uuid4()
    mine_prompt = await seed_prompt(prompts_repo, organization_id, "mine")
    theirs_prompt = await seed_prompt(prompts_repo, other_org, "theirs")
    mine = await versions_repo.create(make_version_row(organization_id, mine_prompt.id, "1.0.0"))
    theirs = await versions_repo.create(make_version_row(other_org, theirs_prompt.id, "1.0.0"))

    assert (await versions_repo.require_in_org(organization_id, mine.id)).id == mine.id
    assert (await versions_repo.require_in_org(other_org, theirs.id)).id == theirs.id
    with pytest.raises(NotFoundError):
        await versions_repo.require_in_org(organization_id, theirs.id)
    with pytest.raises(NotFoundError):
        await versions_repo.require_in_org(organization_id, uuid.uuid4())


# ---- PromptVersionRepository.list_for_prompt / get_by_number ----------------


async def test_list_for_prompt_is_newest_first_and_scoped_to_one_prompt(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "versioned")
    sibling = await seed_prompt(prompts_repo, organization_id, "sibling")
    first = await versions_repo.create(
        make_version_row(organization_id, prompt.id, "1.0.0", created_at=ago(300))
    )
    second = await versions_repo.create(
        make_version_row(organization_id, prompt.id, "1.1.0", created_at=ago(200))
    )
    third = await versions_repo.create(
        make_version_row(organization_id, prompt.id, "2.0.0", created_at=ago(100))
    )
    other = await versions_repo.create(
        make_version_row(organization_id, sibling.id, "1.0.0", created_at=ago(150))
    )

    rows = await versions_repo.list_for_prompt(prompt.id)
    assert [row.id for row in rows] == [third.id, second.id, first.id]
    assert other.id not in {row.id for row in rows}
    assert await versions_repo.list_for_prompt(uuid.uuid4()) == []


async def test_get_by_number_matches_one_prompts_own_revision_only(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "numbered")
    sibling = await seed_prompt(prompts_repo, organization_id, "numbered-sibling")
    mine = await versions_repo.create(make_version_row(organization_id, prompt.id, "1.0.0"))
    theirs = await versions_repo.create(make_version_row(organization_id, sibling.id, "1.0.0"))

    found = await versions_repo.get_by_number(prompt.id, "1.0.0")
    assert found is not None
    assert found.id == mine.id
    assert found.id != theirs.id
    assert await versions_repo.get_by_number(prompt.id, "9.9.9") is None


# ---- PromptVersionRepository.clear_current / get_current --------------------


async def test_clear_current_demotes_exactly_one_row_and_marks_it_superseded(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "live")
    sibling = await seed_prompt(prompts_repo, organization_id, "untouched")
    live = await versions_repo.create(
        make_version_row(
            organization_id,
            prompt.id,
            "1.0.0",
            is_current=True,
            status=PromptVersionStatus.PUBLISHED,
        )
    )
    draft = await versions_repo.create(
        make_version_row(
            organization_id, prompt.id, "1.1.0", is_current=False, status=PromptVersionStatus.DRAFT
        )
    )
    other_live = await versions_repo.create(
        make_version_row(
            organization_id,
            sibling.id,
            "1.0.0",
            is_current=True,
            status=PromptVersionStatus.PUBLISHED,
        )
    )

    assert await versions_repo.clear_current(prompt.id) == 1

    assert live.is_current is False
    assert live.status == PromptVersionStatus.SUPERSEDED
    assert draft.is_current is False
    assert draft.status == PromptVersionStatus.DRAFT
    assert other_live.is_current is True
    assert other_live.status == PromptVersionStatus.PUBLISHED

    assert await versions_repo.get_current(prompt.id) is None
    current_sibling = await versions_repo.get_current(sibling.id)
    assert current_sibling is not None
    assert current_sibling.id == other_live.id


async def test_clear_current_demotes_every_drifted_row_and_leaves_get_current_deterministic(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    organization_id: uuid.UUID,
) -> None:
    """Two rows both claiming to be live is exactly the drift this guards."""
    prompt = await seed_prompt(prompts_repo, organization_id, "drifted")
    first = await versions_repo.create(
        make_version_row(
            organization_id,
            prompt.id,
            "1.0.0",
            is_current=True,
            status=PromptVersionStatus.PUBLISHED,
        )
    )
    second = await versions_repo.create(
        make_version_row(
            organization_id,
            prompt.id,
            "1.1.0",
            is_current=True,
            status=PromptVersionStatus.PUBLISHED,
        )
    )

    assert await versions_repo.clear_current(prompt.id) == 2
    assert [row.status for row in (first, second)] == [
        PromptVersionStatus.SUPERSEDED,
        PromptVersionStatus.SUPERSEDED,
    ]
    assert await versions_repo.get_current(prompt.id) is None

    second.is_current = True
    second.status = PromptVersionStatus.PUBLISHED
    await versions_repo.update(second)

    promoted = await versions_repo.get_current(prompt.id)
    assert promoted is not None
    assert promoted.id == second.id


async def test_clear_current_reports_zero_when_no_revision_is_live(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "all-draft")
    await versions_repo.create(make_version_row(organization_id, prompt.id, "1.0.0"))
    assert await versions_repo.clear_current(prompt.id) == 0
    assert await versions_repo.clear_current(uuid.uuid4()) == 0


async def test_get_current_ignores_a_soft_deleted_live_revision(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "deleted-current")
    live = await versions_repo.create(
        make_version_row(organization_id, prompt.id, "1.0.0", is_current=True)
    )
    await versions_repo.delete(live.id)

    assert await versions_repo.get_current(prompt.id) is None
    assert await versions_repo.clear_current(prompt.id) == 0


# ---- PromptVersionRepository.list_published ---------------------------------


async def test_list_published_covers_published_and_superseded_only(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "history")
    sibling = await seed_prompt(prompts_repo, organization_id, "history-sibling")
    published = await versions_repo.create(
        make_version_row(organization_id, prompt.id, "1.0.0", status=PromptVersionStatus.PUBLISHED)
    )
    superseded = await versions_repo.create(
        make_version_row(organization_id, prompt.id, "0.9.0", status=PromptVersionStatus.SUPERSEDED)
    )
    draft = await versions_repo.create(
        make_version_row(organization_id, prompt.id, "1.1.0", status=PromptVersionStatus.DRAFT)
    )
    rolled_back = await versions_repo.create(
        make_version_row(
            organization_id, prompt.id, "1.2.0", status=PromptVersionStatus.ROLLED_BACK
        )
    )
    other = await versions_repo.create(
        make_version_row(organization_id, sibling.id, "1.0.0", status=PromptVersionStatus.PUBLISHED)
    )

    rows = await versions_repo.list_published(prompt.id)
    assert {row.id for row in rows} == {published.id, superseded.id}
    assert {draft.id, rolled_back.id, other.id}.isdisjoint({row.id for row in rows})


async def test_list_published_is_empty_for_a_prompt_that_never_shipped(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "never-shipped")
    await versions_repo.create(make_version_row(organization_id, prompt.id, "1.0.0"))
    assert await versions_repo.list_published(prompt.id) == []


# ---- the service-level factories exercise the same repositories -------------


async def test_make_published_leaves_exactly_one_current_revision(
    make_published: Any,
    versions_repo: PromptVersionRepository,
    db_session: AsyncSession,
) -> None:
    prompt, version = await make_published("factory-published")
    current = await versions_repo.get_current(prompt.id)
    assert current is not None
    assert current.id == version.id
    assert current.is_current is True
    assert isinstance(current.published_at, datetime)
    assert prompt.current_version_number == version.version_number
    assert db_session.is_active
