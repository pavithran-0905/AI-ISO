"""Unit/integration tests for every service, against real PostgreSQL.

See ``test_repositories.py``'s own module docstring for why every
model/enum starting with ``Test`` is imported under an alias here too.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import (
    ChaosFaultType,
    CheckResultStatus,
    ContractTestType,
    CoverageType,
    MockServiceType,
    PerformanceTestType,
    QaAuditAction,
    QaReportKind,
    QualityGateType,
    SecurityTestType,
    SyntheticCheckType,
)
from app.models.enums import TestEnvironmentType as EnvironmentTypeEnum
from app.models.enums import TestType as SuiteTypeEnum
from app.services import pipeline as pipeline_services
from app.services import test_execution as test_execution_services
from app.services.audit import AuditService
from app.services.bundle import Repositories
from app.services.environments import MockServiceService
from app.services.environments import TestDataSetService as DataSetService
from app.services.environments import TestEnvironmentService as EnvironmentService
from app.services.notifications import QaNotifier
from app.services.performance import BenchmarkService, PerformanceService
from app.services.pipeline import PipelineService
from app.services.quality_gates import QualityGateService
from app.services.reports import ReportService
from app.services.security_chaos import ChaosService, SecurityService
from app.services.statistics import StatisticsService
from app.services.synthetic_contract import ContractTestService, SyntheticCheckService
from app.services.test_definitions import TestCaseService as CaseService
from app.services.test_definitions import TestSuiteService as SuiteService
from app.services.test_execution import TestResultService as ResultService
from app.services.test_execution import TestRunService as RunService
from tests.conftest import RecordingNotifier, RecordingPublisher, hours_ago, utcnow


async def _make_suite(repos: Repositories, organization_id: uuid.UUID, name: str = "s1"):
    service = SuiteService(repos.test_suites)
    return await service.create(organization_id, name=name, test_type=SuiteTypeEnum.UNIT)


class TestDefinitionsServices:
    async def test_suite_create(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        suite = await _make_suite(repos, organization_id)
        assert suite.name == "s1"

    async def test_case_create(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        suite = await _make_suite(repos, organization_id, name="s2")
        service = CaseService(repos.test_cases)
        case = await service.create(organization_id, test_suite_id=suite.id, name="c1")
        assert case.name == "c1"


class TestExecutionServices:
    async def test_run_start_and_complete_succeeded(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        suite = await _make_suite(repos, organization_id, name="s3")
        service = RunService(repos.test_runs, publish=publisher)
        run = await service.create(organization_id, test_suite_id=suite.id)
        run = await service.start(run, now=utcnow())
        assert "TestStarted" in publisher.names()
        completed = await service.complete(run, status="succeeded", now=utcnow())  # type: ignore[arg-type]
        assert completed.status == "succeeded"
        assert "TestCompleted" in publisher.names()

    async def test_run_complete_failed_publishes_test_failed(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        suite = await _make_suite(repos, organization_id, name="s4")
        service = RunService(repos.test_runs, publish=publisher)
        run = await service.create(organization_id, test_suite_id=suite.id)
        run = await service.start(run, now=utcnow())
        completed = await service.complete(run, status="failed", now=utcnow(), error_message="boom")  # type: ignore[arg-type]
        assert completed.status == "failed"
        assert "TestFailed" in publisher.names()

    async def test_run_invalid_transition_raises(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        suite = await _make_suite(repos, organization_id, name="s5")
        service = RunService(repos.test_runs)
        run = await service.create(organization_id, test_suite_id=suite.id)
        with pytest.raises(test_execution_services.TransitionRefusedError):
            await service.complete(run, status="succeeded", now=utcnow())  # type: ignore[arg-type]

    async def test_result_record(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        suite = await _make_suite(repos, organization_id, name="s6")
        case_service = CaseService(repos.test_cases)
        case = await case_service.create(organization_id, test_suite_id=suite.id, name="c2")
        run_service = RunService(repos.test_runs)
        run = await run_service.create(organization_id, test_suite_id=suite.id)
        result_service = ResultService(repos.test_results)
        result = await result_service.record(
            organization_id, test_run_id=run.id, test_case_id=case.id, status="passed"  # type: ignore[arg-type]
        )
        assert result.status == "passed"


class TestEnvironmentsServices:
    async def test_environment_create(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = EnvironmentService(repos.test_environments)
        env = await service.create(
            organization_id, name="qa-env", environment_type=EnvironmentTypeEnum.QA
        )
        assert env.name == "qa-env"

    async def test_data_set_create(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = DataSetService(repos.test_data_sets)
        data_set = await service.create(organization_id, name="ds1")
        assert data_set.is_reusable is True

    async def test_mock_service_create(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = MockServiceService(repos.mock_services)
        mock = await service.create(organization_id, name="mock1", mock_type=MockServiceType.REST)
        assert mock.mock_type == "rest"


class TestQualityGateService:
    async def test_evaluate_passes_and_publishes(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = QualityGateService(repos.quality_gates, publish=publisher)
        gate = await service.create(
            organization_id,
            name="coverage-gate",
            gate_type=QualityGateType.MINIMUM_COVERAGE,
            threshold=90.0,
        )
        evaluated = await service.evaluate(gate, value=95.0)
        assert evaluated.status == "passed"
        assert "QualityGatePassed" in publisher.names()

    async def test_evaluate_fails_and_publishes(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = QualityGateService(repos.quality_gates, publish=publisher)
        gate = await service.create(
            organization_id,
            name="coverage-gate-2",
            gate_type=QualityGateType.MINIMUM_COVERAGE,
            threshold=90.0,
        )
        evaluated = await service.evaluate(gate, value=80.0)
        assert evaluated.status == "failed"
        assert "QualityGateFailed" in publisher.names()


class TestCoverageServiceModule:
    async def test_record(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        from app.services.coverage import CoverageService

        service = CoverageService(repos.coverage_reports)
        report = await service.record(
            organization_id, coverage_type=CoverageType.UNIT, percentage=95.0
        )
        assert report.percentage == 95.0


class TestPerformanceServices:
    async def test_performance_notifies_on_regression(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        service = PerformanceService(repos.performance_results, notifier=notifier)  # type: ignore[arg-type]
        await service.record(
            organization_id,
            performance_type=PerformanceTestType.LATENCY,
            latency_ms=150.0,
            baseline_latency_ms=100.0,
            tolerance_percent=10.0,
        )
        assert any(call[0] == "notify_performance_regression" for call in notifier.calls)

    async def test_performance_no_notification_within_tolerance(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        service = PerformanceService(repos.performance_results, notifier=notifier)  # type: ignore[arg-type]
        await service.record(
            organization_id,
            performance_type=PerformanceTestType.LATENCY,
            latency_ms=102.0,
            baseline_latency_ms=100.0,
            tolerance_percent=10.0,
        )
        assert notifier.calls == []

    async def test_benchmark_publishes_and_notifies_on_regression(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        service = BenchmarkService(repos.benchmark_results, publish=publisher, notifier=notifier)  # type: ignore[arg-type]
        await service.record(
            organization_id,
            name="throughput",
            baseline_value=1000.0,
            measured_value=800.0,
            tolerance_percent=10.0,
            higher_is_better=True,
        )
        assert "BenchmarkCompleted" in publisher.names()
        assert any(call[0] == "notify_benchmark_regression" for call in notifier.calls)


class TestSecurityChaosServices:
    async def test_security_notifies_on_non_passed(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        service = SecurityService(repos.security_results, publish=publisher, notifier=notifier)  # type: ignore[arg-type]
        result = await service.record(
            organization_id, security_type=SecurityTestType.OWASP_TOP_10, findings_count=10
        )
        assert result.status == "failed"
        assert "SecurityScanCompleted" in publisher.names()
        assert any(call[0] == "notify_security_issue" for call in notifier.calls)

    async def test_security_no_notification_when_passed(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        service = SecurityService(repos.security_results, notifier=notifier)  # type: ignore[arg-type]
        await service.record(
            organization_id, security_type=SecurityTestType.OWASP_TOP_10, findings_count=0
        )
        assert notifier.calls == []

    async def test_chaos_record_publishes(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = ChaosService(repos.chaos_results, publish=publisher)
        result = await service.record(
            organization_id,
            fault_type=ChaosFaultType.NODE_FAILURE,
            recovery_time_seconds=30.0,
            target_seconds=60.0,
        )
        assert result.status == "passed"
        assert "ChaosTestCompleted" in publisher.names()


class TestSyntheticContractServices:
    async def test_synthetic_check_record(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = SyntheticCheckService(repos.synthetic_checks)
        check = await service.record(
            organization_id,
            name="homepage",
            check_type=SyntheticCheckType.AVAILABILITY,
            status=CheckResultStatus.PASSED,
            now=utcnow(),
        )
        assert check.name == "homepage"

    async def test_contract_test_validate(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = ContractTestService(repos.contract_tests)
        result = await service.validate(
            organization_id,
            name="checkout-api",
            contract_type=ContractTestType.CONSUMER,
            provider_version="1.1.0",
            consumer_version="1.0.0",
        )
        assert result.status == "passed"


class TestPipelineService:
    async def test_start_and_complete_succeeded(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = PipelineService(repos.pipeline_results)
        pipeline = await service.start(organization_id, name="build-pipeline", now=utcnow())
        assert pipeline.status == "running"
        completed = await service.complete(pipeline, status="succeeded", now=utcnow())  # type: ignore[arg-type]
        assert completed.status == "succeeded"

    async def test_complete_failed_notifies(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        service = PipelineService(repos.pipeline_results, notifier=notifier)  # type: ignore[arg-type]
        pipeline = await service.start(organization_id, name="deploy-pipeline", now=utcnow())
        completed = await service.complete(  # type: ignore[arg-type]
            pipeline, status="failed", now=utcnow(), detail="build broke"
        )
        assert completed.status == "failed"
        assert (
            "notify_pipeline_failed",
            {"pipeline_name": "deploy-pipeline", "reason": "build broke"},
        ) in notifier.calls

    async def test_invalid_transition_raises(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = PipelineService(repos.pipeline_results)
        pipeline = await service.start(organization_id, name="pipeline-x", now=utcnow())
        await service.complete(pipeline, status="succeeded", now=utcnow())  # type: ignore[arg-type]
        with pytest.raises(pipeline_services.TransitionRefusedError):
            await service.complete(pipeline, status="failed", now=utcnow())  # type: ignore[arg-type]


class TestStatisticsAndReportsServices:
    async def test_roll_up_window_is_idempotent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = StatisticsService(repos.statistics)
        window_start = utcnow()
        first = await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=utcnow(),
            test_run_count=1,
            pass_count=1,
            fail_count=0,
            flaky_count=0,
            quality_gate_failure_count=0,
            quality_score=0.9,
        )
        second = await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=utcnow(),
            test_run_count=5,
            pass_count=1,
            fail_count=0,
            flaky_count=0,
            quality_gate_failure_count=0,
            quality_score=0.9,
        )
        assert first.id == second.id
        assert second.test_run_count == 5
        assert len(await service.list_range(organization_id, since=hours_ago(1))) == 1

    async def test_report_generate(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = ReportService(repos.reports)
        report = await service.generate(
            organization_id,
            kind=QaReportKind.COVERAGE,
            title="Coverage report",
            period_start=hours_ago(1),
            period_end=utcnow(),
            row_count=5,
            now=utcnow(),
        )
        assert report.status == "completed"
        assert report.row_count == 5


class TestAuditService:
    async def test_record_and_list_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = AuditService(repos.audit)
        await service.record(
            organization_id=organization_id,
            action=QaAuditAction.ADMINISTRATIVE,
            entity_type="x",
            entity_id=uuid.uuid4(),
            summary="did a thing",
            occurred_at=utcnow(),
        )
        entries = await service.list_recent(organization_id)
        assert len(entries) == 1
        assert entries[0].summary == "did a thing"


class TestQaNotifierSanity:
    """A light sanity check that the notifier import above is actually
    exercised somewhere in this module (used by type-annotated fixtures
    throughout)."""

    def test_notifier_class_importable(self) -> None:
        assert QaNotifier is not None
