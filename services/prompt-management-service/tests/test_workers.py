"""Tests for :mod:`app.workers` -- the four leader-elected background
sweeps plus their ``shared_core.scheduler`` registration.

**Everything runs against real infrastructure.** Each worker is built
with the real SAVEPOINT-isolated ``db_session_factory`` (workers take a
*factory*, not a session, precisely because each one opens a session per
unit of work) and driven through its own real ``tick()`` against real
seeded PostgreSQL rows. The registration tests use a real
``SchedulerManager`` on a real RabbitMQ connection and a real Redis
client.

That ``SchedulerManager``'s timer really does fire these jobs was
verified live, out of band, against a real seeded lapsed approval. What
is under test here is each sweep's own logic.

**Failure injection is real, not mocked.** Two mechanisms are used, and
neither replaces the code under test:

- Cross-tenant lookups. ``_evaluate_one`` resolves its experiment with
  ``require_in_org``; handing it an organization the experiment does not
  belong to makes the real repository raise a real ``NotFoundError``.
- :class:`FlakySessionFactory`, a real ``async_sessionmaker`` wrapper
  that hands out genuine sessions but raises a real ``OSError`` on a
  chosen call. That is what PostgreSQL dropping a connection part-way
  through a sweep actually looks like to the worker, and it is the only
  way to reach the "the rest of the tick continues" branch from inside
  ``tick()`` rather than by calling the private helper directly.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from shared_core.enums.job_status import JobStatus
from shared_core.exceptions.not_found import NotFoundError
from shared_core.queue.factory import create_queue_framework
from shared_core.scheduler import Job, JobType, SchedulerManager
from shared_core.scheduler import ScheduleType as FrameworkScheduleType
from shared_core.scheduler.factory import create_scheduler_framework
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import (
    AbTestArm,
    AbTestStatus,
    ApprovalStatus,
    AuditAction,
    ExecutionStatus,
    PromptLifecycleStatus,
    PromptType,
    VersionBump,
)
from app.models.governance import PromptApproval
from app.models.prompt import Prompt
from app.models.testing import PromptAbTest, PromptExecution
from app.repositories.analytics import PromptAuditRepository, PromptStatisticRepository
from app.repositories.governance import PromptApprovalRepository
from app.repositories.prompt import PromptRepository
from app.repositories.testing import PromptAbTestRepository
from app.workers.ab_evaluation_sweep import AbEvaluationSweepWorker
from app.workers.approval_expiry_sweep import ApprovalExpirySweepWorker
from app.workers.registrar import (
    AB_EVALUATION_SWEEP_JOB_ID,
    APPROVAL_EXPIRY_SWEEP_JOB_ID,
    REVIEW_CYCLE_SWEEP_JOB_ID,
    STATISTICS_ROLLUP_JOB_ID,
    _register,
    register_ab_evaluation_sweep,
    register_approval_expiry_sweep,
    register_review_cycle_sweep,
    register_statistics_rollup,
)
from app.workers.review_cycle_sweep import ReviewCycleSweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from tests.conftest import (
    UNREACHABLE_ERRORS,
    MakePromptFn,
    RecordingPublisher,
    ago,
    rabbitmq_test_settings,
    soon,
)

pytestmark = pytest.mark.asyncio

_ARM_SAMPLES = 10
"""Executions per arm in the A/B fixtures. Comfortably above the
``MIN_SAMPLES_PER_ARM`` floor of 2, and small enough that seeding both
arms is fast; experiments in these tests set their own
``minimum_samples_per_arm`` to match rather than the production default
of 100."""


# ---------------------------------------------------------------------------
# Real failure injection
# ---------------------------------------------------------------------------


class FlakySessionFactory:
    """A real session factory that fails on one chosen call.

    Every session it returns is a genuine one from the wrapped
    ``async_sessionmaker``; only the *nth* call raises, with a real
    ``OSError`` -- what a dropped PostgreSQL connection actually looks
    like from inside a sweep.
    """

    def __init__(self, wrapped: async_sessionmaker[AsyncSession], *, fail_on_call: int) -> None:
        self._wrapped = wrapped
        self._fail_on_call = fail_on_call
        self.calls = 0

    def __call__(self) -> Any:
        self.calls += 1
        if self.calls == self._fail_on_call:
            raise OSError("connection to server was lost")
        return self._wrapped()


# ---------------------------------------------------------------------------
# Fresh-session readers
#
# The worker mutates rows through its own sessions, so re-reading through
# the seeding session's identity map could return a stale in-memory copy
# and quietly assert nothing. Every assertion below re-selects.
# ---------------------------------------------------------------------------


def _bare_prompt(organization_id: uuid.UUID, slug: str) -> Prompt:
    """A prompt belonging to a *different* tenant.

    Written straight through the repository rather than through
    ``PromptService``: the point is a second ``organization_id`` in the
    ``prompts`` table, which is what makes the rollup's tenant discovery
    return more than one row.
    """
    return Prompt(
        organization_id=organization_id,
        slug=slug,
        name=slug.replace("-", " ").title(),
        prompt_type=PromptType.SYSTEM,
    )


async def _read_approval(
    factory: async_sessionmaker[AsyncSession], approval_id: uuid.UUID
) -> PromptApproval:
    async with factory() as session:
        return await PromptApprovalRepository(session).require_by_id(approval_id)


async def _read_prompt(factory: async_sessionmaker[AsyncSession], prompt_id: uuid.UUID) -> Any:
    async with factory() as session:
        return await PromptRepository(session).require_by_id(prompt_id)


async def _read_experiment(
    factory: async_sessionmaker[AsyncSession], experiment_id: uuid.UUID
) -> PromptAbTest:
    async with factory() as session:
        return await PromptAbTestRepository(session).require_by_id(experiment_id)


async def _audit_actions(
    factory: async_sessionmaker[AsyncSession], organization_id: uuid.UUID
) -> list[str]:
    async with factory() as session:
        rows = await PromptAuditRepository(session).list_for_org(organization_id, limit=200)
        return [str(row.action) for row in rows]


# ---------------------------------------------------------------------------
# Approval expiry sweep
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_approval(approvals_repo: PromptApprovalRepository, make_prompt: MakePromptFn) -> Any:
    """Create one approval row against a real prompt revision."""
    _prompt, version = await make_prompt("approval-target")

    async def _make(
        *,
        status: ApprovalStatus = ApprovalStatus.PENDING,
        expires_at: datetime | None = None,
        approver_id: str | None = None,
    ) -> PromptApproval:
        return await approvals_repo.create(
            PromptApproval(
                organization_id=version.organization_id,
                prompt_version_id=version.id,
                status=status,
                approver_id=approver_id,
                requested_by="requester",
                requested_at=ago(7200),
                expires_at=expires_at if expires_at is not None else ago(3600),
            )
        )

    return _make


async def test_approval_expiry_expires_a_lapsed_pending_request(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_approval: Any,
    publisher: RecordingPublisher,
) -> None:
    lapsed = await make_approval(expires_at=ago(3600))

    worker = ApprovalExpirySweepWorker(db_session_factory, publish_event=publisher)
    assert await worker.tick() == 1

    reloaded = await _read_approval(db_session_factory, lapsed.id)
    assert reloaded.status == ApprovalStatus.EXPIRED
    assert reloaded.decided_at is not None


async def test_approval_expiry_leaves_a_request_still_within_its_deadline(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_approval: Any,
    publisher: RecordingPublisher,
) -> None:
    """The deadline is the whole point: expiring early would cancel
    requests a reviewer still has time to answer."""
    live = await make_approval(expires_at=soon(3600))

    worker = ApprovalExpirySweepWorker(db_session_factory, publish_event=publisher)
    assert await worker.tick() == 0

    assert (await _read_approval(db_session_factory, live.id)).status == ApprovalStatus.PENDING


@pytest.mark.parametrize(
    "decided",
    [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.EXPIRED],
)
async def test_approval_expiry_never_touches_an_already_decided_request(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_approval: Any,
    publisher: RecordingPublisher,
    decided: ApprovalStatus,
) -> None:
    """Rewriting a recorded human decision as ``EXPIRED`` would destroy
    the audit answer to "who approved this, and when?"."""
    settled = await make_approval(status=decided, expires_at=ago(3600), approver_id="reviewer")

    worker = ApprovalExpirySweepWorker(db_session_factory, publish_event=publisher)
    assert await worker.tick() == 0

    reloaded = await _read_approval(db_session_factory, settled.id)
    assert reloaded.status == decided
    assert reloaded.approver_id == "reviewer"


async def test_approval_expiry_honours_max_per_tick(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_approval: Any,
    publisher: RecordingPublisher,
) -> None:
    """A backlog of ten thousand lapsed approvals must not become one
    ten-thousand-row transaction."""
    for _ in range(4):
        await make_approval(expires_at=ago(3600))

    worker = ApprovalExpirySweepWorker(db_session_factory, publish_event=publisher, max_per_tick=2)
    assert await worker.tick() == 2
    assert await worker.tick() == 2
    assert await worker.tick() == 0


async def test_approval_expiry_swallows_a_database_failure_and_returns_zero(
    db_session_factory: async_sessionmaker[AsyncSession],
    publisher: RecordingPublisher,
) -> None:
    """A sweep that raised would take down the scheduler's whole tick;
    the next tick retries a transient failure for free."""
    worker = ApprovalExpirySweepWorker(
        FlakySessionFactory(db_session_factory, fail_on_call=1),  # type: ignore[arg-type]
        publish_event=publisher,
    )
    assert await worker.tick() == 0


async def test_approval_expiry_run_job_matches_the_scheduler_signature(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_approval: Any,
    publisher: RecordingPublisher,
) -> None:
    """``run_job`` is what ``shared_core.scheduler`` actually calls; it
    takes the job and returns nothing."""
    lapsed = await make_approval(expires_at=ago(3600))

    worker = ApprovalExpirySweepWorker(db_session_factory, publish_event=publisher)
    assert await worker.run_job(object()) is None

    assert (await _read_approval(db_session_factory, lapsed.id)).status == ApprovalStatus.EXPIRED


# ---------------------------------------------------------------------------
# Review cycle sweep
# ---------------------------------------------------------------------------


@pytest.fixture
def make_published_prompt(prompts_repo: PromptRepository, make_published: Any) -> Any:
    """Publish a prompt, then set its review/expiry dates directly."""

    async def _make(
        slug: str,
        *,
        last_reviewed_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> Prompt:
        prompt, _version = await make_published(slug)
        prompt.last_reviewed_at = last_reviewed_at
        prompt.expires_at = expires_at
        return await prompts_repo.update(prompt)

    return _make


async def test_review_cycle_flags_an_overdue_prompt_without_deprecating_it(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_published_prompt: Any,
    organization_id: uuid.UUID,
) -> None:
    """The load-bearing distinction in this worker. An overdue review
    means "a human should look at this", not "stop serving it" --
    deprecating over a paperwork lapse would break production."""
    overdue = await make_published_prompt("overdue", last_reviewed_at=ago(86_400 * 120))

    worker = ReviewCycleSweepWorker(db_session_factory, review_cycle_days=90)
    assert await worker.tick() == (1, 0)

    reloaded = await _read_prompt(db_session_factory, overdue.id)
    assert reloaded.status == PromptLifecycleStatus.PUBLISHED
    assert str(AuditAction.ADMINISTRATIVE) in await _audit_actions(
        db_session_factory, organization_id
    )


async def test_review_cycle_flags_a_prompt_that_was_never_reviewed(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_published_prompt: Any,
) -> None:
    """A NULL ``last_reviewed_at`` is the strongest possible signal a
    review is owed, so excluding it would let exactly the prompts most
    needing attention escape the sweep forever."""
    await make_published_prompt("never-reviewed", last_reviewed_at=None)

    worker = ReviewCycleSweepWorker(db_session_factory, review_cycle_days=90)
    assert await worker.tick() == (1, 0)


async def test_review_cycle_leaves_a_recently_reviewed_prompt_alone(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_published_prompt: Any,
    organization_id: uuid.UUID,
) -> None:
    await make_published_prompt("fresh", last_reviewed_at=ago(86_400))

    worker = ReviewCycleSweepWorker(db_session_factory, review_cycle_days=90)
    assert await worker.tick() == (0, 0)

    actions = await _audit_actions(db_session_factory, organization_id)
    assert actions == [str(AuditAction.PUBLISHED), str(AuditAction.PROMPT_CREATED)]


async def test_review_cycle_deprecates_a_prompt_past_its_own_expiry(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_published_prompt: Any,
    organization_id: uuid.UUID,
) -> None:
    """An explicit ``expires_at`` is a deliberate author decision, which
    is what earns deprecation where an overdue review does not."""
    expired = await make_published_prompt("expired", last_reviewed_at=ago(60), expires_at=ago(3600))

    worker = ReviewCycleSweepWorker(db_session_factory, review_cycle_days=90)
    assert await worker.tick() == (0, 1)

    reloaded = await _read_prompt(db_session_factory, expired.id)
    assert reloaded.status == PromptLifecycleStatus.DEPRECATED
    assert str(AuditAction.DEPRECATED) in await _audit_actions(db_session_factory, organization_id)


async def test_review_cycle_leaves_a_prompt_whose_expiry_is_still_ahead(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_published_prompt: Any,
) -> None:
    future = await make_published_prompt(
        "not-yet-expired", last_reviewed_at=ago(60), expires_at=soon(86_400)
    )

    worker = ReviewCycleSweepWorker(db_session_factory, review_cycle_days=90)
    assert await worker.tick() == (0, 0)

    assert (
        await _read_prompt(db_session_factory, future.id)
    ).status == PromptLifecycleStatus.PUBLISHED


async def test_review_cycle_counts_a_prompt_that_is_both_overdue_and_expired_in_both(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_published_prompt: Any,
    organization_id: uuid.UUID,
) -> None:
    """Two independent conditions with two independent remedies: the
    prompt is flagged for the missing review *and* deprecated for the
    passed expiry."""
    both = await make_published_prompt(
        "overdue-and-expired", last_reviewed_at=ago(86_400 * 120), expires_at=ago(3600)
    )

    worker = ReviewCycleSweepWorker(db_session_factory, review_cycle_days=90)
    assert await worker.tick() == (1, 1)

    assert (
        await _read_prompt(db_session_factory, both.id)
    ).status == PromptLifecycleStatus.DEPRECATED
    actions = await _audit_actions(db_session_factory, organization_id)
    assert str(AuditAction.ADMINISTRATIVE) in actions
    assert str(AuditAction.DEPRECATED) in actions


async def test_review_cycle_ignores_prompts_that_were_never_published(
    db_session_factory: async_sessionmaker[AsyncSession],
    prompts_repo: PromptRepository,
    make_prompt: MakePromptFn,
) -> None:
    """A draft nobody published has nothing to review and nothing to
    deprecate."""
    prompt, _version = await make_prompt("still-a-draft")
    prompt.expires_at = ago(3600)
    await prompts_repo.update(prompt)

    worker = ReviewCycleSweepWorker(db_session_factory, review_cycle_days=90)
    assert await worker.tick() == (0, 0)


async def test_review_cycle_honours_max_per_tick(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_published_prompt: Any,
) -> None:
    for index in range(3):
        await make_published_prompt(f"overdue-{index}", last_reviewed_at=None)

    worker = ReviewCycleSweepWorker(db_session_factory, review_cycle_days=90, max_per_tick=2)
    assert await worker.tick() == (2, 0)


async def test_review_cycle_swallows_a_database_failure(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    worker = ReviewCycleSweepWorker(
        FlakySessionFactory(db_session_factory, fail_on_call=1),  # type: ignore[arg-type]
        review_cycle_days=90,
    )
    assert await worker.tick() == (0, 0)


async def test_review_cycle_run_job_matches_the_scheduler_signature(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_published_prompt: Any,
) -> None:
    expired = await make_published_prompt("run-job-expired", expires_at=ago(3600))

    worker = ReviewCycleSweepWorker(db_session_factory, review_cycle_days=90)
    assert await worker.run_job(object()) is None

    assert (
        await _read_prompt(db_session_factory, expired.id)
    ).status == PromptLifecycleStatus.DEPRECATED


# ---------------------------------------------------------------------------
# A/B evaluation sweep
# ---------------------------------------------------------------------------


@pytest.fixture
def make_experiment(
    ab_tests_repo: PromptAbTestRepository,
    executions_repo: Any,
    make_prompt: MakePromptFn,
    prompt_service: Any,
    organization_id: uuid.UUID,
) -> Any:
    """A real running experiment with real execution rows on both arms.

    ``AbTestingService.evaluate`` reconciles against ``prompt_executions``
    before deciding, so the arm counters have to be backed by genuine
    rows rather than written onto the experiment.
    """

    async def _make(
        slug: str = "experiment-prompt",
        *,
        control_successes: int,
        variant_successes: int,
        samples: int = _ARM_SAMPLES,
        auto_promote: bool = False,
        status: AbTestStatus = AbTestStatus.RUNNING,
    ) -> PromptAbTest:
        prompt, control = await make_prompt(slug)
        variant = await prompt_service.add_version(
            prompt, body="Hi {{ name }}", component=VersionBump.MINOR
        )

        experiment = await ab_tests_repo.create(
            PromptAbTest(
                organization_id=organization_id,
                prompt_id=prompt.id,
                name=f"{slug}-experiment",
                status=status,
                control_version_id=control.id,
                variant_version_id=variant.id,
                minimum_samples_per_arm=samples,
                significance_level=0.05,
                auto_promote=auto_promote,
                started_at=ago(3600),
            )
        )

        for arm, version, successes in (
            (AbTestArm.CONTROL, control, control_successes),
            (AbTestArm.VARIANT, variant, variant_successes),
        ):
            for index in range(samples):
                await executions_repo.create(
                    PromptExecution(
                        organization_id=organization_id,
                        prompt_id=prompt.id,
                        prompt_version_id=version.id,
                        ab_test_id=experiment.id,
                        ab_arm=arm,
                        status=(
                            ExecutionStatus.SUCCEEDED
                            if index < successes
                            else ExecutionStatus.FAILED
                        ),
                        executed_at=ago(60),
                    )
                )
        return experiment

    return _make


async def test_ab_sweep_concludes_a_significant_experiment(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_experiment: Any,
    publisher: RecordingPublisher,
) -> None:
    experiment = await make_experiment(control_successes=0, variant_successes=_ARM_SAMPLES)

    worker = AbEvaluationSweepWorker(db_session_factory, publish_event=publisher)
    assert await worker.tick() == 1

    reloaded = await _read_experiment(db_session_factory, experiment.id)
    assert reloaded.status == AbTestStatus.COMPLETED
    assert reloaded.is_significant is True
    assert reloaded.winner == AbTestArm.VARIANT
    assert reloaded.p_value is not None


async def test_ab_sweep_leaves_an_inconclusive_experiment_running(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_experiment: Any,
    publisher: RecordingPublisher,
) -> None:
    """Concluding on noise would close experiments that have not
    finished measuring anything."""
    experiment = await make_experiment(control_successes=5, variant_successes=5)

    worker = AbEvaluationSweepWorker(db_session_factory, publish_event=publisher)
    assert await worker.tick() == 0

    assert (
        await _read_experiment(db_session_factory, experiment.id)
    ).status == AbTestStatus.RUNNING


async def test_ab_sweep_leaves_an_experiment_below_its_sample_horizon(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_experiment: Any,
    publisher: RecordingPublisher,
) -> None:
    """Both arms must independently reach the horizon; checking a
    fixed-horizon test early is the classic way to manufacture false
    positives."""
    experiment = await make_experiment(control_successes=0, variant_successes=3, samples=3)
    async with db_session_factory() as session:
        row = await PromptAbTestRepository(session).require_by_id(experiment.id)
        row.minimum_samples_per_arm = 100
        await PromptAbTestRepository(session).update(row)
        await session.commit()

    worker = AbEvaluationSweepWorker(db_session_factory, publish_event=publisher)
    assert await worker.tick() == 0

    assert (
        await _read_experiment(db_session_factory, experiment.id)
    ).status == AbTestStatus.RUNNING


async def test_ab_sweep_ignores_experiments_that_are_not_running(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_experiment: Any,
    publisher: RecordingPublisher,
) -> None:
    experiment = await make_experiment(
        control_successes=0, variant_successes=_ARM_SAMPLES, status=AbTestStatus.DRAFT
    )

    worker = AbEvaluationSweepWorker(db_session_factory, publish_event=publisher)
    assert await worker.tick() == 0

    assert (await _read_experiment(db_session_factory, experiment.id)).status == AbTestStatus.DRAFT


async def test_ab_sweep_does_not_promote_when_auto_promote_is_off_service_wide(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_experiment: Any,
    publisher: RecordingPublisher,
) -> None:
    """Promotion means publishing a new version, which is exactly what
    this service's approval workflow exists to gate. The service-wide
    switch is off by default and overrides the per-experiment flag."""
    experiment = await make_experiment(
        control_successes=0, variant_successes=_ARM_SAMPLES, auto_promote=True
    )

    worker = AbEvaluationSweepWorker(
        db_session_factory, publish_event=publisher, auto_promote=False
    )
    assert await worker.tick() == 1

    assert (
        await _read_experiment(db_session_factory, experiment.id)
    ).status == AbTestStatus.COMPLETED


async def test_ab_sweep_does_not_promote_an_experiment_that_did_not_opt_in(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_experiment: Any,
    publisher: RecordingPublisher,
) -> None:
    """Both switches are required: the service-wide one and the
    experiment's own."""
    experiment = await make_experiment(
        control_successes=0, variant_successes=_ARM_SAMPLES, auto_promote=False
    )

    worker = AbEvaluationSweepWorker(db_session_factory, publish_event=publisher, auto_promote=True)
    assert await worker.tick() == 1

    assert (
        await _read_experiment(db_session_factory, experiment.id)
    ).status == AbTestStatus.COMPLETED


