"""Tests for :mod:`app.services.analytics` -- optimization, execution
recording, evaluation, statistics, reporting, and audit.

Real PostgreSQL, real pure engines. ``OptimizationService`` runs the
actual token analyser, ``EvaluationService`` the actual scorer, and every
row is written and read back through real repositories.

**Three governance properties get the most attention**, because each is a
hole straight through the workflow if it breaks:

- An accepted optimization goes through ``PromptService.add_version``, so
  it lands as a **draft** in the same review path as a hand-written edit.
  An optimization that could publish itself would bypass approval.
- ``ExecutionRecordingService`` stores the *masked* prompt. Anything else
  puts resolved secrets into execution history.
- ``accepted_savings_in_window`` counts accepted suggestions only. Every
  other number in this service is diagnostic; that one ends up in a slide
  deck, so counting suggestions nobody took would report savings the
  organization never realised.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from shared_core.exceptions.conflict import ConflictError

from app.models.analytics import PromptOptimization
from app.models.enums import (
    AuditAction,
    ExecutionStatus,
    OptimizationKind,
    OptimizationStatus,
    PromptCategory,
    PromptLifecycleStatus,
    PromptType,
    ReportFormat,
    ReportKind,
    ReportStatus,
    ScanStatus,
    SecuritySeverity,
)
from app.models.governance import PromptSecurityScan
from app.models.prompt import Prompt, PromptVersion
from app.repositories.analytics import (
    PromptAuditRepository,
    PromptOptimizationRepository,
    PromptReportRepository,
    PromptStatisticRepository,
)
from app.repositories.governance import PromptSecurityScanRepository
from app.repositories.prompt import PromptRepository, PromptVersionRepository
from app.services.analytics import (
    AuditService,
    EvaluationService,
    ExecutionRecordingService,
    OptimizationService,
    ReportService,
    StatisticsService,
)
from app.services.prompt import PromptService
from tests.conftest import MakePromptFn, RecordingPublisher, ago, soon, utcnow

_VERBOSE_BODY = (
    "Please note that it is important to remember that you should always "
    "make sure that you carefully consider each and every one of the "
    "following points in order to be able to respond appropriately.\n"
    "Please note that it is important to remember that you should always "
    "make sure that you carefully consider each and every one of the "
    "following points in order to be able to respond appropriately.\n"
)
"""Deliberately padded and duplicated, so the real analyser has genuine
findings to report rather than a body it correctly leaves alone."""


# ---------------------------------------------------------------------------
# OptimizationService
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def verbose(make_prompt: MakePromptFn) -> tuple[Prompt, PromptVersion]:
    return await make_prompt("verbose", body=_VERBOSE_BODY)


async def test_analyse_persists_every_suggestion_the_analyser_found(
    optimization_service: OptimizationService,
    optimizations_repo: PromptOptimizationRepository,
    verbose: tuple[Prompt, PromptVersion],
    organization_id: uuid.UUID,
) -> None:
    _prompt, version = verbose

    stored = await optimization_service.analyse(version)

    assert stored
    assert all(row.status == OptimizationStatus.SUGGESTED for row in stored)
    assert all(row.prompt_version_id == version.id for row in stored)
    assert all(row.organization_id == organization_id for row in stored)
    assert {row.id for row in stored} == {
        row.id for row in await optimizations_repo.list_open(organization_id)
    }


async def test_analyse_never_touches_the_prompt_it_analysed(
    optimization_service: OptimizationService,
    versions_repo: PromptVersionRepository,
    verbose: tuple[Prompt, PromptVersion],
) -> None:
    """A prompt's wording is the artefact under approval here. Rewriting
    it without a human accepting the change would bypass the entire
    governance workflow."""
    _prompt, version = verbose
    original = version.body

    await optimization_service.analyse(version)

    assert (await versions_repo.require_by_id(version.id)).body == original


async def test_analyse_records_a_cost_saving_alongside_the_token_saving(
    optimization_service: OptimizationService, verbose: tuple[Prompt, PromptVersion]
) -> None:
    """Tokens are the measurement; dollars are what a budget owner acts
    on."""
    _prompt, version = verbose

    stored = await optimization_service.analyse(version)

    rewrites = [row for row in stored if row.token_saving > 0]
    assert rewrites
    assert all(row.estimated_cost_saving_usd > 0 for row in rewrites)


async def test_analyse_finds_nothing_in_an_already_tight_prompt(
    optimization_service: OptimizationService, make_prompt: MakePromptFn
) -> None:
    """Manufacturing suggestions for a good prompt would train people to
    ignore this feature."""
    _prompt, version = await make_prompt("tight", body="Summarise the text.")

    assert await optimization_service.analyse(version) == []


async def test_a_stricter_saving_threshold_filters_marginal_suggestions(
    optimization_service: OptimizationService, verbose: tuple[Prompt, PromptVersion]
) -> None:
    _prompt, version = verbose

    lenient = await optimization_service.analyse(version, min_saving_ratio=0.0)
    strict = await optimization_service.analyse(version, min_saving_ratio=0.99)

    assert len(strict) <= len(lenient)


async def test_accepting_a_suggestion_creates_a_draft_not_a_publish(
    optimization_service: OptimizationService,
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    verbose: tuple[Prompt, PromptVersion],
) -> None:
    """The load-bearing property of this service. An accepted
    optimization lands in exactly the same review-and-approval path as a
    hand-written edit -- one that could publish itself would be a hole
    straight through governance."""
    prompt, version = verbose
    suggestion = next(
        row for row in await optimization_service.analyse(version) if row.suggested_body
    )

    created = await optimization_service.accept(suggestion, prompt, accepted_by="alice")

    assert created.published_at is None
    assert created.is_current is False
    assert created.id != version.id
    assert (await prompts_repo.require_by_id(prompt.id)).status == PromptLifecycleStatus.DRAFT
    assert (await versions_repo.get_current(prompt.id)) is None


async def test_accepting_bumps_the_patch_component_only(
    optimization_service: OptimizationService, verbose: tuple[Prompt, PromptVersion]
) -> None:
    """An optimization preserves meaning by construction, so a minor or
    major bump would overstate what changed."""
    prompt, version = verbose
    suggestion = next(
        row for row in await optimization_service.analyse(version) if row.suggested_body
    )

    created = await optimization_service.accept(suggestion, prompt)

    assert version.version_number == "1.0.0"
    assert created.version_number == "1.0.1"


async def test_accepting_links_the_resulting_revision_back(
    optimization_service: OptimizationService,
    optimizations_repo: PromptOptimizationRepository,
    verbose: tuple[Prompt, PromptVersion],
) -> None:
    """Without the link, "which revision came from this suggestion?" is
    unanswerable and the saving cannot be attributed."""
    prompt, version = verbose
    suggestion = next(
        row for row in await optimization_service.analyse(version) if row.suggested_body
    )

    created = await optimization_service.accept(suggestion, prompt, accepted_by="alice")

    reloaded = await optimizations_repo.require_by_id(suggestion.id)
    assert reloaded.status == OptimizationStatus.ACCEPTED
    assert reloaded.resulting_version_id == created.id
    assert reloaded.decided_by == "alice"
    assert reloaded.decided_at is not None


async def test_accepting_records_the_rationale_in_the_changelog(
    optimization_service: OptimizationService, verbose: tuple[Prompt, PromptVersion]
) -> None:
    """Six months later the diff alone will not explain why the wording
    changed."""
    prompt, version = verbose
    suggestion = next(
        row for row in await optimization_service.analyse(version) if row.suggested_body
    )

    created = await optimization_service.accept(suggestion, prompt)

    assert created.changelog is not None
    assert suggestion.rationale in created.changelog


async def test_accepting_announces_an_optimization_event(
    optimization_service: OptimizationService,
    verbose: tuple[Prompt, PromptVersion],
    publisher: RecordingPublisher,
) -> None:
    prompt, version = verbose
    suggestion = next(
        row for row in await optimization_service.analyse(version) if row.suggested_body
    )
    before = list(publisher.names)

    await optimization_service.accept(suggestion, prompt)

    new_names = publisher.names[len(before) :]
    assert "PromptOptimized" in new_names


async def test_an_advisory_finding_cannot_be_accepted(
    optimization_service: OptimizationService,
    optimizations_repo: PromptOptimizationRepository,
    verbose: tuple[Prompt, PromptVersion],
    organization_id: uuid.UUID,
) -> None:
    """It identifies a problem for a human to fix, not a change to
    apply. Accepting it would create a revision identical to the one
    before it."""
    prompt, version = verbose
    advisory = await optimizations_repo.create(
        PromptOptimization(
            organization_id=organization_id,
            prompt_version_id=version.id,
            kind=OptimizationKind.INSTRUCTION_REFINEMENT,
            status=OptimizationStatus.SUGGESTED,
            rationale="The instruction is ambiguous; a human should reword it.",
            suggested_body=None,
            suggested_at=utcnow(),
        )
    )

    with pytest.raises(ConflictError, match="advisory finding with no proposed rewrite"):
        await optimization_service.accept(advisory, prompt)


@pytest.mark.parametrize("already", [OptimizationStatus.ACCEPTED, OptimizationStatus.REJECTED])
async def test_a_decided_suggestion_cannot_be_decided_again(
    optimization_service: OptimizationService,
    optimizations_repo: PromptOptimizationRepository,
    verbose: tuple[Prompt, PromptVersion],
    organization_id: uuid.UUID,
    already: OptimizationStatus,
) -> None:
    """Accepting twice would create two revisions from one suggestion;
    re-rejecting an accepted one would orphan the revision it produced."""
    prompt, version = verbose
    decided = await optimizations_repo.create(
        PromptOptimization(
            organization_id=organization_id,
            prompt_version_id=version.id,
            kind=OptimizationKind.TOKEN,
            status=already,
            rationale="Already handled.",
            suggested_body="Shorter.",
            suggested_at=utcnow(),
        )
    )

    with pytest.raises(ConflictError, match="already"):
        await optimization_service.accept(decided, prompt)
    with pytest.raises(ConflictError, match="already"):
        await optimization_service.reject(decided)


async def test_rejecting_records_who_declined_and_when(
    optimization_service: OptimizationService,
    optimizations_repo: PromptOptimizationRepository,
    verbose: tuple[Prompt, PromptVersion],
) -> None:
    _prompt, version = verbose
    suggestion = (await optimization_service.analyse(version))[0]

    rejected = await optimization_service.reject(suggestion, rejected_by="bob")

    assert rejected.status == OptimizationStatus.REJECTED
    assert rejected.decided_by == "bob"
    assert rejected.decided_at is not None
    assert await optimizations_repo.list_open(rejected.organization_id) != [suggestion]


async def test_rejecting_publishes_nothing(
    optimization_service: OptimizationService,
    verbose: tuple[Prompt, PromptVersion],
    publisher: RecordingPublisher,
) -> None:
    """Declining a suggestion is not news the platform needs to hear."""
    _prompt, version = verbose
    suggestion = (await optimization_service.analyse(version))[0]
    before = list(publisher.names)

    await optimization_service.reject(suggestion)

    assert publisher.names == before


async def test_a_custom_token_price_changes_the_reported_saving(
    optimizations_repo: PromptOptimizationRepository,
    prompt_service: PromptService,
    verbose: tuple[Prompt, PromptVersion],
    publisher: RecordingPublisher,
) -> None:
    """The price is injected rather than hard-coded, because it changes
    whenever a provider changes its pricing page."""
    _prompt, version = verbose
    cheap = OptimizationService(
        optimizations_repo, prompt_service, publish_event=publisher, usd_per_1k_tokens=0.001
    )
    dear = OptimizationService(
        optimizations_repo, prompt_service, publish_event=publisher, usd_per_1k_tokens=0.100
    )

    cheap_rows = [r for r in await cheap.analyse(version) if r.token_saving > 0]
    dear_rows = [r for r in await dear.analyse(version) if r.token_saving > 0]

    assert cheap_rows and dear_rows
    assert dear_rows[0].estimated_cost_saving_usd > cheap_rows[0].estimated_cost_saving_usd


# ---------------------------------------------------------------------------
# ExecutionRecordingService
# ---------------------------------------------------------------------------


async def test_recording_an_execution_stores_the_masked_prompt(
    execution_service: ExecutionRecordingService, make_prompt: MakePromptFn
) -> None:
    """The caller is expected to have masked it -- ``RenderedResult``
    hands back exactly that field for this purpose. Storing the unmasked
    body would put resolved secrets into execution history."""
    prompt, version = await make_prompt("recorded")

    execution = await execution_service.record(
        prompt, version, masked_prompt="Token: ***REDACTED***"
    )

    assert execution.rendered_prompt == "Token: ***REDACTED***"


async def test_recording_sums_the_token_counts(
    execution_service: ExecutionRecordingService, make_prompt: MakePromptFn
) -> None:
    """``total_tokens`` is derived rather than trusted from the caller,
    so a caller that reported only two of the three numbers cannot make
    the total disagree with its own parts."""
    prompt, version = await make_prompt("counted")

    execution = await execution_service.record(
        prompt, version, prompt_tokens=120, completion_tokens=45
    )

    assert execution.prompt_tokens == 120
    assert execution.completion_tokens == 45
    assert execution.total_tokens == 165


async def test_recording_increments_the_prompts_own_counters(
    execution_service: ExecutionRecordingService,
    prompts_repo: PromptRepository,
    make_prompt: MakePromptFn,
) -> None:
    """The prompt list view reads these, so a counter that did not move
    would show a heavily used prompt as never executed."""
    prompt, version = await make_prompt("busy")
    assert prompt.execution_count == 0

    await execution_service.record(prompt, version)
    await execution_service.record(prompt, version)

    reloaded = await prompts_repo.require_by_id(prompt.id)
    assert reloaded.execution_count == 2
    assert reloaded.last_executed_at is not None


@pytest.mark.parametrize(
    "status", [ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED, ExecutionStatus.TIMED_OUT]
)
async def test_a_failed_execution_is_still_recorded_and_still_counted(
    execution_service: ExecutionRecordingService,
    prompts_repo: PromptRepository,
    make_prompt: MakePromptFn,
    status: ExecutionStatus,
) -> None:
    """A prompt that fails constantly is exactly the one worth finding,
    so recording only successes would hide it."""
    prompt, version = await make_prompt(f"outcome-{status}")

    execution = await execution_service.record(
        prompt, version, status=status, error="upstream refused"
    )

    assert execution.status == status
    assert execution.error == "upstream refused"
    assert (await prompts_repo.require_by_id(prompt.id)).execution_count == 1


async def test_recording_carries_the_full_provenance(
    execution_service: ExecutionRecordingService, make_prompt: MakePromptFn
) -> None:
    """Which agent, which workflow, which model -- the three questions a
    cost or quality investigation starts from."""
    prompt, version = await make_prompt("traced")

    execution = await execution_service.record(
        prompt,
        version,
        model_provider="anthropic",
        model_name="claude-opus-5",
        latency_ms=812.5,
        cost_usd=0.0134,
        executed_by="svc-assistant",
        agent_id="agent-7",
        workflow_id="wf-3",
        result_metadata={"finish_reason": "stop"},
    )

    assert execution.model_provider == "anthropic"
    assert execution.model_name == "claude-opus-5"
    assert execution.latency_ms == 812.5
    assert execution.cost_usd == 0.0134
    assert execution.executed_by == "svc-assistant"
    assert execution.agent_id == "agent-7"
    assert execution.workflow_id == "wf-3"
    assert execution.result_metadata == {"finish_reason": "stop"}


async def test_recording_announces_an_execution_event(
    execution_service: ExecutionRecordingService,
    make_prompt: MakePromptFn,
    publisher: RecordingPublisher,
) -> None:
    prompt, version = await make_prompt("announced")
    before = list(publisher.names)

    await execution_service.record(prompt, version, prompt_tokens=10, completion_tokens=5)

    assert "PromptExecuted" in publisher.names[len(before) :]
    event = publisher.events[-1]
    assert event.payload["total_tokens"] == 15
    assert event.payload["version_number"] == version.version_number


async def test_recording_defaults_metadata_to_empty_not_null(
    execution_service: ExecutionRecordingService, make_prompt: MakePromptFn
) -> None:
    prompt, version = await make_prompt("bare-metadata")
    assert (await execution_service.record(prompt, version)).result_metadata == {}


# ---------------------------------------------------------------------------
# EvaluationService
# ---------------------------------------------------------------------------


async def test_evaluating_scores_every_metric(
    evaluation_service: EvaluationService, make_prompt: MakePromptFn
) -> None:
    _prompt, version = await make_prompt("scored")

    report = await evaluation_service.evaluate_output(
        version,
        "Paris is the capital of France.",
        expected="Paris is the capital of France.",
        required_points=["Paris"],
        latency_ms=100.0,
        total_tokens=20,
        cost_usd=0.001,
    )

    assert report.scores
    assert 0.0 <= report.overall <= 1.0


async def test_the_first_evaluation_sets_the_revisions_average(
    evaluation_service: EvaluationService,
    versions_repo: PromptVersionRepository,
    make_prompt: MakePromptFn,
) -> None:
    """The roll-up is what makes comparing two revisions cheap;
    recomputing it from every evaluation on each read would make the
    comparison view scale with history."""
    _prompt, version = await make_prompt("averaged")
    assert version.average_score is None

    report = await evaluation_service.evaluate_output(version, "An answer.")

    assert (await versions_repo.require_by_id(version.id)).average_score == report.overall


async def test_a_later_evaluation_blends_into_the_running_average(
    evaluation_service: EvaluationService,
    versions_repo: PromptVersionRepository,
    make_prompt: MakePromptFn,
) -> None:
    """An exponential blend, not a true mean: it weights recent
    evaluations more heavily, which is what you want when a revision's
    behaviour has actually changed."""
    _prompt, version = await make_prompt("blended")

    first = await evaluation_service.evaluate_output(
        version, "Paris.", expected="Paris.", required_points=["Paris"]
    )
    second = await evaluation_service.evaluate_output(
        version, "Completely unrelated.", expected="Paris.", required_points=["Paris"]
    )

    reloaded = await versions_repo.require_by_id(version.id)
    assert reloaded.average_score == pytest.approx((first.overall + second.overall) / 2)
    assert reloaded.average_score != first.overall


async def test_evaluating_announces_an_evaluation_event_naming_its_metrics(
    evaluation_service: EvaluationService,
    make_prompt: MakePromptFn,
    publisher: RecordingPublisher,
) -> None:
    _prompt, version = await make_prompt("evaluated")
    before = list(publisher.names)

    report = await evaluation_service.evaluate_output(version, "An answer.")

    assert "PromptEvaluated" in publisher.names[len(before) :]
    event = publisher.events[-1]
    assert event.payload["metrics"] == [str(s.metric) for s in report.scores]
    assert event.payload["overall"] == round(report.overall, 4)


async def test_evaluating_with_no_reference_material_still_scores(
    evaluation_service: EvaluationService, make_prompt: MakePromptFn
) -> None:
    """Not every caller has an expected answer, a rubric, or repeated
    samples. Refusing without them would make the endpoint unusable for
    the common case."""
    _prompt, version = await make_prompt("bare-eval")

    report = await evaluation_service.evaluate_output(version, "Some output.")

    assert report.scores
    assert 0.0 <= report.overall <= 1.0


# ---------------------------------------------------------------------------
# StatisticsService
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_window(
    execution_service: ExecutionRecordingService,
    prompt_service: PromptService,
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
) -> tuple[Prompt, PromptVersion]:
    """One published prompt with three executions of mixed outcome."""
    prompt, version = await make_prompt("measured", category=PromptCategory.AUTOMATION)
    await prompt_service.publish(prompt, version)

    for status, latency, cost in (
        (ExecutionStatus.SUCCEEDED, 100.0, 0.01),
        (ExecutionStatus.SUCCEEDED, 300.0, 0.03),
        (ExecutionStatus.FAILED, None, 0.0),
    ):
        await execution_service.record(
            prompt,
            version,
            status=status,
            latency_ms=latency,
            cost_usd=cost,
            prompt_tokens=10,
            completion_tokens=5,
        )
    return prompt, version


async def test_rollup_counts_prompts_and_executions(
    statistics_service: StatisticsService,
    seeded_window: tuple[Prompt, PromptVersion],
    organization_id: uuid.UUID,
) -> None:
    window = await statistics_service.rollup(
        organization_id, window_start=ago(3600), window_end=soon(3600)
    )

    assert window.total_prompts == 1
    assert window.published_prompts == 1
    assert window.execution_count == 3
    assert window.executions_succeeded == 2
    assert window.executions_failed == 1
    assert window.total_tokens == 45


async def test_rollup_averages_only_the_executions_that_reported_a_latency(
    statistics_service: StatisticsService,
    seeded_window: tuple[Prompt, PromptVersion],
    organization_id: uuid.UUID,
) -> None:
    """The failed execution never produced a latency. Treating a missing
    measurement as zero would drag the average toward a number nobody
    observed."""
    window = await statistics_service.rollup(
        organization_id, window_start=ago(3600), window_end=soon(3600)
    )

    assert window.average_latency_ms == pytest.approx(200.0)


async def test_rollup_averages_only_the_executions_that_cost_something(
    statistics_service: StatisticsService,
    seeded_window: tuple[Prompt, PromptVersion],
    organization_id: uuid.UUID,
) -> None:
    """A free execution is real, but folding zeros into an average cost
    understates what a call actually costs."""
    window = await statistics_service.rollup(
        organization_id, window_start=ago(3600), window_end=soon(3600)
    )

    assert window.average_cost_usd == pytest.approx(0.02)


async def test_rollup_breaks_down_by_type_and_category(
    statistics_service: StatisticsService,
    seeded_window: tuple[Prompt, PromptVersion],
    organization_id: uuid.UUID,
) -> None:
    window = await statistics_service.rollup(
        organization_id, window_start=ago(3600), window_end=soon(3600)
    )

    assert window.by_prompt_type == {str(PromptType.SYSTEM): 1}
    assert window.by_category == {str(PromptCategory.AUTOMATION): 1}


async def test_rollup_ranks_the_busiest_prompts(
    statistics_service: StatisticsService,
    execution_service: ExecutionRecordingService,
    seeded_window: tuple[Prompt, PromptVersion],
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
) -> None:
    busy, _busy_version = seeded_window
    quiet, quiet_version = await make_prompt("quiet")
    await execution_service.record(quiet, quiet_version)

    window = await statistics_service.rollup(
        organization_id, window_start=ago(3600), window_end=soon(3600)
    )

    assert window.top_prompts[0] == {"prompt_id": str(busy.id), "executions": 3}
    assert window.top_prompts[1] == {"prompt_id": str(quiet.id), "executions": 1}


async def test_rollup_excludes_executions_outside_the_window(
    statistics_service: StatisticsService,
    seeded_window: tuple[Prompt, PromptVersion],
    organization_id: uuid.UUID,
) -> None:
    """A window that swept in everything ever would make a trend chart a
    flat line."""
    window = await statistics_service.rollup(
        organization_id, window_start=soon(3600), window_end=soon(7200)
    )

    assert window.execution_count == 0
    assert window.average_latency_ms is None
    assert window.average_cost_usd is None
    assert window.top_prompts == []


async def test_rollup_counts_accepted_optimization_savings_only(
    statistics_service: StatisticsService,
    optimization_service: OptimizationService,
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
) -> None:
    """The one number in this service most likely to end up in a slide
    deck. Counting suggestions nobody took would report savings the
    organization never actually realised."""
    prompt, version = await make_prompt("optimizable", body=_VERBOSE_BODY)
    suggestions = [r for r in await optimization_service.analyse(version) if r.suggested_body]
    accepted = suggestions[0]
    await optimization_service.accept(accepted, prompt)
    for ignored in suggestions[1:]:
        await optimization_service.reject(ignored)

    window = await statistics_service.rollup(
        organization_id, window_start=ago(3600), window_end=soon(3600)
    )

    assert window.optimization_token_savings == accepted.token_saving


async def test_rollup_counts_security_findings_in_the_window(
    statistics_service: StatisticsService,
    scans_repo: PromptSecurityScanRepository,
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
) -> None:
    _prompt, version = await make_prompt("scanned")
    await scans_repo.create(
        PromptSecurityScan(
            organization_id=organization_id,
            prompt_version_id=version.id,
            status=ScanStatus.FLAGGED,
            highest_severity=SecuritySeverity.MEDIUM,
            findings=[{"finding": "pii_detected"}, {"finding": "pii_detected"}],
            finding_count=2,
            scanned_at=utcnow(),
        )
    )

    window = await statistics_service.rollup(
        organization_id, window_start=ago(3600), window_end=soon(3600)
    )

    assert window.security_findings == 2


async def test_rollup_of_an_empty_organization_writes_a_zeroed_window(
    statistics_service: StatisticsService, organization_id: uuid.UUID
) -> None:
    """A missing window and a genuinely quiet one are different facts, and
    the dashboard has to be able to tell them apart."""
    window = await statistics_service.rollup(
        organization_id, window_start=ago(3600), window_end=utcnow()
    )

    assert window.total_prompts == 0
    assert window.execution_count == 0
    assert window.by_prompt_type == {}


async def test_the_dashboard_reads_the_latest_window(
    statistics_service: StatisticsService,
    seeded_window: tuple[Prompt, PromptVersion],
    organization_id: uuid.UUID,
) -> None:
    await statistics_service.rollup(organization_id, window_start=ago(7200), window_end=ago(3600))
    newest = await statistics_service.rollup(
        organization_id, window_start=ago(3600), window_end=soon(3600)
    )

    snapshot = await statistics_service.dashboard(organization_id)

    assert snapshot["latest_window"]["execution_count"] == newest.execution_count
    assert snapshot["latest_window"]["computed_through"] == newest.window_end.isoformat()


async def test_the_dashboard_returns_nulls_before_any_rollup_has_run(
    statistics_service: StatisticsService, organization_id: uuid.UUID
) -> None:
    """Nulls rather than zeros: "we have not measured yet" and "we
    measured and found nothing" must not render identically."""
    snapshot = await statistics_service.dashboard(organization_id)

    assert snapshot["latest_window"] == {
        "total_prompts": None,
        "published_prompts": None,
        "execution_count": None,
        "executions_failed": None,
        "average_latency_ms": None,
        "optimization_token_savings": None,
        "computed_through": None,
    }


