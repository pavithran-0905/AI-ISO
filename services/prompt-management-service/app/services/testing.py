"""Prompt testing and A/B experiments (docs/061 "PROMPT TESTING",
"A/B TESTING").

**Tests here assert on the *rendered prompt*, not on a model's reply.**
This service has no provider credentials by design, so it cannot call a
model. That is a real constraint, not an oversight, and it shapes what
these tests can honestly claim: they catch template breakage, missing
variables, wording regressions, and unsafe output patterns -- the
failures that are deterministic and reproducible. Whether a model
*answers well* is measured by
:mod:`app.services.evaluation` against executions recorded by whichever
service actually ran the prompt.

A caller that has already obtained a model reply may pass it as
``actual_output``, in which case the output assertions apply to it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from shared_core.exceptions.conflict import ConflictError

from app.abtesting import statistics
from app.models.analytics import PromptAudit
from app.models.enums import (
    AbTestArm,
    AbTestStatus,
    AuditAction,
    ExecutionStatus,
    TestKind,
    TestRunStatus,
)
from app.models.prompt import PromptVersion
from app.models.testing import PromptAbTest, PromptTest, PromptTestResult
from app.repositories.analytics import PromptAuditRepository
from app.repositories.testing import (
    PromptAbTestRepository,
    PromptExecutionRepository,
    PromptTestRepository,
    PromptTestResultRepository,
)
from app.services.rendering import RenderingService
from app.types import EventPublisher

_SOURCE_SERVICE = "prompt-management-service"


@dataclass(frozen=True, slots=True)
class TestOutcome:
    """One test run's verdict before it is persisted."""

    status: TestRunStatus
    score: float
    rendered: str | None
    failure_reasons: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """Whether the case met every assertion."""
        return self.status == TestRunStatus.PASSED