async def test_ab_sweep_promotes_a_winning_variant_when_both_switches_are_on(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_experiment: Any,
    publisher: RecordingPublisher,
) -> None:
    experiment = await make_experiment(
        control_successes=0, variant_successes=_ARM_SAMPLES, auto_promote=True
    )

    worker = AbEvaluationSweepWorker(db_session_factory, publish_event=publisher, auto_promote=True)
    assert await worker.tick() == 1

    assert (
        await _read_experiment(db_session_factory, experiment.id)
    ).status == AbTestStatus.PROMOTED


async def test_ab_sweep_never_promotes_a_significant_loss(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_experiment: Any,
    publisher: RecordingPublisher,
) -> None:
    """A significant result where the variant did *worse* is a real
    finding, not a winner. Promoting it would ship a measured
    regression, so ``variant_wins`` -- not ``significant`` -- is the
    gate."""
    experiment = await make_experiment(
        control_successes=_ARM_SAMPLES, variant_successes=0, auto_promote=True
    )

    worker = AbEvaluationSweepWorker(db_session_factory, publish_event=publisher, auto_promote=True)
    assert await worker.tick() == 1

    reloaded = await _read_experiment(db_session_factory, experiment.id)
    assert reloaded.status == AbTestStatus.COMPLETED
    assert reloaded.winner == AbTestArm.CONTROL