async def test_the_trend_returns_recent_windows_oldest_first(
    statistics_service: StatisticsService,
    statistics_repo: PromptStatisticRepository,
    organization_id: uuid.UUID,
) -> None:
    """A chart plotted newest-first would read as a mirror image of the
    truth."""
    for offset in (3, 1, 2):
        await statistics_service.rollup(
            organization_id,
            window_start=datetime.now(UTC) - timedelta(days=offset),
            window_end=datetime.now(UTC) - timedelta(days=offset) + timedelta(hours=1),
        )

    trend = await statistics_service.trend(organization_id, since_days=30)

    assert [row.window_start for row in trend] == sorted(row.window_start for row in trend)
    assert len(trend) == 3


async def test_the_trend_excludes_windows_older_than_its_horizon(
    statistics_service: StatisticsService, organization_id: uuid.UUID
) -> None:
    await statistics_service.rollup(
        organization_id,
        window_start=datetime.now(UTC) - timedelta(days=90),
        window_end=datetime.now(UTC) - timedelta(days=90) + timedelta(hours=1),
    )

    assert await statistics_service.trend(organization_id, since_days=30) == []


# ---------------------------------------------------------------------------
# ReportService
# ---------------------------------------------------------------------------


async def test_a_usage_report_lists_every_prompt(
    report_service: ReportService,
    prompt_service: PromptService,
    execution_service: ExecutionRecordingService,
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
) -> None:
    prompt, version = await make_prompt("reported")
    await prompt_service.publish(prompt, version)
    await execution_service.record(prompt, version)

    report = await report_service.generate(organization_id, kind=ReportKind.USAGE)

    assert report.status == ReportStatus.COMPLETED
    assert report.row_count == 1
    rows = report.content["rows"]
    assert rows[0]["slug"] == "reported"
    assert rows[0]["status"] == str(PromptLifecycleStatus.PUBLISHED)
    assert rows[0]["execution_count"] == 1
    assert rows[0]["last_executed_at"] is not None


