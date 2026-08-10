"""Tests for :mod:`app.services.testing` -- prompt test cases and A/B
experiments.

Real PostgreSQL, real rendering. ``PromptTestingService`` renders through
the actual :class:`~app.services.rendering.RenderingService`, so a test
case here fails or passes for the same reason it would in production.

**What these tests can honestly claim.** This service holds no provider
credentials by design and cannot call a model, so a test case asserts on
the *rendered prompt*, not on a reply. That is a real constraint, and the
tests below reflect it: the assertion surface is template breakage,
missing variables, wording regressions, and forbidden patterns. Where a
caller has already obtained a model reply, it arrives as
``actual_output`` and the output assertions apply to that instead --
which is itself worth pinning, since silently asserting against the
prompt when the caller supplied an output would make every such test
vacuous.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio
from shared_core.exceptions.conflict import ConflictError

from app.abtesting import statistics
from app.models.enums import (
    AbTestArm,
    AbTestStatus,
    AuditAction,
    ExecutionStatus,
    VersionBump,
)

# Aliased away from their real names, per the convention every AI-IOS
# test module touching these two follows: pytest tries to *collect* any
# imported class whose name starts with "Test", and a StrEnum has a
# ``__new__`` it cannot instantiate, which turns into a collection error
# under this service's ``filterwarnings = error``.
from app.models.enums import TestKind as PromptTestKind
from app.models.enums import TestRunStatus as PromptTestRunStatus
from app.models.prompt import PromptVersion
from app.models.template import PromptVariable
from app.models.testing import PromptExecution, PromptTest
from app.repositories.analytics import PromptAuditRepository
from app.repositories.template import PromptVariableRepository
from app.repositories.testing import (
    PromptExecutionRepository,
    PromptTestRepository,
    PromptTestResultRepository,
)
from app.services.prompt import PromptService
from app.services.testing import AbTestingService, PromptTestingService, outcome_succeeded
from app.services.testing import TestOutcome as PromptTestOutcome
from tests.conftest import MakePromptFn, RecordingPublisher, ago

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def subject(
    make_prompt: MakePromptFn, variables_repo: PromptVariableRepository
) -> tuple[Any, PromptVersion]:
    """A prompt whose body is ``Hello {{ name }}``, with ``name`` declared."""
    prompt, version = await make_prompt("greeting")
    await variables_repo.create(
        PromptVariable(
            organization_id=version.organization_id,
            prompt_version_id=version.id,
            name="name",
        )
    )
    return prompt, version


@pytest.fixture
def define_test(testing_service: PromptTestingService, organization_id: uuid.UUID) -> Any:
    """Register one test case against a prompt."""

    async def _define(prompt_id: uuid.UUID, name: str = "case", **kwargs: Any) -> PromptTest:
        return await testing_service.define(
            organization_id=organization_id, prompt_id=prompt_id, name=name, **kwargs
        )

    return _define


# ---------------------------------------------------------------------------
# define()
# ---------------------------------------------------------------------------


async def test_define_stores_every_assertion_it_was_given(
    define_test: Any, subject: tuple[Any, PromptVersion], organization_id: uuid.UUID
) -> None:
    prompt, _version = subject

    test = await define_test(
        prompt.id,
        "full",
        kind=PromptTestKind.REGRESSION,
        variables={"name": "Ada"},
        expected_output="Hello Ada",
        expected_substrings=["Hello"],
        forbidden_substrings=["Goodbye"],
        minimum_score=0.5,
        description="A complete case.",
    )

    assert test.organization_id == organization_id
    assert test.prompt_id == prompt.id
    assert test.kind == PromptTestKind.REGRESSION
    assert test.variables == {"name": "Ada"}
    assert test.expected_output == "Hello Ada"
    assert test.expected_substrings == ["Hello"]
    assert test.forbidden_substrings == ["Goodbye"]
    assert test.minimum_score == 0.5
    assert test.description == "A complete case."


@pytest.mark.parametrize("minimum_score", [-0.01, 1.01, 2.0, -5.0])
async def test_define_refuses_a_threshold_outside_zero_to_one(
    define_test: Any, subject: tuple[Any, PromptVersion], minimum_score: float
) -> None:
    """The score is a ratio of satisfied assertions, so a threshold above
    1.0 could never be met and one below 0.0 could never fail -- either
    is a silently useless test case."""
    prompt, _version = subject

    with pytest.raises(ValueError, match=r"minimum_score must be within \[0.0, 1.0\]"):
        await define_test(prompt.id, "bad", minimum_score=minimum_score)


@pytest.mark.parametrize("minimum_score", [0.0, 0.5, 1.0])
async def test_define_accepts_both_ends_of_the_range(
    define_test: Any, subject: tuple[Any, PromptVersion], minimum_score: float
) -> None:
    prompt, _version = subject
    assert (await define_test(prompt.id, "ok", minimum_score=minimum_score)).minimum_score == (
        minimum_score
    )


async def test_define_defaults_the_collections_to_empty_not_null(
    define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    """``None`` in a JSON list column would make every downstream
    ``for s in test.expected_substrings`` a crash rather than a no-op."""
    prompt, _version = subject

    test = await define_test(prompt.id, "bare")

    assert test.variables == {}
    assert test.expected_substrings == []
    assert test.forbidden_substrings == []


# ---------------------------------------------------------------------------
# run() -- rendering and assertions
# ---------------------------------------------------------------------------


async def test_a_case_with_no_assertions_passes_on_rendering_alone(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    """Honest rather than flattering: the case asserted nothing and
    nothing failed, so the render succeeding *is* the assertion."""
    prompt, version = subject
    test = await define_test(prompt.id, "no-assertions", variables={"name": "Ada"})

    result = await testing_service.run(test, version)

    assert result.status == PromptTestRunStatus.PASSED
    assert result.score == 1.0
    assert result.failure_reasons == []
    assert result.rendered_prompt == "Hello Ada"


async def test_an_exact_output_match_passes(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    prompt, version = subject
    test = await define_test(
        prompt.id, "exact", variables={"name": "Ada"}, expected_output="Hello Ada"
    )

    assert (await testing_service.run(test, version)).status == PromptTestRunStatus.PASSED


async def test_an_exact_output_mismatch_fails_and_says_why(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    prompt, version = subject
    test = await define_test(
        prompt.id, "exact", variables={"name": "Ada"}, expected_output="Goodbye Ada"
    )

    result = await testing_service.run(test, version)

    assert result.status == PromptTestRunStatus.FAILED
    assert any("does not match the expected output" in reason for reason in result.failure_reasons)


async def test_exact_matching_ignores_surrounding_whitespace(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    """A trailing newline in a template is a formatting detail, not a
    wording regression."""
    prompt, version = subject
    test = await define_test(
        prompt.id, "padded", variables={"name": "Ada"}, expected_output="  Hello Ada\n"
    )

    assert (await testing_service.run(test, version)).status == PromptTestRunStatus.PASSED


async def test_a_missing_expected_substring_fails_and_names_it(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    prompt, version = subject
    test = await define_test(
        prompt.id, "substrings", variables={"name": "Ada"}, expected_substrings=["Greetings"]
    )

    result = await testing_service.run(test, version)

    assert result.status == PromptTestRunStatus.FAILED
    assert any("'Greetings'" in reason for reason in result.failure_reasons)


async def test_a_present_forbidden_substring_fails_and_names_it(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    """The check that catches an injection phrase or a leaked internal
    hostname reaching a rendered prompt."""
    prompt, version = subject
    test = await define_test(
        prompt.id, "forbidden", variables={"name": "Ada"}, forbidden_substrings=["Hello"]
    )

    result = await testing_service.run(test, version)

    assert result.status == PromptTestRunStatus.FAILED
    assert any("forbidden content" in reason for reason in result.failure_reasons)


async def test_only_the_first_three_offending_substrings_are_named(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    """A failure reason listing forty substrings is unreadable, and the
    column it lands in is bounded."""
    prompt, version = subject
    test = await define_test(
        prompt.id,
        "many",
        variables={"name": "Ada"},
        expected_substrings=[f"absent-{index}" for index in range(10)],
        minimum_score=0.0,
    )

    result = await testing_service.run(test, version)

    missing_reason = next(r for r in result.failure_reasons if "Missing expected" in r)
    assert missing_reason.count("absent-") == 3


async def test_a_render_failure_is_errored_not_failed(
    testing_service: PromptTestingService,
    define_test: Any,
    make_prompt: MakePromptFn,
) -> None:
    """The case never got to make its assertions. Reporting that as a
    content failure would send someone hunting for a wording problem that
    does not exist.

    An *undeclared* variable is what actually breaks a render here. A
    merely unsupplied one does not: runs go through
    ``RenderingService.preview``, which deliberately substitutes a
    ``<name>`` placeholder so authoring stays possible before every
    runtime value exists.
    """
    prompt, version = await make_prompt("undeclared", body="Hello {{ nobody_declared_me }}")
    test = await define_test(prompt.id, "unrenderable")

    result = await testing_service.run(test, version)

    assert result.status == PromptTestRunStatus.ERRORED
    assert result.score == 0.0
    assert result.rendered_prompt is None
    assert any("could not be rendered" in reason for reason in result.failure_reasons)


async def test_an_unsupplied_variable_renders_a_placeholder_rather_than_erroring(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    """The flip side, worth pinning because it is surprising: a case that
    supplies no variables still runs. Preview substitutes placeholders for
    declared variables, so the case measures the prompt's *shape*, and an
    ``expected_substrings`` assertion about the surrounding wording still
    means something."""
    prompt, version = subject
    test = await define_test(prompt.id, "no-variables", expected_substrings=["Hello"])

    result = await testing_service.run(test, version)

    assert result.status == PromptTestRunStatus.PASSED
    assert result.rendered_prompt == "Hello <name>"


async def test_a_supplied_actual_output_is_what_gets_asserted_on(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    """The pivot that makes this service useful to a caller who *did*
    call a model. Asserting against the prompt instead would make every
    such test vacuous -- it would pass whatever the model replied."""
    prompt, version = subject
    test = await define_test(
        prompt.id,
        "against-output",
        variables={"name": "Ada"},
        expected_substrings=["Paris"],
    )

    on_prompt = await testing_service.run(test, version)
    on_output = await testing_service.run(test, version, actual_output="The capital is Paris.")

    assert on_prompt.status == PromptTestRunStatus.FAILED
    assert on_output.status == PromptTestRunStatus.PASSED
    assert on_output.actual_output == "The capital is Paris."


async def test_the_rendered_prompt_is_recorded_even_when_asserting_on_an_output(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    """Both halves are needed to diagnose a failure: what was asked, and
    what came back."""
    prompt, version = subject
    test = await define_test(prompt.id, "both", variables={"name": "Ada"})

    result = await testing_service.run(test, version, actual_output="anything")

    assert result.rendered_prompt == "Hello Ada"
    assert result.actual_output == "anything"


async def test_a_run_records_who_ran_it_and_how_long_it_took(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    prompt, version = subject
    test = await define_test(prompt.id, "timed", variables={"name": "Ada"})

    result = await testing_service.run(test, version, run_by="ci-pipeline")

    assert result.run_by == "ci-pipeline"
    assert result.duration_ms >= 0.0
    assert result.prompt_version_id == version.id


async def test_a_run_updates_the_definitions_own_last_status(
    testing_service: PromptTestingService,
    tests_repo: PromptTestRepository,
    define_test: Any,
    subject: tuple[Any, PromptVersion],
) -> None:
    """The dashboard reads the definition, not the result history, so a
    stale ``last_status`` would show a red case as green."""
    prompt, version = subject
    test = await define_test(
        prompt.id, "tracked", variables={"name": "Ada"}, expected_output="wrong"
    )

    await testing_service.run(test, version)

    reloaded = await tests_repo.require_by_id(test.id)
    assert reloaded.last_status == PromptTestRunStatus.FAILED
    assert reloaded.last_run_at is not None


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


async def test_the_score_is_the_share_of_assertions_that_held(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    """Two assertions declared, one broken, so 0.5 -- and 0.5 is below
    the 0.7 default, which adds the threshold reason on top."""
    prompt, version = subject
    test = await define_test(
        prompt.id,
        "half",
        variables={"name": "Ada"},
        expected_substrings=["Hello"],
        forbidden_substrings=["Ada"],
    )

    result = await testing_service.run(test, version)

    assert result.score == 0.5
    assert result.status == PromptTestRunStatus.FAILED
    assert any("below the 0.70 threshold" in reason for reason in result.failure_reasons)


async def test_a_lenient_threshold_lets_a_partial_pass_through(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    """A partial score still fails, because the broken assertion is
    itself a reason -- the threshold only controls whether a *further*
    reason is added."""
    prompt, version = subject
    test = await define_test(
        prompt.id,
        "lenient",
        variables={"name": "Ada"},
        expected_substrings=["Hello"],
        forbidden_substrings=["Ada"],
        minimum_score=0.5,
    )

    result = await testing_service.run(test, version)

    assert result.score == 0.5
    assert result.status == PromptTestRunStatus.FAILED
    assert not any("threshold" in reason for reason in result.failure_reasons)


async def test_the_score_never_goes_below_zero(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    """Every assertion broken is 0.0, not a negative number -- the score
    is reported as a ratio and a negative one would be meaningless."""
    prompt, version = subject
    test = await define_test(
        prompt.id,
        "all-broken",
        variables={"name": "Ada"},
        expected_output="nope",
        expected_substrings=["absent"],
        forbidden_substrings=["Hello"],
        minimum_score=0.0,
    )

    result = await testing_service.run(test, version)

    assert result.score == 0.0


# ---------------------------------------------------------------------------
# Snapshot testing
# ---------------------------------------------------------------------------


async def test_a_snapshot_case_with_no_snapshot_yet_passes(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    """The first run is what establishes the baseline; failing it would
    mean a snapshot case could never be introduced."""
    prompt, version = subject
    test = await define_test(
        prompt.id, "first-run", kind=PromptTestKind.SNAPSHOT, variables={"name": "Ada"}
    )

    assert (await testing_service.run(test, version)).status == PromptTestRunStatus.PASSED


async def test_a_matching_snapshot_passes(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    prompt, version = subject
    test = await define_test(
        prompt.id, "snap", kind=PromptTestKind.SNAPSHOT, variables={"name": "Ada"}
    )
    await testing_service.accept_snapshot(test, "Hello Ada")

    assert (await testing_service.run(test, version)).status == PromptTestRunStatus.PASSED


async def test_a_drifted_snapshot_fails(
    testing_service: PromptTestingService,
    prompt_service: PromptService,
    define_test: Any,
    subject: tuple[Any, PromptVersion],
) -> None:
    """The entire point: the wording changed and nobody said it should."""
    prompt, _version = subject
    test = await define_test(
        prompt.id, "snap", kind=PromptTestKind.SNAPSHOT, variables={"name": "Ada"}
    )
    await testing_service.accept_snapshot(test, "Hello Ada")

    revised = await prompt_service.add_version(
        prompt, body="Greetings {{ name }}", component=VersionBump.MINOR
    )
    result = await testing_service.run(test, revised)

    assert result.status == PromptTestRunStatus.FAILED
    assert any("differs from the accepted snapshot" in r for r in result.failure_reasons)


async def test_a_snapshot_is_only_checked_for_a_snapshot_kind_case(
    testing_service: PromptTestingService,
    prompt_service: PromptService,
    define_test: Any,
    subject: tuple[Any, PromptVersion],
) -> None:
    """``kind`` is what opts a case into snapshot comparison, so a stored
    snapshot on an automated case must not silently start failing it."""
    prompt, _version = subject
    test = await define_test(
        prompt.id, "not-a-snapshot", kind=PromptTestKind.AUTOMATED, variables={"name": "Ada"}
    )
    await testing_service.accept_snapshot(test, "something else entirely")

    revised = await prompt_service.add_version(
        prompt, body="Greetings {{ name }}", component=VersionBump.MINOR
    )
    assert (await testing_service.run(test, revised)).status == PromptTestRunStatus.PASSED


async def test_accepting_a_snapshot_is_explicit_not_automatic(
    testing_service: PromptTestingService,
    tests_repo: PromptTestRepository,
    define_test: Any,
    subject: tuple[Any, PromptVersion],
) -> None:
    """A snapshot that updated itself on every run would pass forever and
    detect nothing."""
    prompt, version = subject
    test = await define_test(
        prompt.id, "snap", kind=PromptTestKind.SNAPSHOT, variables={"name": "Ada"}
    )

    await testing_service.run(test, version)
    assert (await tests_repo.require_by_id(test.id)).snapshot is None

    await testing_service.accept_snapshot(test, "Hello Ada")
    assert (await tests_repo.require_by_id(test.id)).snapshot == "Hello Ada"


# ---------------------------------------------------------------------------
# run_all()
# ---------------------------------------------------------------------------


async def test_run_all_runs_every_enabled_case(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    prompt, version = subject
    await define_test(prompt.id, "a", variables={"name": "Ada"})
    await define_test(prompt.id, "b", variables={"name": "Ada"})

    results = await testing_service.run_all(prompt.id, version)

    assert len(results) == 2
    assert all(r.status == PromptTestRunStatus.PASSED for r in results)


async def test_run_all_skips_a_disabled_case(
    testing_service: PromptTestingService,
    tests_repo: PromptTestRepository,
    define_test: Any,
    subject: tuple[Any, PromptVersion],
) -> None:
    prompt, version = subject
    await define_test(prompt.id, "enabled", variables={"name": "Ada"})
    disabled = await define_test(prompt.id, "disabled", variables={"name": "Ada"})
    disabled.enabled = False
    await tests_repo.update(disabled)

    results = await testing_service.run_all(prompt.id, version)

    assert len(results) == 1
    assert results[0].prompt_test_id != disabled.id


async def test_run_all_continues_past_a_failing_case(
    testing_service: PromptTestingService, define_test: Any, subject: tuple[Any, PromptVersion]
) -> None:
    """A caller preparing a publish wants the whole picture; stopping at
    the first failure would hide the other four."""
    prompt, version = subject
    await define_test(prompt.id, "a-broken", variables={"name": "Ada"}, expected_output="x")
    await define_test(prompt.id, "b-passing", variables={"name": "Ada"})

    results = await testing_service.run_all(prompt.id, version)

    assert {r.status for r in results} == {PromptTestRunStatus.FAILED, PromptTestRunStatus.PASSED}


async def test_run_all_returns_nothing_for_a_prompt_with_no_cases(
    testing_service: PromptTestingService, subject: tuple[Any, PromptVersion]
) -> None:
    prompt, version = subject
    assert await testing_service.run_all(prompt.id, version) == []


async def test_run_all_never_touches_another_prompts_cases(
    testing_service: PromptTestingService,
    define_test: Any,
    subject: tuple[Any, PromptVersion],
    make_prompt: MakePromptFn,
) -> None:
    prompt, version = subject
    other, _other_version = await make_prompt("unrelated")
    await define_test(prompt.id, "mine", variables={"name": "Ada"})
    await define_test(other.id, "theirs", variables={"name": "Ada"})

    results = await testing_service.run_all(prompt.id, version)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# AbTestingService.start
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def two_versions(
    make_prompt: MakePromptFn, prompt_service: PromptService
) -> tuple[Any, PromptVersion, PromptVersion]:
    """A prompt with two distinct revisions, ready to be split."""
    prompt, control = await make_prompt("split-me")
    variant = await prompt_service.add_version(
        prompt, body="Hi {{ name }}", component=VersionBump.MINOR
    )
    return prompt, control, variant


async def test_start_opens_a_running_experiment(
    ab_service: AbTestingService,
    two_versions: tuple[Any, PromptVersion, PromptVersion],
    organization_id: uuid.UUID,
) -> None:
    prompt, control, variant = two_versions

    experiment = await ab_service.start(
        organization_id=organization_id,
        prompt_id=prompt.id,
        name="wording",
        control=control,
        variant=variant,
        variant_weight=0.25,
        minimum_samples_per_arm=50,
        significance_level=0.01,
        auto_promote=True,
    )

    assert experiment.status == AbTestStatus.RUNNING
    assert experiment.control_version_id == control.id
    assert experiment.variant_version_id == variant.id
    assert experiment.variant_weight == 0.25
    assert experiment.minimum_samples_per_arm == 50
    assert experiment.significance_level == 0.01
    assert experiment.auto_promote is True
    assert experiment.started_at is not None


async def test_start_refuses_to_split_a_revision_against_itself(
    ab_service: AbTestingService,
    two_versions: tuple[Any, PromptVersion, PromptVersion],
    organization_id: uuid.UUID,
) -> None:
    """Identical arms would produce a p-value measuring nothing but
    sampling noise, reported as if it meant something."""
    prompt, control, _variant = two_versions

    with pytest.raises(ConflictError, match="must be different revisions"):
        await ab_service.start(
            organization_id=organization_id,
            prompt_id=prompt.id,
            name="self",
            control=control,
            variant=control,
        )


@pytest.mark.parametrize("weight", [-0.1, 1.1, 2.0])
async def test_start_refuses_a_weight_outside_zero_to_one(
    ab_service: AbTestingService,
    two_versions: tuple[Any, PromptVersion, PromptVersion],
    organization_id: uuid.UUID,
    weight: float,
) -> None:
    prompt, control, variant = two_versions

    with pytest.raises(ValueError, match=r"variant_weight must be within \[0, 1\]"):
        await ab_service.start(
            organization_id=organization_id,
            prompt_id=prompt.id,
            name="bad-weight",
            control=control,
            variant=variant,
            variant_weight=weight,
        )


async def test_start_refuses_a_second_concurrent_experiment_on_one_prompt(
    ab_service: AbTestingService,
    two_versions: tuple[Any, PromptVersion, PromptVersion],
    organization_id: uuid.UUID,
) -> None:
    """Two concurrent splits contaminate each other's control arm and
    neither result would mean anything."""
    prompt, control, variant = two_versions
    await ab_service.start(
        organization_id=organization_id,
        prompt_id=prompt.id,
        name="first",
        control=control,
        variant=variant,
    )

    with pytest.raises(ConflictError, match="already running on this prompt"):
        await ab_service.start(
            organization_id=organization_id,
            prompt_id=prompt.id,
            name="second",
            control=control,
            variant=variant,
        )


async def test_a_concluded_experiment_frees_the_prompt_for_a_new_one(
    ab_service: AbTestingService,
    two_versions: tuple[Any, PromptVersion, PromptVersion],
    organization_id: uuid.UUID,
) -> None:
    """The one-at-a-time rule is about *concurrency*, not a lifetime
    limit -- iterating on wording means running experiment after
    experiment."""
    prompt, control, variant = two_versions
    first = await ab_service.start(
        organization_id=organization_id,
        prompt_id=prompt.id,
        name="first",
        control=control,
        variant=variant,
    )
    await ab_service.cancel(first, reason="superseded")

    second = await ab_service.start(
        organization_id=organization_id,
        prompt_id=prompt.id,
        name="second",
        control=control,
        variant=variant,
    )
    assert second.status == AbTestStatus.RUNNING


# ---------------------------------------------------------------------------
# assign / record_outcome / reconcile
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def experiment(
    ab_service: AbTestingService,
    two_versions: tuple[Any, PromptVersion, PromptVersion],
    organization_id: uuid.UUID,
) -> Any:
    prompt, control, variant = two_versions
    return await ab_service.start(
        organization_id=organization_id,
        prompt_id=prompt.id,
        name="live",
        control=control,
        variant=variant,
        minimum_samples_per_arm=10,
    )


@pytest.mark.parametrize(
    ("weight", "roll", "expected"),
    [
        (0.5, 0.0, AbTestArm.VARIANT),
        (0.5, 0.49, AbTestArm.VARIANT),
        (0.5, 0.5, AbTestArm.CONTROL),
        (0.5, 0.99, AbTestArm.CONTROL),
        (0.0, 0.0, AbTestArm.CONTROL),
        (1.0, 0.99, AbTestArm.VARIANT),
    ],
)
async def test_assign_routes_by_the_supplied_draw(
    ab_service: AbTestingService, experiment: Any, weight: float, roll: float, expected: AbTestArm
) -> None:
    """``assign`` takes the random draw rather than generating one, which
    is what keeps routing a pure function a test can pin exactly."""
    experiment.variant_weight = weight
    assert ab_service.assign(experiment, roll) == expected


async def test_record_outcome_increments_the_named_arm_only(
    ab_service: AbTestingService, experiment: Any
) -> None:
    await ab_service.record_outcome(experiment, arm=AbTestArm.CONTROL, succeeded=True)
    await ab_service.record_outcome(experiment, arm=AbTestArm.CONTROL, succeeded=False)
    await ab_service.record_outcome(experiment, arm=AbTestArm.VARIANT, succeeded=True)

    assert experiment.control_executions == 2
    assert experiment.control_successes == 1
    assert experiment.variant_executions == 1
    assert experiment.variant_successes == 1


async def test_reconcile_recounts_both_arms_from_the_execution_rows(
    ab_service: AbTestingService,
    executions_repo: PromptExecutionRepository,
    experiment: Any,
    two_versions: tuple[Any, PromptVersion, PromptVersion],
    organization_id: uuid.UUID,
) -> None:
    """The cached counters exist so a scheduled decision does not scan
    every execution. A winner called from drifted counters would be wrong
    in a way nobody would notice."""
    prompt, control, variant = two_versions
    experiment.control_executions = 999
    experiment.control_successes = 999

    for arm, version, succeeded in (
        (AbTestArm.CONTROL, control, True),
        (AbTestArm.CONTROL, control, False),
        (AbTestArm.VARIANT, variant, True),
    ):
        await executions_repo.create(
            PromptExecution(
                organization_id=organization_id,
                prompt_id=prompt.id,
                prompt_version_id=version.id,
                ab_test_id=experiment.id,
                ab_arm=arm,
                status=ExecutionStatus.SUCCEEDED if succeeded else ExecutionStatus.FAILED,
                executed_at=ago(60),
            )
        )

    reconciled = await ab_service.reconcile(experiment)

    assert reconciled.control_executions == 2
    assert reconciled.control_successes == 1
    assert reconciled.variant_executions == 1
    assert reconciled.variant_successes == 1


async def test_reconcile_zeroes_an_arm_with_no_execution_rows(
    ab_service: AbTestingService, experiment: Any
) -> None:
    """Counters that survived a reconcile against an empty table would be
    exactly the drift reconciling exists to remove."""
    experiment.variant_executions = 42
    experiment.variant_successes = 40

    reconciled = await ab_service.reconcile(experiment)

    assert reconciled.variant_executions == 0
    assert reconciled.variant_successes == 0


# ---------------------------------------------------------------------------
# evaluate / conclude
# ---------------------------------------------------------------------------


async def _seed_arms(
    repo: PromptExecutionRepository,
    experiment: Any,
    prompt_id: uuid.UUID,
    control: PromptVersion,
    variant: PromptVersion,
    organization_id: uuid.UUID,
    *,
    control_successes: int,
    variant_successes: int,
    samples: int = 10,
) -> None:
    for arm, version, successes in (
        (AbTestArm.CONTROL, control, control_successes),
        (AbTestArm.VARIANT, variant, variant_successes),
    ):
        for index in range(samples):
            await repo.create(
                PromptExecution(
                    organization_id=organization_id,
                    prompt_id=prompt_id,
                    prompt_version_id=version.id,
                    ab_test_id=experiment.id,
                    ab_arm=arm,
                    status=(
                        ExecutionStatus.SUCCEEDED if index < successes else ExecutionStatus.FAILED
                    ),
                    executed_at=ago(60),
                )
            )


async def test_evaluate_declines_before_both_arms_reach_the_horizon(
    ab_service: AbTestingService,
    executions_repo: PromptExecutionRepository,
    experiment: Any,
    two_versions: tuple[Any, PromptVersion, PromptVersion],
    organization_id: uuid.UUID,
) -> None:
    """Peeking at a fixed-horizon test and stopping as soon as it looks
    significant is the classic way to manufacture false positives."""
    prompt, control, variant = two_versions
    await _seed_arms(
        executions_repo,
        experiment,
        prompt.id,
        control,
        variant,
        organization_id,
        control_successes=0,
        variant_successes=3,
        samples=3,
    )

    result = await ab_service.evaluate(experiment)

    assert result.significant is False
    assert "of the 10 executions required" in result.reason


async def test_evaluate_calls_a_significant_variant_win(
    ab_service: AbTestingService,
    executions_repo: PromptExecutionRepository,
    experiment: Any,
    two_versions: tuple[Any, PromptVersion, PromptVersion],
    organization_id: uuid.UUID,
) -> None:
    prompt, control, variant = two_versions
    await _seed_arms(
        executions_repo,
        experiment,
        prompt.id,
        control,
        variant,
        organization_id,
        control_successes=0,
        variant_successes=10,
    )

    result = await ab_service.evaluate(experiment)

    assert result.significant is True
    assert result.variant_wins is True
    assert result.difference > 0


async def test_evaluate_can_skip_reconciling(ab_service: AbTestingService, experiment: Any) -> None:
    """The counters are trusted when the caller says so -- useful for a
    dashboard read that must not scan the execution table."""
    experiment.control_executions = 10
    experiment.control_successes = 0
    experiment.variant_executions = 10
    experiment.variant_successes = 10

    result = await ab_service.evaluate(experiment, reconcile=False)

    assert result.significant is True
    assert result.variant_wins is True


async def test_conclude_records_the_verdict_and_the_winner(
    ab_service: AbTestingService,
    audit_repo: PromptAuditRepository,
    experiment: Any,
    organization_id: uuid.UUID,
) -> None:
    result = statistics.evaluate_experiment(
        statistics.ArmResult(10, 0),
        statistics.ArmResult(10, 10),
        minimum_samples_per_arm=10,
    )

    concluded = await ab_service.conclude(experiment, result, decided_by="analyst")

    assert concluded.status == AbTestStatus.COMPLETED
    assert concluded.is_significant is True
    assert concluded.winner == AbTestArm.VARIANT
    assert concluded.p_value == result.p_value
    assert concluded.decision_notes == result.reason
    assert concluded.completed_at is not None

    actions = [str(row.action) for row in await audit_repo.list_for_org(organization_id)]
    assert str(AuditAction.AB_TEST_DECIDED) in actions


async def test_conclude_names_the_control_arm_when_control_won(
    ab_service: AbTestingService, experiment: Any
) -> None:
    result = statistics.evaluate_experiment(
        statistics.ArmResult(10, 10),
        statistics.ArmResult(10, 0),
        minimum_samples_per_arm=10,
    )

    concluded = await ab_service.conclude(experiment, result)

    assert concluded.winner == AbTestArm.CONTROL
    assert result.variant_wins is False


async def test_conclude_leaves_an_inconclusive_experiment_without_a_winner(
    ab_service: AbTestingService, experiment: Any
) -> None:
    """Picking the higher-scoring arm anyway would be reading noise as
    signal."""
    result = statistics.evaluate_experiment(
        statistics.ArmResult(10, 5),
        statistics.ArmResult(10, 6),
        minimum_samples_per_arm=10,
    )

    concluded = await ab_service.conclude(experiment, result)

    assert concluded.status == AbTestStatus.COMPLETED
    assert concluded.is_significant is False
    assert concluded.winner is None


async def test_an_inconclusive_conclusion_is_audited_as_unsuccessful(
    ab_service: AbTestingService,
    audit_repo: PromptAuditRepository,
    experiment: Any,
    organization_id: uuid.UUID,
) -> None:
    """``succeeded`` tracks whether the experiment *reached a verdict*,
    which is what someone auditing "did we learn anything?" needs."""
    result = statistics.evaluate_experiment(
        statistics.ArmResult(10, 5), statistics.ArmResult(10, 5), minimum_samples_per_arm=10
    )

    await ab_service.conclude(experiment, result)

    row = next(
        r
        for r in await audit_repo.list_for_org(organization_id)
        if r.action == AuditAction.AB_TEST_DECIDED
    )
    assert row.succeeded is False


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------


async def test_cancel_abandons_a_running_experiment_without_a_winner(
    ab_service: AbTestingService, experiment: Any
) -> None:
    cancelled = await ab_service.cancel(experiment, reason="requirements changed")

    assert cancelled.status == AbTestStatus.CANCELLED
    assert cancelled.winner is None
    assert cancelled.decision_notes == "requirements changed"
    assert cancelled.completed_at is not None


async def test_cancel_refuses_an_experiment_that_is_not_running(
    ab_service: AbTestingService, experiment: Any
) -> None:
    """Cancelling a completed experiment would erase a recorded verdict."""
    await ab_service.cancel(experiment)

    with pytest.raises(ConflictError, match="not running"):
        await ab_service.cancel(experiment)


async def test_cancel_accepts_no_reason(ab_service: AbTestingService, experiment: Any) -> None:
    assert (await ab_service.cancel(experiment)).decision_notes is None


# ---------------------------------------------------------------------------
# outcome_succeeded
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ExecutionStatus.SUCCEEDED, True),
        (ExecutionStatus.FAILED, False),
        (ExecutionStatus.TIMED_OUT, False),
    ],
)
def test_outcome_succeeded_counts_only_a_success(status: ExecutionStatus, expected: bool) -> None:
    """A timeout is not a success. Counting it as one would inflate an
    arm's rate with executions that never produced an answer."""
    assert outcome_succeeded(status) is expected