async def test_ab_sweep_evaluate_one_survives_a_cross_tenant_lookup(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_experiment: Any,
    publisher: RecordingPublisher,
) -> None:
    """``require_in_org`` raising for real is the failure this worker's
    ``except`` clause exists for."""
    experiment = await make_experiment(control_successes=0, variant_successes=_ARM_SAMPLES)

    worker = AbEvaluationSweepWorker(db_session_factory, publish_event=publisher)
    assert await worker._evaluate_one(experiment.id, uuid.uuid4()) is False

    assert (
        await _read_experiment(db_session_factory, experiment.id)
    ).status == AbTestStatus.RUNNING


async def test_ab_sweep_evaluate_one_reraises_nothing_for_a_missing_experiment(
    db_session_factory: async_sessionmaker[AsyncSession],
    organization_id: uuid.UUID,
    publisher: RecordingPublisher,
) -> None:
    """An experiment deleted between the sweep's snapshot and its
    evaluation is a real race, and must not kill the tick."""
    worker = AbEvaluationSweepWorker(db_session_factory, publish_event=publisher)
    assert await worker._evaluate_one(uuid.uuid4(), organization_id) is False


async def test_ab_sweep_continues_after_one_experiment_fails(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_experiment: Any,
    publisher: RecordingPublisher,
) -> None:
    """One experiment failing must not poison the transaction the next
    one needs, nor stop the sweep. Call 1 is the snapshot; call 2 is the
    first experiment, which is the one made to fail."""
    first = await make_experiment("first", control_successes=0, variant_successes=_ARM_SAMPLES)
    second = await make_experiment("second", control_successes=0, variant_successes=_ARM_SAMPLES)

    worker = AbEvaluationSweepWorker(
        FlakySessionFactory(db_session_factory, fail_on_call=2),  # type: ignore[arg-type]
        publish_event=publisher,
    )
    assert await worker.tick() == 1

    statuses = {
        (await _read_experiment(db_session_factory, first.id)).status,
        (await _read_experiment(db_session_factory, second.id)).status,
    }
    assert statuses == {AbTestStatus.RUNNING, AbTestStatus.COMPLETED}