class PromptTestingService:
    """Defines and runs prompt tests."""

    def __init__(
        self,
        tests: PromptTestRepository,
        results: PromptTestResultRepository,
        rendering: RenderingService,
    ) -> None:
        self._tests = tests
        self._results = results
        self._rendering = rendering

    async def define(
        self,
        *,
        organization_id: UUID,
        prompt_id: UUID,
        name: str,
        kind: TestKind = TestKind.AUTOMATED,
        variables: dict[str, object] | None = None,
        expected_output: str | None = None,
        expected_substrings: list[str] | None = None,
        forbidden_substrings: list[str] | None = None,
        minimum_score: float = 0.7,
        description: str | None = None,
    ) -> PromptTest:
        """Register a reusable test case for one prompt.

        Raises:
            ValueError: If *minimum_score* is outside ``[0, 1]``.
        """
        if not 0.0 <= minimum_score <= 1.0:
            raise ValueError(f"minimum_score must be within [0.0, 1.0], got {minimum_score!r}.")
        return await self._tests.create(
            PromptTest(
                organization_id=organization_id,
                prompt_id=prompt_id,
                name=name,
                description=description,
                kind=kind,
                variables=dict(variables or {}),
                expected_output=expected_output,
                expected_substrings=list(expected_substrings or []),
                forbidden_substrings=list(forbidden_substrings or []),
                minimum_score=minimum_score,
            )
        )

    async def run(
        self,
        test: PromptTest,
        version: PromptVersion,
        *,
        actual_output: str | None = None,
        run_by: str | None = None,
    ) -> PromptTestResult:
        """Run *test* against *version* and record the result.

        A render failure is ``ERRORED``, not ``FAILED``: the case never
        got to make its assertions, and reporting that as a content
        failure would send someone hunting for a wording problem that
        does not exist.
        """
        started = time.perf_counter()
        outcome = await self._evaluate(test, version, actual_output)
        duration_ms = (time.perf_counter() - started) * 1_000

        result = await self._results.create(
            PromptTestResult(
                organization_id=test.organization_id,
                prompt_test_id=test.id,
                prompt_version_id=version.id,
                status=outcome.status,
                score=outcome.score,
                rendered_prompt=outcome.rendered,
                actual_output=actual_output,
                failure_reasons=list(outcome.failure_reasons),
                duration_ms=duration_ms,
                run_at=datetime.now(UTC),
                run_by=run_by,
            )
        )
        test.last_status = outcome.status
        test.last_run_at = result.run_at
        await self._tests.update(test)
        return result

    async def run_all(
        self, prompt_id: UUID, version: PromptVersion, *, run_by: str | None = None
    ) -> list[PromptTestResult]:
        """Run every enabled test defined for *prompt_id*.

        One failing case never stops the rest: a caller preparing a
        publish wants the whole picture, and stopping at the first
        failure would hide the other four.
        """
        results: list[PromptTestResult] = []
        for test in await self._tests.list_for_prompt(prompt_id, enabled_only=True):
            results.append(await self.run(test, version, run_by=run_by))
        return results

    async def accept_snapshot(self, test: PromptTest, rendered: str) -> PromptTest:
        """Adopt *rendered* as this case's approved snapshot.

        Explicit rather than automatic: a snapshot that updated itself
        on every run would pass forever and detect nothing.
        """
        test.snapshot = rendered
        return await self._tests.update(test)

    async def _evaluate(
        self, test: PromptTest, version: PromptVersion, actual_output: str | None
    ) -> TestOutcome:
        """Render and apply every assertion this case declares."""
        try:
            preview = await self._rendering.preview(version, dict(test.variables or {}))
        except Exception as exc:
            return TestOutcome(
                status=TestRunStatus.ERRORED,
                score=0.0,
                rendered=None,
                failure_reasons=(f"The prompt could not be rendered: {exc}",),
            )

        rendered = preview.body
        subject = actual_output if actual_output is not None else rendered
        reasons: list[str] = []

        if (
            test.kind == TestKind.SNAPSHOT
            and test.snapshot is not None
            and rendered != test.snapshot
        ):
            reasons.append("The rendered prompt differs from the accepted snapshot.")

        if test.expected_output is not None and subject.strip() != test.expected_output.strip():
            reasons.append("The output does not match the expected output exactly.")

        missing = [s for s in (test.expected_substrings or []) if s not in subject]
        if missing:
            reasons.append(f"Missing expected content: {', '.join(repr(s) for s in missing[:3])}.")

        present = [s for s in (test.forbidden_substrings or []) if s in subject]
        if present:
            reasons.append(
                f"Contains forbidden content: {', '.join(repr(s) for s in present[:3])}."
            )

        assertions = self._assertion_count(test)
        score = 1.0 if not assertions else max(0.0, 1.0 - len(reasons) / assertions)
        if score < test.minimum_score:
            reasons.append(f"Score {score:.2f} is below the {test.minimum_score:.2f} threshold.")

        return TestOutcome(
            status=TestRunStatus.FAILED if reasons else TestRunStatus.PASSED,
            score=score,
            rendered=rendered,
            failure_reasons=tuple(reasons),
        )

    @staticmethod
    def _assertion_count(test: PromptTest) -> int:
        """How many distinct assertions this case declares.

        The score denominator. A case declaring nothing scores a clean
        ``1.0`` -- it asserted nothing and nothing failed, which is
        honest rather than flattering: the rendering itself succeeding
        *is* the assertion in that case.
        """
        return sum(
            (
                test.expected_output is not None,
                bool(test.expected_substrings),
                bool(test.forbidden_substrings),
                test.kind == TestKind.SNAPSHOT and test.snapshot is not None,
            )
        )