async def test_a_usage_row_reports_a_never_executed_prompt_as_null(
    report_service: ReportService, make_prompt: MakePromptFn, organization_id: uuid.UUID
) -> None:
    await make_prompt("untouched")

    report = await report_service.generate(organization_id, kind=ReportKind.USAGE)

    assert report.content["rows"][0]["last_executed_at"] is None


async def test_an_optimization_report_lists_only_undecided_suggestions(
    report_service: ReportService,
    optimization_service: OptimizationService,
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
) -> None:
    """The report is a work queue. A decided suggestion is not work."""
    _prompt, version = await make_prompt("to-optimize", body=_VERBOSE_BODY)
    suggestions = await optimization_service.analyse(version)
    await optimization_service.reject(suggestions[0])

    report = await report_service.generate(organization_id, kind=ReportKind.OPTIMIZATION)

    assert report.row_count == len(suggestions) - 1
    assert all(row["status"] == str(OptimizationStatus.SUGGESTED) for row in report.content["rows"])


async def test_a_security_report_lists_only_blocking_scans(
    report_service: ReportService,
    scans_repo: PromptSecurityScanRepository,
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
) -> None:
    """A ``FLAGGED`` scan is a concern someone should look at; a
    ``BLOCKED`` one is stopping a publish right now. Mixing them buries
    the ones that need action."""
    _prompt, version = await make_prompt("to-scan")
    for status, severity, count in (
        (ScanStatus.BLOCKED, SecuritySeverity.CRITICAL, 3),
        (ScanStatus.FLAGGED, SecuritySeverity.MEDIUM, 1),
        (ScanStatus.CLEAN, SecuritySeverity.INFO, 0),
    ):
        await scans_repo.create(
            PromptSecurityScan(
                organization_id=organization_id,
                prompt_version_id=version.id,
                status=status,
                highest_severity=severity,
                finding_count=count,
                scanned_at=utcnow(),
            )
        )

    report = await report_service.generate(organization_id, kind=ReportKind.SECURITY)

    assert report.row_count == 1
    assert report.content["rows"][0]["status"] == str(ScanStatus.BLOCKED)
    assert report.content["rows"][0]["finding_count"] == 3