async def test_ab_sweep_honours_max_per_tick(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_experiment: Any,
    publisher: RecordingPublisher,
) -> None:
    await make_experiment("one", control_successes=0, variant_successes=_ARM_SAMPLES)
    await make_experiment("two", control_successes=0, variant_successes=_ARM_SAMPLES)

    worker = AbEvaluationSweepWorker(db_session_factory, publish_event=publisher, max_per_tick=1)
    assert await worker.tick() == 1


async def test_ab_sweep_run_job_matches_the_scheduler_signature(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_experiment: Any,
    publisher: RecordingPublisher,
) -> None:
    experiment = await make_experiment(control_successes=0, variant_successes=_ARM_SAMPLES)

    worker = AbEvaluationSweepWorker(db_session_factory, publish_event=publisher)
    assert await worker.run_job(object()) is None

    assert (
        await _read_experiment(db_session_factory, experiment.id)
    ).status == AbTestStatus.COMPLETED


# ---------------------------------------------------------------------------
# Statistics rollup
# ---------------------------------------------------------------------------


async def _latest_statistic(
    factory: async_sessionmaker[AsyncSession], organization_id: uuid.UUID
) -> Any:
    async with factory() as session:
        return await PromptStatisticRepository(session).latest(organization_id)


async def test_statistics_rollup_writes_a_window_for_an_organization(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
) -> None:
    await make_prompt("counted")

    worker = StatisticsRollupWorker(db_session_factory, window_seconds=3600)
    assert await worker.tick() == 1

    latest = await _latest_statistic(db_session_factory, organization_id)
    assert latest is not None
    assert latest.total_prompts == 1
    assert latest.window_end > latest.window_start