# ---------------------------------------------------------------------------
# TestOutcome.passed
#
# ``TestOutcome`` is exported, so ``passed`` is part of this module's own
# public surface even though the router reads the persisted
# ``PromptTestResult.status`` instead. ERRORED is the case worth pinning:
# it is not PASSED, and a truthiness check on the status -- which is what
# a naive implementation would reach for, since these are StrEnums with
# non-empty values -- would wrongly call it passed.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (PromptTestRunStatus.PASSED, True),
        (PromptTestRunStatus.FAILED, False),
        (PromptTestRunStatus.ERRORED, False),
        (PromptTestRunStatus.PENDING, False),
    ],
)
def test_outcome_passed_is_true_only_for_passed(status: Any, expected: bool) -> None:
    assert PromptTestOutcome(status=status, score=1.0, rendered="anything").passed is expected


def test_outcome_is_frozen_so_a_reached_verdict_cannot_be_edited() -> None:
    outcome = PromptTestOutcome(
        status=PromptTestRunStatus.FAILED, score=0.0, rendered=None, failure_reasons=("why",)
    )

    assert outcome.failure_reasons == ("why",)
    with pytest.raises(AttributeError):
        outcome.score = 1.0  # type: ignore[misc]


def test_results_repository_is_wired_into_the_service(
    test_results_repo: PromptTestResultRepository,
) -> None:
    """A guard on the fixture wiring itself: if this repository were not
    the one the service writes through, every result assertion above
    would be reading a different table."""
    assert isinstance(test_results_repo, PromptTestResultRepository)


async def test_a_publisher_is_never_used_by_the_testing_service(
    testing_service: PromptTestingService,
    define_test: Any,
    subject: tuple[Any, PromptVersion],
    publisher: RecordingPublisher,
) -> None:
    """Running a test case is not a domain event. Announcing one would
    make a CI pipeline that runs the suite on every commit a firehose
    into the platform's event bus.

    Measured as a delta, not against an empty list: creating the fixture
    prompt legitimately published a ``PromptCreatedEvent``, so asserting
    on the total would be asserting about ``PromptService``.
    """
    prompt, version = subject
    test = await define_test(prompt.id, "quiet", variables={"name": "Ada"})
    before = list(publisher.names)

    await testing_service.run(test, version)
    await testing_service.run_all(prompt.id, version)
    await testing_service.accept_snapshot(test, "Hello Ada")

    assert publisher.names == before
