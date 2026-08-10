"""Repository tests for :mod:`app.repositories.testing`.

Every query method is exercised against real PostgreSQL with both a row
that *should* match and a row that should *not*, so a filter that was
silently dropped fails here rather than in production.

Tests, results, experiments, and executions all hang off real prompt
and revision rows -- foreign keys are enforced here, so an invented
UUID would be rejected rather than quietly stored.

``TestKind`` and ``TestRunStatus`` are imported under other names:
pytest collects any module-level class whose name starts with ``Test``,
and this service's own ``filterwarnings = ["error"]`` turns the
resulting collection warning into a hard error.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from shared_core.exceptions.not_found import NotFoundError

from app.models.enums import (
    AbTestArm,
    AbTestStatus,
    ExecutionStatus,
    PromptType,
)
from app.models.enums import TestKind as PromptTestKind
from app.models.enums import TestRunStatus as PromptTestRunStatus
from app.models.prompt import Prompt, PromptVersion
from app.models.testing import PromptAbTest, PromptExecution, PromptTest, PromptTestResult
from app.repositories.prompt import PromptRepository, PromptVersionRepository
from app.repositories.testing import (
    PromptAbTestRepository,
    PromptExecutionRepository,
    PromptTestRepository,
    PromptTestResultRepository,
)
from tests.conftest import ago, utcnow


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


async def seed_test(
    repo: PromptTestRepository,
    organization_id: uuid.UUID,
    prompt_id: uuid.UUID,
    name: str,
    **overrides: Any,
) -> PromptTest:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "prompt_id": prompt_id,
        "name": name,
    }
    fields.update(overrides)
    return await repo.create(PromptTest(**fields))


async def seed_result(
    repo: PromptTestResultRepository,
    organization_id: uuid.UUID,
    prompt_test_id: uuid.UUID,
    prompt_version_id: uuid.UUID,
    **overrides: Any,
) -> PromptTestResult:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "prompt_test_id": prompt_test_id,
        "prompt_version_id": prompt_version_id,
        "run_at": utcnow(),
    }
    fields.update(overrides)
    return await repo.create(PromptTestResult(**fields))


async def seed_ab_test(
    repo: PromptAbTestRepository,
    organization_id: uuid.UUID,
    prompt_id: uuid.UUID,
    control_version_id: uuid.UUID,
    variant_version_id: uuid.UUID,
    **overrides: Any,
) -> PromptAbTest:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "prompt_id": prompt_id,
        "name": "Wording experiment",
        "control_version_id": control_version_id,
        "variant_version_id": variant_version_id,
    }
    fields.update(overrides)
    return await repo.create(PromptAbTest(**fields))


async def seed_execution(
    repo: PromptExecutionRepository,
    organization_id: uuid.UUID,
    prompt_id: uuid.UUID,
    prompt_version_id: uuid.UUID,
    **overrides: Any,
) -> PromptExecution:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "prompt_id": prompt_id,
        "prompt_version_id": prompt_version_id,
        "executed_at": utcnow(),
    }
    fields.update(overrides)
    return await repo.create(PromptExecution(**fields))


# ---- PromptTestRepository.require_in_org ------------------------------------


async def test_test_require_in_org_never_returns_another_tenants_row(
    prompts_repo: PromptRepository,
    tests_repo: PromptTestRepository,
    organization_id: uuid.UUID,
) -> None:
    other_org = uuid.uuid4()
    mine_prompt = await seed_prompt(prompts_repo, organization_id, "mine")
    theirs_prompt = await seed_prompt(prompts_repo, other_org, "theirs")
    mine = await seed_test(tests_repo, organization_id, mine_prompt.id, "Greeting case")
    theirs = await seed_test(tests_repo, other_org, theirs_prompt.id, "Greeting case")

    assert (await tests_repo.require_in_org(organization_id, mine.id)).id == mine.id
    assert (await tests_repo.require_in_org(other_org, theirs.id)).id == theirs.id

    with pytest.raises(NotFoundError):
        await tests_repo.require_in_org(organization_id, theirs.id)
    with pytest.raises(NotFoundError):
        await tests_repo.require_in_org(other_org, mine.id)
    with pytest.raises(NotFoundError):
        await tests_repo.require_in_org(organization_id, uuid.uuid4())


# ---- PromptTestRepository.list_for_prompt / list_for_org --------------------


async def test_test_list_for_prompt_is_alphabetical_and_can_exclude_disabled(
    prompts_repo: PromptRepository,
    tests_repo: PromptTestRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "tested")
    sibling = await seed_prompt(prompts_repo, organization_id, "tested-sibling")

    zulu = await seed_test(tests_repo, organization_id, prompt.id, "Zulu case", enabled=True)
    alpha = await seed_test(tests_repo, organization_id, prompt.id, "Alpha case", enabled=True)
    disabled = await seed_test(
        tests_repo, organization_id, prompt.id, "Mike case", enabled=False
    )
    other = await seed_test(tests_repo, organization_id, sibling.id, "Alpha case")

    everything = await tests_repo.list_for_prompt(prompt.id)
    assert [row.id for row in everything] == [alpha.id, disabled.id, zulu.id]
    assert other.id not in {row.id for row in everything}

    enabled_only = await tests_repo.list_for_prompt(prompt.id, enabled_only=True)
    assert [row.id for row in enabled_only] == [alpha.id, zulu.id]
    assert disabled.id not in {row.id for row in enabled_only}

    assert await tests_repo.list_for_prompt(uuid.uuid4()) == []


async def test_test_list_for_org_is_newest_first_and_honours_limit_and_offset(
    prompts_repo: PromptRepository,
    tests_repo: PromptTestRepository,
    organization_id: uuid.UUID,
) -> None:
    other_org = uuid.uuid4()
    prompt = await seed_prompt(prompts_repo, organization_id, "org-tests")
    theirs_prompt = await seed_prompt(prompts_repo, other_org, "their-tests")

    oldest = await seed_test(
        tests_repo, organization_id, prompt.id, "Oldest", created_at=ago(300)
    )
    middle = await seed_test(
        tests_repo, organization_id, prompt.id, "Middle", created_at=ago(200)
    )
    newest = await seed_test(
        tests_repo, organization_id, prompt.id, "Newest", created_at=ago(100)
    )
    theirs = await seed_test(
        tests_repo, other_org, theirs_prompt.id, "Theirs", created_at=ago(150)
    )

    listed = await tests_repo.list_for_org(organization_id)
    assert [row.id for row in listed] == [newest.id, middle.id, oldest.id]
    assert theirs.id not in {row.id for row in listed}

    assert [row.id for row in await tests_repo.list_for_org(organization_id, limit=2)] == [
        newest.id,
        middle.id,
    ]
    assert [
        row.id for row in await tests_repo.list_for_org(organization_id, limit=2, offset=1)
    ] == [middle.id, oldest.id]
    assert await tests_repo.list_for_org(organization_id, offset=3) == []
    assert await tests_repo.list_for_org(uuid.uuid4()) == []


# ---- PromptTestResultRepository.list_for_test / list_for_version ------------


async def test_result_list_for_test_is_newest_first_and_honours_limit(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    tests_repo: PromptTestRepository,
    test_results_repo: PromptTestResultRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "regression")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    case = await seed_test(tests_repo, organization_id, prompt.id, "Case")
    other_case = await seed_test(tests_repo, organization_id, prompt.id, "Other case")

    oldest = await seed_result(
        test_results_repo, organization_id, case.id, version.id, run_at=ago(300)
    )
    middle = await seed_result(
        test_results_repo, organization_id, case.id, version.id, run_at=ago(200)
    )
    newest = await seed_result(
        test_results_repo, organization_id, case.id, version.id, run_at=ago(100)
    )
    other = await seed_result(
        test_results_repo, organization_id, other_case.id, version.id, run_at=ago(150)
    )

    rows = await test_results_repo.list_for_test(case.id)
    assert [row.id for row in rows] == [newest.id, middle.id, oldest.id]
    assert other.id not in {row.id for row in rows}

    assert [row.id for row in await test_results_repo.list_for_test(case.id, limit=2)] == [
        newest.id,
        middle.id,
    ]
    assert await test_results_repo.list_for_test(uuid.uuid4()) == []


async def test_result_list_for_version_is_newest_first_and_scoped_to_one_revision(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    tests_repo: PromptTestRepository,
    test_results_repo: PromptTestResultRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "per-version")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    sibling = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")
    case = await seed_test(tests_repo, organization_id, prompt.id, "Case")

    older = await seed_result(
        test_results_repo, organization_id, case.id, version.id, run_at=ago(300)
    )
    newer = await seed_result(
        test_results_repo, organization_id, case.id, version.id, run_at=ago(100)
    )
    other = await seed_result(
        test_results_repo, organization_id, case.id, sibling.id, run_at=ago(200)
    )

    rows = await test_results_repo.list_for_version(version.id)
    assert [row.id for row in rows] == [newer.id, older.id]
    assert other.id not in {row.id for row in rows}
    assert await test_results_repo.list_for_version(uuid.uuid4()) == []


# ---- PromptTestResultRepository.count_failed_for_version --------------------


async def test_count_failed_for_version_counts_errored_alongside_failed(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    tests_repo: PromptTestRepository,
    test_results_repo: PromptTestResultRepository,
    organization_id: uuid.UUID,
) -> None:
    """A test that could not run has not demonstrated the revision is sound."""
    prompt = await seed_prompt(prompts_repo, organization_id, "failing")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    sibling = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")
    case = await seed_test(tests_repo, organization_id, prompt.id, "Case")

    for status in (PromptTestRunStatus.FAILED, PromptTestRunStatus.ERRORED):
        await seed_result(test_results_repo, organization_id, case.id, version.id, status=status)
    for status in (PromptTestRunStatus.PASSED, PromptTestRunStatus.PENDING, PromptTestRunStatus.RUNNING):
        await seed_result(test_results_repo, organization_id, case.id, version.id, status=status)
    await seed_result(
        test_results_repo,
        organization_id,
        case.id,
        sibling.id,
        status=PromptTestRunStatus.FAILED,
    )

    assert await test_results_repo.count_failed_for_version(version.id) == 2
    assert await test_results_repo.count_failed_for_version(sibling.id) == 1
    assert await test_results_repo.count_failed_for_version(uuid.uuid4()) == 0


async def test_count_failed_for_version_is_zero_when_everything_passed(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    tests_repo: PromptTestRepository,
    test_results_repo: PromptTestResultRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "all-green")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    case = await seed_test(
        tests_repo, organization_id, prompt.id, "Case", kind=PromptTestKind.REGRESSION
    )
    await seed_result(
        test_results_repo,
        organization_id,
        case.id,
        version.id,
        status=PromptTestRunStatus.PASSED,
        score=0.95,
    )

    assert await test_results_repo.count_failed_for_version(version.id) == 0


# ---- PromptAbTestRepository.require_in_org ----------------------------------


async def test_ab_test_require_in_org_never_returns_another_tenants_row(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    ab_tests_repo: PromptAbTestRepository,
    organization_id: uuid.UUID,
) -> None:
    other_org = uuid.uuid4()
    mine_prompt = await seed_prompt(prompts_repo, organization_id, "mine")
    mine_control = await seed_version(versions_repo, organization_id, mine_prompt.id, "1.0.0")
    mine_variant = await seed_version(versions_repo, organization_id, mine_prompt.id, "1.1.0")
    theirs_prompt = await seed_prompt(prompts_repo, other_org, "theirs")
    theirs_control = await seed_version(versions_repo, other_org, theirs_prompt.id, "1.0.0")
    theirs_variant = await seed_version(versions_repo, other_org, theirs_prompt.id, "1.1.0")

    mine = await seed_ab_test(
        ab_tests_repo, organization_id, mine_prompt.id, mine_control.id, mine_variant.id
    )
    theirs = await seed_ab_test(
        ab_tests_repo, other_org, theirs_prompt.id, theirs_control.id, theirs_variant.id
    )

    assert (await ab_tests_repo.require_in_org(organization_id, mine.id)).id == mine.id
    assert (await ab_tests_repo.require_in_org(other_org, theirs.id)).id == theirs.id

    with pytest.raises(NotFoundError):
        await ab_tests_repo.require_in_org(organization_id, theirs.id)
    with pytest.raises(NotFoundError):
        await ab_tests_repo.require_in_org(other_org, mine.id)
    with pytest.raises(NotFoundError):
        await ab_tests_repo.require_in_org(organization_id, uuid.uuid4())


# ---- PromptAbTestRepository.get_running_for_prompt --------------------------


async def test_get_running_for_prompt_returns_only_the_live_experiment(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    ab_tests_repo: PromptAbTestRepository,
    organization_id: uuid.UUID,
) -> None:
    """Two concurrent splits over one prompt would contaminate each other."""
    prompt = await seed_prompt(prompts_repo, organization_id, "split")
    sibling = await seed_prompt(prompts_repo, organization_id, "split-sibling")
    control = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    variant = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")
    sibling_control = await seed_version(versions_repo, organization_id, sibling.id, "1.0.0")
    sibling_variant = await seed_version(versions_repo, organization_id, sibling.id, "1.1.0")

    running = await seed_ab_test(
        ab_tests_repo,
        organization_id,
        prompt.id,
        control.id,
        variant.id,
        status=AbTestStatus.RUNNING,
    )
    for status in (
        AbTestStatus.DRAFT,
        AbTestStatus.COMPLETED,
        AbTestStatus.PROMOTED,
        AbTestStatus.CANCELLED,
    ):
        await seed_ab_test(
            ab_tests_repo, organization_id, prompt.id, control.id, variant.id, status=status
        )
    sibling_running = await seed_ab_test(
        ab_tests_repo,
        organization_id,
        sibling.id,
        sibling_control.id,
        sibling_variant.id,
        status=AbTestStatus.RUNNING,
    )

    found = await ab_tests_repo.get_running_for_prompt(prompt.id)
    assert found is not None
    assert found.id == running.id
    assert found.id != sibling_running.id
    assert await ab_tests_repo.get_running_for_prompt(uuid.uuid4()) is None


async def test_get_running_for_prompt_is_none_when_only_drafts_exist(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    ab_tests_repo: PromptAbTestRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "never-started")
    control = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    variant = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")
    await seed_ab_test(
        ab_tests_repo,
        organization_id,
        prompt.id,
        control.id,
        variant.id,
        status=AbTestStatus.DRAFT,
    )

    assert await ab_tests_repo.get_running_for_prompt(prompt.id) is None


# ---- PromptAbTestRepository.list_running / list_for_org ---------------------


async def test_list_running_is_oldest_start_first_across_every_tenant(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    ab_tests_repo: PromptAbTestRepository,
    organization_id: uuid.UUID,
) -> None:
    """The evaluation sweep is platform-wide, so this deliberately is not
    tenant-scoped -- ``list_for_org`` is the scoped read."""
    prompt = await seed_prompt(prompts_repo, organization_id, "sweeping")
    control = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    variant = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")

    second = await seed_ab_test(
        ab_tests_repo,
        organization_id,
        prompt.id,
        control.id,
        variant.id,
        status=AbTestStatus.RUNNING,
        started_at=ago(200),
    )
    first = await seed_ab_test(
        ab_tests_repo,
        organization_id,
        prompt.id,
        control.id,
        variant.id,
        status=AbTestStatus.RUNNING,
        started_at=ago(300),
    )
    stopped = await seed_ab_test(
        ab_tests_repo,
        organization_id,
        prompt.id,
        control.id,
        variant.id,
        status=AbTestStatus.COMPLETED,
        started_at=ago(400),
    )

    running_ids = [row.id for row in await ab_tests_repo.list_running()]
    assert running_ids.index(first.id) < running_ids.index(second.id)
    assert stopped.id not in running_ids

    assert len(await ab_tests_repo.list_running(limit=1)) == 1


async def test_ab_test_list_for_org_is_newest_first_and_honours_limit_and_offset(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    ab_tests_repo: PromptAbTestRepository,
    organization_id: uuid.UUID,
) -> None:
    other_org = uuid.uuid4()
    prompt = await seed_prompt(prompts_repo, organization_id, "listed")
    control = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    variant = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")
    theirs_prompt = await seed_prompt(prompts_repo, other_org, "theirs")
    theirs_control = await seed_version(versions_repo, other_org, theirs_prompt.id, "1.0.0")
    theirs_variant = await seed_version(versions_repo, other_org, theirs_prompt.id, "1.1.0")

    oldest = await seed_ab_test(
        ab_tests_repo,
        organization_id,
        prompt.id,
        control.id,
        variant.id,
        created_at=ago(300),
    )
    middle = await seed_ab_test(
        ab_tests_repo,
        organization_id,
        prompt.id,
        control.id,
        variant.id,
        created_at=ago(200),
    )
    newest = await seed_ab_test(
        ab_tests_repo,
        organization_id,
        prompt.id,
        control.id,
        variant.id,
        created_at=ago(100),
    )
    theirs = await seed_ab_test(
        ab_tests_repo,
        other_org,
        theirs_prompt.id,
        theirs_control.id,
        theirs_variant.id,
        created_at=ago(150),
    )

    listed = await ab_tests_repo.list_for_org(organization_id)
    assert [row.id for row in listed] == [newest.id, middle.id, oldest.id]
    assert theirs.id not in {row.id for row in listed}

    assert [row.id for row in await ab_tests_repo.list_for_org(organization_id, limit=2)] == [
        newest.id,
        middle.id,
    ]
    assert [
        row.id for row in await ab_tests_repo.list_for_org(organization_id, limit=2, offset=1)
    ] == [middle.id, oldest.id]
    assert await ab_tests_repo.list_for_org(uuid.uuid4()) == []


# ---- PromptExecutionRepository.list_for_prompt / list_for_version -----------


async def test_execution_list_for_prompt_is_newest_first_and_honours_limit(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    executions_repo: PromptExecutionRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "executed")
    sibling = await seed_prompt(prompts_repo, organization_id, "executed-sibling")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    sibling_version = await seed_version(versions_repo, organization_id, sibling.id, "1.0.0")

    oldest = await seed_execution(
        executions_repo, organization_id, prompt.id, version.id, executed_at=ago(300)
    )
    middle = await seed_execution(
        executions_repo, organization_id, prompt.id, version.id, executed_at=ago(200)
    )
    newest = await seed_execution(
        executions_repo, organization_id, prompt.id, version.id, executed_at=ago(100)
    )
    other = await seed_execution(
        executions_repo,
        organization_id,
        sibling.id,
        sibling_version.id,
        executed_at=ago(150),
    )

    rows = await executions_repo.list_for_prompt(prompt.id)
    assert [row.id for row in rows] == [newest.id, middle.id, oldest.id]
    assert other.id not in {row.id for row in rows}

    assert [row.id for row in await executions_repo.list_for_prompt(prompt.id, limit=2)] == [
        newest.id,
        middle.id,
    ]
    assert await executions_repo.list_for_prompt(uuid.uuid4()) == []


async def test_execution_list_for_version_is_newest_first_and_scoped_to_one_revision(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    executions_repo: PromptExecutionRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "per-revision")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    sibling = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")

    older = await seed_execution(
        executions_repo, organization_id, prompt.id, version.id, executed_at=ago(300)
    )
    newer = await seed_execution(
        executions_repo, organization_id, prompt.id, version.id, executed_at=ago(100)
    )
    other = await seed_execution(
        executions_repo, organization_id, prompt.id, sibling.id, executed_at=ago(200)
    )

    rows = await executions_repo.list_for_version(version.id)
    assert [row.id for row in rows] == [newer.id, older.id]
    assert other.id not in {row.id for row in rows}

    assert [row.id for row in await executions_repo.list_for_version(version.id, limit=1)] == [
        newer.id
    ]
    assert await executions_repo.list_for_version(uuid.uuid4()) == []


# ---- PromptExecutionRepository.list_in_window -------------------------------


async def test_execution_list_in_window_is_inclusive_of_since_and_exclusive_of_until(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    executions_repo: PromptExecutionRepository,
    organization_id: uuid.UUID,
) -> None:
    other_org = uuid.uuid4()
    prompt = await seed_prompt(prompts_repo, organization_id, "windowed")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    theirs_prompt = await seed_prompt(prompts_repo, other_org, "theirs")
    theirs_version = await seed_version(versions_repo, other_org, theirs_prompt.id, "1.0.0")
    since = ago(3_600)
    until = ago(1_800)

    at_since = await seed_execution(
        executions_repo, organization_id, prompt.id, version.id, executed_at=since
    )
    inside = await seed_execution(
        executions_repo, organization_id, prompt.id, version.id, executed_at=ago(2_400)
    )
    at_until = await seed_execution(
        executions_repo, organization_id, prompt.id, version.id, executed_at=until
    )
    before = await seed_execution(
        executions_repo, organization_id, prompt.id, version.id, executed_at=ago(7_200)
    )
    theirs = await seed_execution(
        executions_repo, other_org, theirs_prompt.id, theirs_version.id, executed_at=ago(2_400)
    )

    rows = await executions_repo.list_in_window(organization_id, since=since, until=until)
    assert {row.id for row in rows} == {at_since.id, inside.id}
    assert {at_until.id, before.id, theirs.id}.isdisjoint({row.id for row in rows})

    assert (
        await executions_repo.list_in_window(organization_id, since=ago(600), until=utcnow()) == []
    )


# ---- PromptExecutionRepository.arm_counts -----------------------------------


async def test_arm_counts_recounts_both_arms_and_ignores_unassigned_rows(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    ab_tests_repo: PromptAbTestRepository,
    executions_repo: PromptExecutionRepository,
    organization_id: uuid.UUID,
) -> None:
    """The authoritative recount the evaluation sweep reconciles the
    experiment's own cached counters against."""
    prompt = await seed_prompt(prompts_repo, organization_id, "counted-arms")
    control = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    variant = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")
    experiment = await seed_ab_test(
        ab_tests_repo,
        organization_id,
        prompt.id,
        control.id,
        variant.id,
        status=AbTestStatus.RUNNING,
    )
    other_experiment = await seed_ab_test(
        ab_tests_repo,
        organization_id,
        prompt.id,
        control.id,
        variant.id,
        status=AbTestStatus.RUNNING,
    )

    for status in (
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
    ):
        await seed_execution(
            executions_repo,
            organization_id,
            prompt.id,
            control.id,
            ab_test_id=experiment.id,
            ab_arm=AbTestArm.CONTROL,
            status=status,
        )
    for status in (ExecutionStatus.SUCCEEDED, ExecutionStatus.TIMED_OUT):
        await seed_execution(
            executions_repo,
            organization_id,
            prompt.id,
            variant.id,
            ab_test_id=experiment.id,
            ab_arm=AbTestArm.VARIANT,
            status=status,
        )
    # Routed into the experiment but never assigned an arm, and an
    # unrelated experiment's own traffic: neither may be counted.
    await seed_execution(
        executions_repo,
        organization_id,
        prompt.id,
        control.id,
        ab_test_id=experiment.id,
        ab_arm=None,
        status=ExecutionStatus.SUCCEEDED,
    )
    await seed_execution(
        executions_repo,
        organization_id,
        prompt.id,
        control.id,
        ab_test_id=other_experiment.id,
        ab_arm=AbTestArm.CONTROL,
        status=ExecutionStatus.SUCCEEDED,
    )

    assert await executions_repo.arm_counts(experiment.id) == {"control": (3, 2), "variant": (2, 1)}
    assert await executions_repo.arm_counts(other_experiment.id) == {"control": (1, 1)}


async def test_arm_counts_is_empty_for_an_experiment_with_no_traffic(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    ab_tests_repo: PromptAbTestRepository,
    executions_repo: PromptExecutionRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "no-traffic")
    control = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    variant = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")
    experiment = await seed_ab_test(
        ab_tests_repo, organization_id, prompt.id, control.id, variant.id
    )
    await seed_execution(
        executions_repo, organization_id, prompt.id, control.id, ab_test_id=None, ab_arm=None
    )

    assert await executions_repo.arm_counts(experiment.id) == {}
    assert await executions_repo.arm_counts(uuid.uuid4()) == {}