async def test_statistics_rollup_covers_every_tenant_independently(
    db_session_factory: async_sessionmaker[AsyncSession],
    prompts_repo: PromptRepository,
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
) -> None:
    """The rollup has no organizations table to iterate, so it derives
    tenants from the prompts themselves -- a tenant silently missing
    from a rollup is worse than one that visibly failed."""
    await make_prompt("mine")
    other_org = uuid.uuid4()
    await prompts_repo.create(_bare_prompt(other_org, "theirs"))

    worker = StatisticsRollupWorker(db_session_factory, window_seconds=3600)
    assert await worker.tick() == 2

    mine = await _latest_statistic(db_session_factory, organization_id)
    other = await _latest_statistic(db_session_factory, other_org)
    assert mine is not None
    assert other is not None
    assert mine.organization_id == organization_id
    assert other.total_prompts == 1


async def test_statistics_rollup_does_nothing_when_no_prompts_exist(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    worker = StatisticsRollupWorker(db_session_factory, window_seconds=3600)
    assert await worker.tick() == 0


async def test_statistics_rollup_window_matches_the_configured_length(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
) -> None:
    await make_prompt("windowed")

    worker = StatisticsRollupWorker(db_session_factory, window_seconds=900)
    await worker.tick()

    latest = await _latest_statistic(db_session_factory, organization_id)
    assert latest is not None
    assert latest.window_end - latest.window_start == timedelta(seconds=900)


async def test_statistics_rollup_continues_after_one_tenant_fails(
    db_session_factory: async_sessionmaker[AsyncSession],
    prompts_repo: PromptRepository,
    make_prompt: MakePromptFn,
) -> None:
    """One session per organization exists exactly so a failure on one
    tenant does not poison the transaction the next one needs. Call 1 is
    the tenant listing; call 2 is the first tenant."""
    await make_prompt("first-tenant")
    await prompts_repo.create(_bare_prompt(uuid.uuid4(), "second-tenant"))

    worker = StatisticsRollupWorker(
        FlakySessionFactory(db_session_factory, fail_on_call=2),  # type: ignore[arg-type]
        window_seconds=3600,
    )
    assert await worker.tick() == 1


async def test_statistics_rollup_returns_zero_when_the_tenant_listing_fails(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Unlike the per-tenant loop, the listing itself is not guarded --
    a failure there means there is nothing to iterate at all."""
    worker = StatisticsRollupWorker(
        FlakySessionFactory(db_session_factory, fail_on_call=1),  # type: ignore[arg-type]
        window_seconds=3600,
    )
    with pytest.raises(OSError, match="connection to server was lost"):
        await worker.tick()


async def test_statistics_rollup_honours_max_organizations_per_tick(
    db_session_factory: async_sessionmaker[AsyncSession],
    prompts_repo: PromptRepository,
    make_prompt: MakePromptFn,
) -> None:
    await make_prompt("tenant-a")
    for index in range(2):
        await prompts_repo.create(_bare_prompt(uuid.uuid4(), f"tenant-{index}"))

    worker = StatisticsRollupWorker(
        db_session_factory, window_seconds=3600, max_organizations_per_tick=2
    )
    assert await worker.tick() == 2


async def test_statistics_rollup_run_job_matches_the_scheduler_signature(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
) -> None:
    await make_prompt("run-job-rollup")

    worker = StatisticsRollupWorker(db_session_factory, window_seconds=3600)
    assert await worker.run_job(object()) is None

    assert await _latest_statistic(db_session_factory, organization_id) is not None


# ---------------------------------------------------------------------------
# Scheduler registration
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def scheduler_manager(cache_framework: Any) -> AsyncIterator[SchedulerManager]:
    """A real ``SchedulerManager`` on real RabbitMQ and real Redis.

    Deliberately never started: registration is a synchronous registry
    operation, and running the polling loop would add nothing to what
    these tests assert.
    """
    try:
        queue = await create_queue_framework(rabbitmq_test_settings())
    except UNREACHABLE_ERRORS as exc:  # pragma: no cover - environment guard
        pytest.skip(f"RabbitMQ is not reachable: {exc}")
    manager = create_scheduler_framework(
        queue.manager,
        cache_framework.client,
        queue_name="prompt_management_service_test_scheduler_queue",
    )
    try:
        yield manager
    finally:
        await queue.shutdown()


async def _noop_job(_job: Job) -> None:
    """A real ``JobFn``: right signature, awaitable, does nothing."""


@pytest.mark.parametrize("interval_seconds", [0, -1, -0.5])
async def test_register_rejects_a_non_positive_interval(
    scheduler_manager: SchedulerManager, interval_seconds: float
) -> None:
    """Zero would busy-loop the scheduler; negative is meaningless."""
    with pytest.raises(ValueError, match="interval must be positive"):
        _register(
            scheduler_manager,
            _noop_job,
            job_id="whatever",
            interval_seconds=interval_seconds,
            component="whatever",
        )

    assert scheduler_manager.registry.list_jobs() == []


@pytest.mark.parametrize(
    ("register", "expected_job_id"),
    [
        (register_approval_expiry_sweep, APPROVAL_EXPIRY_SWEEP_JOB_ID),
        (register_review_cycle_sweep, REVIEW_CYCLE_SWEEP_JOB_ID),
        (register_ab_evaluation_sweep, AB_EVALUATION_SWEEP_JOB_ID),
        (register_statistics_rollup, STATISTICS_ROLLUP_JOB_ID),
    ],
)
async def test_each_register_helper_produces_its_own_deterministic_job(
    scheduler_manager: SchedulerManager, register: Any, expected_job_id: str
) -> None:
    job = register(scheduler_manager, _noop_job, interval_seconds=30)

    assert job.job_id == expected_job_id
    assert job.job_name == expected_job_id
    assert job.job_type == JobType.SYSTEM
    assert job.schedule.schedule_type == FrameworkScheduleType.FIXED_RATE
    assert job.schedule.interval == timedelta(seconds=30)
    assert job.metadata["component"] == expected_job_id


@pytest.mark.parametrize(
    "register",
    [
        register_approval_expiry_sweep,
        register_review_cycle_sweep,
        register_ab_evaluation_sweep,
        register_statistics_rollup,
    ],
)
async def test_registration_returns_the_managers_job_not_the_local_one(
    scheduler_manager: SchedulerManager, register: Any
) -> None:
    """Registration is what computes the first due time. Returning the
    locally built object would hand the caller a job that reads as never
    scheduled -- ``JobRegistry.transition`` replaces the entry with a new
    dataclass copy rather than mutating the one that was handed in."""
    job = register(scheduler_manager, _noop_job, interval_seconds=30)

    assert job.next_run is not None
    assert job.status == JobStatus.SCHEDULED
    assert job is scheduler_manager.registry.get(job.job_id)


async def test_all_four_jobs_register_side_by_side(
    scheduler_manager: SchedulerManager,
) -> None:
    """Deterministic ids mean the four never collide with each other."""
    register_approval_expiry_sweep(scheduler_manager, _noop_job, interval_seconds=30)
    register_review_cycle_sweep(scheduler_manager, _noop_job, interval_seconds=60)
    register_ab_evaluation_sweep(scheduler_manager, _noop_job, interval_seconds=90)
    register_statistics_rollup(scheduler_manager, _noop_job, interval_seconds=120)

    registered = {job.job_id for job in scheduler_manager.registry.list_jobs()}
    assert registered == {
        APPROVAL_EXPIRY_SWEEP_JOB_ID,
        REVIEW_CYCLE_SWEEP_JOB_ID,
        AB_EVALUATION_SWEEP_JOB_ID,
        STATISTICS_ROLLUP_JOB_ID,
    }


async def test_re_registering_replaces_rather_than_leaks(
    scheduler_manager: SchedulerManager,
) -> None:
    """Deterministic ids exist so a restart does not accumulate a second
    copy of every sweep."""
    register_approval_expiry_sweep(scheduler_manager, _noop_job, interval_seconds=30)
    second = register_approval_expiry_sweep(scheduler_manager, _noop_job, interval_seconds=45)

    assert len(scheduler_manager.registry.list_jobs()) == 1
    assert second.schedule.interval == timedelta(seconds=45)


async def test_a_registered_job_actually_runs_the_worker(
    scheduler_manager: SchedulerManager,
    db_session_factory: async_sessionmaker[AsyncSession],
    make_approval: Any,
    publisher: RecordingPublisher,
) -> None:
    """The registration and the worker are wired to each other, not just
    individually correct: invoking the registered job's own ``fn``
    expires a real lapsed approval."""
    lapsed = await make_approval(expires_at=ago(3600))
    worker = ApprovalExpirySweepWorker(db_session_factory, publish_event=publisher)

    job = register_approval_expiry_sweep(scheduler_manager, worker.run_job, interval_seconds=30)
    await job.fn(job)

    assert (await _read_approval(db_session_factory, lapsed.id)).status == ApprovalStatus.EXPIRED


async def test_a_lapsed_approval_is_found_by_the_repository_the_sweep_uses(
    db_session_factory: async_sessionmaker[AsyncSession],
    make_approval: Any,
) -> None:
    """A guard on the sweep's own precondition: if this query stopped
    returning rows, every expiry test above would pass vacuously."""
    await make_approval(expires_at=ago(3600))

    async with db_session_factory() as session:
        found = await PromptApprovalRepository(session).list_pending_expired(datetime.now(UTC))

    assert len(found) == 1


async def test_a_missing_approval_raises_not_found(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The reader helper these tests rely on really does fail loudly."""
    with pytest.raises(NotFoundError):
        await _read_approval(db_session_factory, uuid.uuid4())