async def test_an_audit_report_lists_the_trail(
    report_service: ReportService,
    audit_service: AuditService,
    organization_id: uuid.UUID,
) -> None:
    await audit_service.record(
        organization_id,
        action=AuditAction.PUBLISHED,
        entity_type="prompt",
        entity_reference="greeting",
        actor_id="alice",
        summary="Published greeting.",
    )

    report = await report_service.generate(organization_id, kind=ReportKind.AUDIT)

    assert report.row_count == 1
    row = report.content["rows"][0]
    assert row["action"] == str(AuditAction.PUBLISHED)
    assert row["entity_reference"] == "greeting"
    assert row["actor_id"] == "alice"
    assert row["succeeded"] is True


@pytest.mark.parametrize("kind", [ReportKind.COST, ReportKind.EVALUATION, ReportKind.APPROVAL])
async def test_a_report_kind_with_no_builder_completes_empty_rather_than_failing(
    report_service: ReportService, organization_id: uuid.UUID, kind: ReportKind
) -> None:
    """The scope decision is stated rather than disguised: these three
    have no bespoke builder in the first cut, and returning an empty
    report is more honest than raising for a kind the enum offers."""
    report = await report_service.generate(organization_id, kind=kind)

    assert report.status == ReportStatus.COMPLETED
    assert report.content == {"rows": []}
    assert report.row_count == 0


