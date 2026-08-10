"""Repository tests for :mod:`app.repositories.analytics`.

Every query method is exercised against real PostgreSQL with both a row
that *should* match and a row that should *not*, so a filter that was
silently dropped fails here rather than in production.

Optimizations hang off a real revision (foreign keys are enforced);
statistics, reports, and audit rows are organization-scoped and stand
alone.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from shared_core.exceptions.not_found import NotFoundError

from app.models.analytics import PromptAudit, PromptOptimization, PromptReport, PromptStatistic
from app.models.enums import (
    AuditAction,
    OptimizationKind,
    OptimizationStatus,
    PromptType,
    ReportFormat,
    ReportKind,
    ReportStatus,
)
from app.models.prompt import Prompt, PromptVersion
from app.repositories.analytics import (
    PromptAuditRepository,
    PromptOptimizationRepository,
    PromptReportRepository,
    PromptStatisticRepository,
)
from app.repositories.prompt import PromptRepository, PromptVersionRepository
from tests.conftest import ago, utcnow


def one_minute() -> timedelta:
    return timedelta(minutes=1)


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


async def seed_optimization(
    repo: PromptOptimizationRepository,
    organization_id: uuid.UUID,
    prompt_version_id: uuid.UUID,
    **overrides: Any,
) -> PromptOptimization:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "prompt_version_id": prompt_version_id,
        "kind": OptimizationKind.TOKEN,
        "rationale": "Trim the redundant preamble.",
        "suggested_at": utcnow(),
    }
    fields.update(overrides)
    return await repo.create(PromptOptimization(**fields))


async def seed_statistic(
    repo: PromptStatisticRepository,
    organization_id: uuid.UUID,
    *,
    window_start: Any,
    **overrides: Any,
) -> PromptStatistic:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "window_start": window_start,
        "window_end": window_start + timedelta(hours=1),
    }
    fields.update(overrides)
    return await repo.create(PromptStatistic(**fields))


async def seed_report(
    repo: PromptReportRepository, organization_id: uuid.UUID, title: str, **overrides: Any
) -> PromptReport:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "kind": ReportKind.USAGE,
        "title": title,
    }
    fields.update(overrides)
    return await repo.create(PromptReport(**fields))


async def seed_audit(
    repo: PromptAuditRepository, organization_id: uuid.UUID, **overrides: Any
) -> PromptAudit:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "action": AuditAction.PROMPT_CREATED,
        "entity_type": "prompt",
        "occurred_at": utcnow(),
        "summary": "Something happened.",
    }
    fields.update(overrides)
    return await repo.create(PromptAudit(**fields))


# ---- PromptOptimizationRepository.require_in_org ----------------------------


async def test_optimization_require_in_org_never_returns_another_tenants_row(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    optimizations_repo: PromptOptimizationRepository,
    organization_id: uuid.UUID,
) -> None:
    other_org = uuid.uuid4()
    mine_version = await seed_version(
        versions_repo,
        organization_id,
        (await seed_prompt(prompts_repo, organization_id, "mine")).id,
    )
    theirs_version = await seed_version(
        versions_repo, other_org, (await seed_prompt(prompts_repo, other_org, "theirs")).id
    )
    mine = await seed_optimization(optimizations_repo, organization_id, mine_version.id)
    theirs = await seed_optimization(optimizations_repo, other_org, theirs_version.id)

    assert (await optimizations_repo.require_in_org(organization_id, mine.id)).id == mine.id
    assert (await optimizations_repo.require_in_org(other_org, theirs.id)).id == theirs.id

    with pytest.raises(NotFoundError):
        await optimizations_repo.require_in_org(organization_id, theirs.id)
    with pytest.raises(NotFoundError):
        await optimizations_repo.require_in_org(other_org, mine.id)
    with pytest.raises(NotFoundError):
        await optimizations_repo.require_in_org(organization_id, uuid.uuid4())


# ---- PromptOptimizationRepository.list_for_version --------------------------


async def test_optimization_list_for_version_is_newest_first_and_scoped(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    optimizations_repo: PromptOptimizationRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "suggested")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    sibling = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")

    oldest = await seed_optimization(
        optimizations_repo, organization_id, version.id, suggested_at=ago(300)
    )
    middle = await seed_optimization(
        optimizations_repo, organization_id, version.id, suggested_at=ago(200)
    )
    newest = await seed_optimization(
        optimizations_repo, organization_id, version.id, suggested_at=ago(100)
    )
    other = await seed_optimization(
        optimizations_repo, organization_id, sibling.id, suggested_at=ago(150)
    )

    rows = await optimizations_repo.list_for_version(version.id)
    assert [row.id for row in rows] == [newest.id, middle.id, oldest.id]
    assert other.id not in {row.id for row in rows}
    assert await optimizations_repo.list_for_version(uuid.uuid4()) == []


# ---- PromptOptimizationRepository.list_open ---------------------------------


async def test_list_open_returns_undecided_suggestions_by_descending_saving(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    optimizations_repo: PromptOptimizationRepository,
    organization_id: uuid.UUID,
) -> None:
    other_org = uuid.uuid4()
    version = await seed_version(
        versions_repo,
        organization_id,
        (await seed_prompt(prompts_repo, organization_id, "open")).id,
    )
    theirs_version = await seed_version(
        versions_repo, other_org, (await seed_prompt(prompts_repo, other_org, "theirs")).id
    )

    biggest = await seed_optimization(
        optimizations_repo,
        organization_id,
        version.id,
        status=OptimizationStatus.SUGGESTED,
        token_saving=500,
    )
    smallest = await seed_optimization(
        optimizations_repo,
        organization_id,
        version.id,
        status=OptimizationStatus.SUGGESTED,
        token_saving=10,
    )
    accepted = await seed_optimization(
        optimizations_repo,
        organization_id,
        version.id,
        status=OptimizationStatus.ACCEPTED,
        token_saving=9_999,
    )
    rejected = await seed_optimization(
        optimizations_repo,
        organization_id,
        version.id,
        status=OptimizationStatus.REJECTED,
        token_saving=9_999,
    )
    theirs = await seed_optimization(
        optimizations_repo,
        other_org,
        theirs_version.id,
        status=OptimizationStatus.SUGGESTED,
        token_saving=1_000,
    )

    rows = await optimizations_repo.list_open(organization_id)
    assert [row.id for row in rows] == [biggest.id, smallest.id]
    assert {accepted.id, rejected.id, theirs.id}.isdisjoint({row.id for row in rows})

    assert [row.id for row in await optimizations_repo.list_open(organization_id, limit=1)] == [
        biggest.id
    ]
    assert await optimizations_repo.list_open(uuid.uuid4()) == []


# ---- PromptOptimizationRepository.accepted_savings_in_window ----------------


async def test_accepted_savings_in_window_counts_accepted_only(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    optimizations_repo: PromptOptimizationRepository,
    organization_id: uuid.UUID,
) -> None:
    """Counting suggestions nobody took would report savings the
    organization never realised."""
    other_org = uuid.uuid4()
    version = await seed_version(
        versions_repo,
        organization_id,
        (await seed_prompt(prompts_repo, organization_id, "savings")).id,
    )
    theirs_version = await seed_version(
        versions_repo, other_org, (await seed_prompt(prompts_repo, other_org, "theirs")).id
    )
    since = ago(3_600)
    until = ago(1_800)

    await seed_optimization(
        optimizations_repo,
        organization_id,
        version.id,
        status=OptimizationStatus.ACCEPTED,
        decided_at=since,
        token_saving=40,
    )
    await seed_optimization(
        optimizations_repo,
        organization_id,
        version.id,
        status=OptimizationStatus.ACCEPTED,
        decided_at=ago(2_400),
        token_saving=60,
    )
    # Accepted but exactly at the exclusive edge, plus a merely suggested
    # one, a rejected one, an undecided one, and another tenant's.
    await seed_optimization(
        optimizations_repo,
        organization_id,
        version.id,
        status=OptimizationStatus.ACCEPTED,
        decided_at=until,
        token_saving=1_000,
    )
    await seed_optimization(
        optimizations_repo,
        organization_id,
        version.id,
        status=OptimizationStatus.SUGGESTED,
        decided_at=ago(2_400),
        token_saving=1_000,
    )
    await seed_optimization(
        optimizations_repo,
        organization_id,
        version.id,
        status=OptimizationStatus.REJECTED,
        decided_at=ago(2_400),
        token_saving=1_000,
    )
    await seed_optimization(
        optimizations_repo,
        organization_id,
        version.id,
        status=OptimizationStatus.ACCEPTED,
        decided_at=None,
        token_saving=1_000,
    )
    await seed_optimization(
        optimizations_repo,
        other_org,
        theirs_version.id,
        status=OptimizationStatus.ACCEPTED,
        decided_at=ago(2_400),
        token_saving=1_000,
    )

    assert (
        await optimizations_repo.accepted_savings_in_window(
            organization_id, since=since, until=until
        )
        == 100
    )
    assert (
        await optimizations_repo.accepted_savings_in_window(
            organization_id, since=ago(600), until=utcnow()
        )
        == 0
    )
    assert (
        await optimizations_repo.accepted_savings_in_window(
            uuid.uuid4(), since=since, until=until
        )
        == 0
    )


# ---- PromptStatisticRepository.latest ---------------------------------------


async def test_statistic_latest_is_the_most_recent_window_in_that_tenant(
    statistics_repo: PromptStatisticRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    await seed_statistic(statistics_repo, organization_id, window_start=ago(7_200))
    newest = await seed_statistic(statistics_repo, organization_id, window_start=ago(1_800))
    await seed_statistic(statistics_repo, organization_id, window_start=ago(3_600))
    theirs = await seed_statistic(statistics_repo, other_org, window_start=utcnow())

    latest = await statistics_repo.latest(organization_id)
    assert latest is not None
    assert latest.id == newest.id
    assert latest.id != theirs.id
    assert await statistics_repo.latest(uuid.uuid4()) is None


# ---- PromptStatisticRepository.list_since -----------------------------------


async def test_list_since_returns_windows_oldest_first(
    statistics_repo: PromptStatisticRepository, organization_id: uuid.UUID
) -> None:
    """The ordering is part of the contract -- a trend chart plots these
    in arrival order."""
    other_org = uuid.uuid4()
    since = ago(3_600)

    # Inserted deliberately out of order, so an unordered SELECT would be
    # very likely to hand them back in insertion order and fail here.
    third = await seed_statistic(statistics_repo, organization_id, window_start=ago(1_200))
    first = await seed_statistic(statistics_repo, organization_id, window_start=since)
    second = await seed_statistic(statistics_repo, organization_id, window_start=ago(2_400))
    before = await seed_statistic(statistics_repo, organization_id, window_start=ago(7_200))
    theirs = await seed_statistic(statistics_repo, other_org, window_start=ago(1_200))

    rows = await statistics_repo.list_since(organization_id, since=since)
    assert [row.id for row in rows] == [first.id, second.id, third.id]
    assert {before.id, theirs.id}.isdisjoint({row.id for row in rows})


async def test_list_since_is_empty_when_every_window_predates_the_cutoff(
    statistics_repo: PromptStatisticRepository, organization_id: uuid.UUID
) -> None:
    await seed_statistic(statistics_repo, organization_id, window_start=ago(7_200))
    assert await statistics_repo.list_since(organization_id, since=ago(3_600)) == []
    assert await statistics_repo.list_since(uuid.uuid4(), since=ago(86_400)) == []


# ---- PromptReportRepository.require_in_org ----------------------------------


async def test_report_require_in_org_never_returns_another_tenants_row(
    reports_repo: PromptReportRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    mine = await seed_report(reports_repo, organization_id, "Usage")
    theirs = await seed_report(reports_repo, other_org, "Usage")

    assert (await reports_repo.require_in_org(organization_id, mine.id)).id == mine.id
    assert (await reports_repo.require_in_org(other_org, theirs.id)).id == theirs.id

    with pytest.raises(NotFoundError):
        await reports_repo.require_in_org(organization_id, theirs.id)
    with pytest.raises(NotFoundError):
        await reports_repo.require_in_org(other_org, mine.id)
    with pytest.raises(NotFoundError):
        await reports_repo.require_in_org(organization_id, uuid.uuid4())


# ---- PromptReportRepository.list_for_org ------------------------------------


async def test_report_list_for_org_is_newest_first_and_filters_by_kind(
    reports_repo: PromptReportRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    oldest_usage = await seed_report(
        reports_repo, organization_id, "Old usage", kind=ReportKind.USAGE, created_at=ago(300)
    )
    newest_usage = await seed_report(
        reports_repo, organization_id, "New usage", kind=ReportKind.USAGE, created_at=ago(100)
    )
    security = await seed_report(
        reports_repo,
        organization_id,
        "Security",
        kind=ReportKind.SECURITY,
        report_format=ReportFormat.CSV,
        status=ReportStatus.COMPLETED,
        created_at=ago(200),
    )
    theirs = await seed_report(
        reports_repo, other_org, "Theirs", kind=ReportKind.USAGE, created_at=ago(150)
    )

    everything = await reports_repo.list_for_org(organization_id)
    assert [row.id for row in everything] == [newest_usage.id, security.id, oldest_usage.id]
    assert theirs.id not in {row.id for row in everything}

    usage_only = await reports_repo.list_for_org(organization_id, kind=ReportKind.USAGE)
    assert [row.id for row in usage_only] == [newest_usage.id, oldest_usage.id]
    assert security.id not in {row.id for row in usage_only}

    assert await reports_repo.list_for_org(organization_id, kind=ReportKind.COST) == []
    assert await reports_repo.list_for_org(uuid.uuid4()) == []


# ---- PromptAuditRepository.list_for_entity ----------------------------------


async def test_audit_list_for_entity_matches_both_type_and_id_newest_first(
    audit_repo: PromptAuditRepository, organization_id: uuid.UUID
) -> None:
    entity_id = uuid.uuid4()
    other_entity_id = uuid.uuid4()

    older = await seed_audit(
        audit_repo,
        organization_id,
        entity_type="prompt",
        entity_id=entity_id,
        occurred_at=ago(300),
    )
    newer = await seed_audit(
        audit_repo,
        organization_id,
        entity_type="prompt",
        entity_id=entity_id,
        occurred_at=ago(100),
    )
    same_id_other_type = await seed_audit(
        audit_repo,
        organization_id,
        entity_type="prompt_version",
        entity_id=entity_id,
        occurred_at=ago(200),
    )
    same_type_other_id = await seed_audit(
        audit_repo,
        organization_id,
        entity_type="prompt",
        entity_id=other_entity_id,
        occurred_at=ago(200),
    )

    rows = await audit_repo.list_for_entity("prompt", entity_id)
    assert [row.id for row in rows] == [newer.id, older.id]
    assert {same_id_other_type.id, same_type_other_id.id}.isdisjoint({row.id for row in rows})
    assert await audit_repo.list_for_entity("prompt", uuid.uuid4()) == []


# ---- PromptAuditRepository.list_for_org -------------------------------------


async def test_audit_list_for_org_is_newest_first_and_honours_limit(
    audit_repo: PromptAuditRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    oldest = await seed_audit(audit_repo, organization_id, occurred_at=ago(300))
    middle = await seed_audit(audit_repo, organization_id, occurred_at=ago(200))
    newest = await seed_audit(audit_repo, organization_id, occurred_at=ago(100))
    theirs = await seed_audit(audit_repo, other_org, occurred_at=ago(150))

    rows = await audit_repo.list_for_org(organization_id)
    assert [row.id for row in rows] == [newest.id, middle.id, oldest.id]
    assert theirs.id not in {row.id for row in rows}

    assert [row.id for row in await audit_repo.list_for_org(organization_id, limit=2)] == [
        newest.id,
        middle.id,
    ]
    assert await audit_repo.list_for_org(uuid.uuid4()) == []


# ---- PromptAuditRepository.count_by_action ----------------------------------


async def test_count_by_action_groups_by_action_from_the_cutoff_inclusive(
    audit_repo: PromptAuditRepository, organization_id: uuid.UUID
) -> None:
    other_org = uuid.uuid4()
    since = ago(3_600)

    await seed_audit(
        audit_repo, organization_id, action=AuditAction.PUBLISHED, occurred_at=since
    )
    await seed_audit(
        audit_repo, organization_id, action=AuditAction.PUBLISHED, occurred_at=ago(1_800)
    )
    await seed_audit(
        audit_repo, organization_id, action=AuditAction.ROLLED_BACK, occurred_at=ago(600)
    )
    # Just before the cutoff, and another tenant's row: neither counts.
    await seed_audit(
        audit_repo,
        organization_id,
        action=AuditAction.PUBLISHED,
        occurred_at=since - one_minute(),
    )
    await seed_audit(audit_repo, other_org, action=AuditAction.PUBLISHED, occurred_at=ago(600))

    assert await audit_repo.count_by_action(organization_id, since=since) == {
        "published": 2,
        "rolled_back": 1,
    }
    assert await audit_repo.count_by_action(organization_id, since=ago(300)) == {}
    assert await audit_repo.count_by_action(uuid.uuid4(), since=since) == {}