class AbTestingService:
    """Runs traffic-split experiments between two revisions."""

    def __init__(
        self,
        ab_tests: PromptAbTestRepository,
        executions: PromptExecutionRepository,
        audit: PromptAuditRepository,
        *,
        publish_event: EventPublisher,
    ) -> None:
        self._ab_tests = ab_tests
        self._executions = executions
        self._audit = audit
        self._publish_event = publish_event

    async def start(
        self,
        *,
        organization_id: UUID,
        prompt_id: UUID,
        name: str,
        control: PromptVersion,
        variant: PromptVersion,
        variant_weight: float = 0.5,
        minimum_samples_per_arm: int = 100,
        significance_level: float = 0.05,
        auto_promote: bool = False,
    ) -> PromptAbTest:
        """Open an experiment between two revisions of one prompt.

        Raises:
            ConflictError: If an experiment is already running on this
                prompt, or the two arms are the same revision.
            ValueError: If *variant_weight* is outside ``[0, 1]``.
        """
        if control.id == variant.id:
            raise ConflictError("The control and variant arms must be different revisions.")
        if not 0.0 <= variant_weight <= 1.0:
            raise ValueError(f"variant_weight must be within [0, 1], got {variant_weight!r}.")
        if await self._ab_tests.get_running_for_prompt(prompt_id) is not None:
            raise ConflictError(
                "An experiment is already running on this prompt. Two concurrent "
                "splits would contaminate each other's control arm and neither "
                "result would mean anything."
            )

        return await self._ab_tests.create(
            PromptAbTest(
                organization_id=organization_id,
                prompt_id=prompt_id,
                name=name,
                status=AbTestStatus.RUNNING,
                control_version_id=control.id,
                variant_version_id=variant.id,
                variant_weight=variant_weight,
                minimum_samples_per_arm=minimum_samples_per_arm,
                significance_level=significance_level,
                auto_promote=auto_promote,
                started_at=datetime.now(UTC),
            )
        )

    @staticmethod
    def assign(experiment: PromptAbTest, roll: float) -> AbTestArm:
        """Which arm one execution routes to ("Traffic Splitting").

        Takes the random draw rather than generating it, so routing
        stays a pure function a test can pin.
        """
        variant = statistics.assign_arm(experiment.variant_weight, roll)
        return AbTestArm.VARIANT if variant else AbTestArm.CONTROL

    async def record_outcome(
        self, experiment: PromptAbTest, *, arm: AbTestArm, succeeded: bool
    ) -> PromptAbTest:
        """Increment one arm's counters."""
        if arm == AbTestArm.CONTROL:
            experiment.control_executions += 1
            experiment.control_successes += int(succeeded)
        else:
            experiment.variant_executions += 1
            experiment.variant_successes += int(succeeded)
        return await self._ab_tests.update(experiment)

    async def reconcile(self, experiment: PromptAbTest) -> PromptAbTest:
        """Recount both arms from the execution rows themselves.

        The cached counters exist so a scheduled decision does not scan
        every execution. Reconciling before a *decision* is cheap
        insurance that they have not drifted -- a winner called from
        drifted counters would be wrong in a way nobody would notice.
        """
        counts = await self._executions.arm_counts(experiment.id)
        control = counts.get(str(AbTestArm.CONTROL), (0, 0))
        variant = counts.get(str(AbTestArm.VARIANT), (0, 0))
        experiment.control_executions, experiment.control_successes = control
        experiment.variant_executions, experiment.variant_successes = variant
        return await self._ab_tests.update(experiment)

    async def evaluate(
        self, experiment: PromptAbTest, *, reconcile: bool = True
    ) -> statistics.SignificanceResult:
        """Test whether the experiment has reached a significant result."""
        if reconcile:
            experiment = await self.reconcile(experiment)
        return statistics.evaluate_experiment(
            statistics.ArmResult(experiment.control_executions, experiment.control_successes),
            statistics.ArmResult(experiment.variant_executions, experiment.variant_successes),
            minimum_samples_per_arm=experiment.minimum_samples_per_arm,
            significance_level=experiment.significance_level,
        )

    async def conclude(
        self,
        experiment: PromptAbTest,
        result: statistics.SignificanceResult,
        *,
        decided_by: str | None = None,
    ) -> PromptAbTest:
        """Close an experiment and record its verdict.

        Sets ``winner`` only when the result is significant. An
        inconclusive experiment has no winner, and picking the
        higher-scoring arm anyway would be reading noise as signal.
        """
        experiment.status = AbTestStatus.COMPLETED
        experiment.p_value = result.p_value
        experiment.is_significant = result.significant
        experiment.completed_at = datetime.now(UTC)
        experiment.decision_notes = result.reason
        if result.significant:
            experiment.winner = AbTestArm.VARIANT if result.difference > 0 else AbTestArm.CONTROL
        experiment = await self._ab_tests.update(experiment)

        await self._audit.create(
            PromptAudit(
                organization_id=experiment.organization_id,
                action=AuditAction.AB_TEST_DECIDED,
                entity_type="prompt_ab_test",
                entity_id=experiment.id,
                entity_reference=experiment.name,
                actor_id=decided_by,
                occurred_at=datetime.now(UTC),
                summary=f"Experiment {experiment.name!r} concluded: {result.reason}",
                succeeded=result.significant,
            )
        )
        return experiment

    async def cancel(self, experiment: PromptAbTest, *, reason: str | None = None) -> PromptAbTest:
        """Abandon a running experiment without calling a winner.

        Raises:
            ConflictError: If the experiment is not running.
        """
        if experiment.status != AbTestStatus.RUNNING:
            raise ConflictError(
                f"Experiment {experiment.name!r} is {experiment.status!s}, not running."
            )
        experiment.status = AbTestStatus.CANCELLED
        experiment.completed_at = datetime.now(UTC)
        experiment.decision_notes = reason
        return await self._ab_tests.update(experiment)


def outcome_succeeded(status: ExecutionStatus) -> bool:
    """Whether one recorded execution counts as a success for an arm."""
    return status == ExecutionStatus.SUCCEEDED


__all__ = [
    "AbTestingService",
    "PromptTestingService",
    "TestOutcome",
    "outcome_succeeded",
]