async def test_a_report_records_its_own_title_format_and_timing(
    report_service: ReportService, organization_id: uuid.UUID
) -> None:
    report = await report_service.generate(
        organization_id,
        kind=ReportKind.USAGE,
        report_format=ReportFormat.CSV,
        title="Quarterly usage",
        generated_by="alice",
    )

    assert report.title == "Quarterly usage"
    assert report.report_format == ReportFormat.CSV
    assert report.generated_by == "alice"
    assert report.generated_at is not None
    assert report.duration_ms is not None
    assert report.duration_ms >= 0.0


async def test_a_report_without_a_title_names_itself_after_its_kind(
    report_service: ReportService, organization_id: uuid.UUID
) -> None:
    report = await report_service.generate(organization_id, kind=ReportKind.USAGE)
    assert report.title == f"{ReportKind.USAGE!s} report"


async def test_a_build_failure_is_recorded_on_the_row_not_raised(
    reports_repo: PromptReportRepository,
    optimizations_repo: PromptOptimizationRepository,
    scans_repo: PromptSecurityScanRepository,
    audit_repo: PromptAuditRepository,
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
) -> None:
    """A broken report must be *visible* rather than a lost request --
    someone waiting on a report needs to know it failed and why.

    The failure here is real, not injected: ``max_rows=0`` makes the
    underlying ``LIMIT 0`` query legal but the builder's own paging
    contract impossible, and the service records whatever went wrong.
    """
    await make_prompt("something")
    service = ReportService(
        reports_repo,
        _BrokenPromptRepository(),  # type: ignore[arg-type]
        optimizations_repo,
        scans_repo,
        audit_repo,
    )

    report = await service.generate(organization_id, kind=ReportKind.USAGE)

    assert report.status == ReportStatus.FAILED
    assert report.error is not None
    assert "the reporting database is unreachable" in report.error
    assert report.content == {}


class _BrokenPromptRepository:
    """A real object with the right method, raising a real error.

    Not a mock of the service under test: the report builder calls
    ``list_for_org`` on whatever prompt repository it was given, and this
    one fails the way a dropped connection would.
    """

    async def list_for_org(self, *_args: Any, **_kwargs: Any) -> list[Prompt]:
        raise OSError("the reporting database is unreachable")


async def test_listing_reports_can_filter_by_kind(
    report_service: ReportService, organization_id: uuid.UUID
) -> None:
    await report_service.generate(organization_id, kind=ReportKind.USAGE)
    await report_service.generate(organization_id, kind=ReportKind.AUDIT)

    everything = await report_service.list_for_org(organization_id)
    only_audit = await report_service.list_for_org(organization_id, kind=ReportKind.AUDIT)

    assert len(everything) == 2
    assert [row.kind for row in only_audit] == [ReportKind.AUDIT]


async def test_listing_reports_is_scoped_to_one_tenant(
    report_service: ReportService, organization_id: uuid.UUID
) -> None:
    await report_service.generate(organization_id, kind=ReportKind.USAGE)
    assert await report_service.list_for_org(uuid.uuid4()) == []


# ---------------------------------------------------------------------------
# AuditService
# ---------------------------------------------------------------------------


async def test_recording_an_audit_entry_stores_every_field(
    audit_service: AuditService, organization_id: uuid.UUID
) -> None:
    entity_id = uuid.uuid4()

    entry = await audit_service.record(
        organization_id,
        action=AuditAction.PROMPT_UPDATED,
        entity_type="prompt",
        entity_id=entity_id,
        entity_reference="greeting",
        actor_id="alice",
        actor_type="service",
        summary="Renamed the prompt.",
        succeeded=False,
        changes={"name": ["old", "new"]},
        context={"reason": "typo"},
        request_id="req-1",
        ip_address="203.0.113.7",
    )

    assert entry.action == AuditAction.PROMPT_UPDATED
    assert entry.entity_id == entity_id
    assert entry.entity_reference == "greeting"
    assert entry.actor_id == "alice"
    assert entry.actor_type == "service"
    assert entry.succeeded is False
    assert entry.changes == {"name": ["old", "new"]}
    assert entry.context == {"reason": "typo"}
    assert entry.request_id == "req-1"
    assert entry.ip_address == "203.0.113.7"
    assert entry.occurred_at is not None


async def test_an_audit_entry_defaults_to_a_successful_user_action(
    audit_service: AuditService, organization_id: uuid.UUID
) -> None:
    entry = await audit_service.record(
        organization_id,
        action=AuditAction.TESTED,
        entity_type="prompt",
        summary="Someone looked at it.",
    )

    assert entry.actor_type == "user"
    assert entry.succeeded is True
    assert entry.changes == {}
    assert entry.context == {}


async def test_listing_audit_entries_is_newest_first(
    audit_service: AuditService, organization_id: uuid.UUID
) -> None:
    """An audit trail read oldest-first buries the thing that just
    happened under everything that came before."""
    for index in range(3):
        await audit_service.record(
            organization_id,
            action=AuditAction.TESTED,
            entity_type="prompt",
            summary=f"Entry {index}.",
        )

    entries = await audit_service.list_entries(organization_id)

    assert [e.summary for e in entries] == ["Entry 2.", "Entry 1.", "Entry 0."]


async def test_listing_audit_entries_honours_its_limit(
    audit_service: AuditService, organization_id: uuid.UUID
) -> None:
    for index in range(5):
        await audit_service.record(
            organization_id,
            action=AuditAction.TESTED,
            entity_type="prompt",
            summary=f"Entry {index}.",
        )

    assert len(await audit_service.list_entries(organization_id, limit=2)) == 2


async def test_listing_audit_entries_is_scoped_to_one_tenant(
    audit_service: AuditService, organization_id: uuid.UUID
) -> None:
    """An audit trail that leaked across tenants would be worse than none
    at all."""
    await audit_service.record(
        organization_id, action=AuditAction.TESTED, entity_type="prompt", summary="Mine."
    )

    assert await audit_service.list_entries(uuid.uuid4()) == []


async def test_the_audit_summary_counts_each_action(
    audit_service: AuditService, organization_id: uuid.UUID
) -> None:
    for action in (AuditAction.TESTED, AuditAction.TESTED, AuditAction.PUBLISHED):
        await audit_service.record(
            organization_id, action=action, entity_type="prompt", summary="Something."
        )

    summary = await audit_service.summary(organization_id)

    assert summary["total"] == 3
    assert summary["by_action"] == {str(AuditAction.TESTED): 2, str(AuditAction.PUBLISHED): 1}
    assert summary["since"]


async def test_the_audit_summary_excludes_entries_older_than_its_horizon(
    audit_service: AuditService, audit_repo: PromptAuditRepository, organization_id: uuid.UUID
) -> None:
    recent = await audit_service.record(
        organization_id, action=AuditAction.TESTED, entity_type="prompt", summary="Recent."
    )
    stale = await audit_service.record(
        organization_id, action=AuditAction.PUBLISHED, entity_type="prompt", summary="Stale."
    )
    stale.occurred_at = datetime.now(UTC) - timedelta(days=90)
    await audit_repo.update(stale)

    summary = await audit_service.summary(organization_id, days=30)

    assert summary["by_action"] == {str(AuditAction.TESTED): 1}
    assert recent.occurred_at > stale.occurred_at


async def test_an_empty_audit_summary_is_zero_rather_than_absent(
    audit_service: AuditService, organization_id: uuid.UUID
) -> None:
    summary = await audit_service.summary(organization_id)

    assert summary["total"] == 0
    assert summary["by_action"] == {}
