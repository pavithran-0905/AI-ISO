"""Integration tests for every repository, against real PostgreSQL.

**Every model/enum whose real name starts with ``Test`` is imported
under an alias.** pytest's default collector treats any top-level name
matching ``Test*`` as a candidate test class and raises a collection
error the moment it finds one with an ``__init__``/``__new__`` it
can't call with no arguments -- true of every SQLAlchemy model and
every ``StrEnum``. This service's own domain vocabulary (test suites,
test cases, test runs, ...) makes that collision unavoidable, so
aliasing at the import site is mandatory here, not just style.
"""

from __future__ import annotations

import uuid

from app.models.enums import (
    ChaosFaultType,
    CheckResultStatus,
    ContractTestType,
    CoverageType,
    MockServiceType,
    PerformanceTestType,
    QaAuditAction,
    QaReportKind,
    QualityGateStatus,
    QualityGateType,
    ReportFormat,
    ReportStatus,
    SecurityTestType,
    SyntheticCheckType,
)
from app.models.enums import TestEnvironmentType as EnvironmentTypeEnum
from app.models.enums import TestResultStatus as ResultStatusEnum
from app.models.enums import TestRunStatus as RunStatusEnum
from app.models.enums import TestType as SuiteTypeEnum
from app.models.environments import MockService
from app.models.environments import TestDataSet as DataSetModel
from app.models.environments import TestEnvironment as EnvironmentModel
from app.models.performance import BenchmarkResult, PerformanceResult
from app.models.pipeline import PipelineResult
from app.models.quality_gates import QualityGate
from app.models.reporting import QaAudit, QaReport, QaStatistic
from app.models.security_chaos import ChaosResult, SecurityResult
from app.models.synthetic_contract import ContractTest, SyntheticCheck
from app.models.test_definitions import TestCase as CaseModel
from app.models.test_definitions import TestSuite as SuiteModel
from app.models.test_execution import TestResult as ResultModel
from app.models.test_execution import TestRun as RunModel
from app.services.bundle import Repositories
from tests.conftest import hours_ago, utcnow


class TestSuiteAndCaseRepositories:
    async def test_suite_find_by_name_list_enabled_and_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.test_suites.create(
            SuiteModel(organization_id=organization_id, name="suite1", test_type=SuiteTypeEnum.UNIT)
        )
        found = await repos.test_suites.find_by_name(organization_id, name="suite1")
        assert found is not None
        assert len(await repos.test_suites.list_enabled(organization_id)) == 1
        assert len(await repos.test_suites.list_all(organization_id)) == 1

    async def test_case_list_for_suite(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        suite = await repos.test_suites.create(
            SuiteModel(
                organization_id=organization_id, name="suite2", test_type=SuiteTypeEnum.INTEGRATION
            )
        )
        await repos.test_cases.create(
            CaseModel(organization_id=organization_id, test_suite_id=suite.id, name="case1")
        )
        assert len(await repos.test_cases.list_for_suite(suite.id)) == 1


class TestExecutionRepositories:
    async def test_run_list_recent_running_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        suite = await repos.test_suites.create(
            SuiteModel(
                organization_id=organization_id, name="suite3", test_type=SuiteTypeEnum.SMOKE
            )
        )
        await repos.test_runs.create(
            RunModel(
                organization_id=organization_id,
                test_suite_id=suite.id,
                status=RunStatusEnum.RUNNING,
            )
        )
        assert (
            len(await repos.test_runs.list_recent(organization_id, status=RunStatusEnum.RUNNING))
            == 1
        )
        assert len(await repos.test_runs.list_running(organization_id)) == 1
        assert organization_id in await repos.test_runs.list_organization_ids()

    async def test_result_list_for_run_recent_for_case_distinct_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        suite = await repos.test_suites.create(
            SuiteModel(
                organization_id=organization_id, name="suite4", test_type=SuiteTypeEnum.REGRESSION
            )
        )
        case = await repos.test_cases.create(
            CaseModel(organization_id=organization_id, test_suite_id=suite.id, name="case2")
        )
        run = await repos.test_runs.create(
            RunModel(organization_id=organization_id, test_suite_id=suite.id)
        )
        await repos.test_results.create(
            ResultModel(
                organization_id=organization_id,
                test_run_id=run.id,
                test_case_id=case.id,
                status=ResultStatusEnum.PASSED,
            )
        )
        assert len(await repos.test_results.list_for_run(run.id)) == 1
        assert (
            len(
                await repos.test_results.list_recent_for_case(organization_id, test_case_id=case.id)
            )
            == 1
        )
        assert case.id in await repos.test_results.list_distinct_case_ids(organization_id)
        assert len(await repos.test_results.list_recent(organization_id)) == 1
        assert organization_id in await repos.test_results.list_organization_ids()


class TestEnvironmentsRepositories:
    async def test_environment_find_by_name_and_list_active(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.test_environments.create(
            EnvironmentModel(
                organization_id=organization_id,
                name="qa-env",
                environment_type=EnvironmentTypeEnum.QA,
            )
        )
        found = await repos.test_environments.find_by_name(organization_id, name="qa-env")
        assert found is not None
        assert len(await repos.test_environments.list_active(organization_id)) == 1

    async def test_data_set_list_reusable(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.test_data_sets.create(
            DataSetModel(organization_id=organization_id, name="dataset1", is_reusable=True)
        )
        assert len(await repos.test_data_sets.list_reusable(organization_id)) == 1

    async def test_mock_service_list_active(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.mock_services.create(
            MockService(
                organization_id=organization_id, name="mock1", mock_type=MockServiceType.REST
            )
        )
        assert len(await repos.mock_services.list_active(organization_id)) == 1


class TestQualityGateRepository:
    async def test_find_by_name_list_all_and_by_status(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.quality_gates.create(
            QualityGate(
                organization_id=organization_id,
                name="coverage-gate",
                gate_type=QualityGateType.MINIMUM_COVERAGE,
                threshold=90.0,
                status=QualityGateStatus.PASSED,
            )
        )
        found = await repos.quality_gates.find_by_name(organization_id, name="coverage-gate")
        assert found is not None
        assert len(await repos.quality_gates.list_all(organization_id)) == 1
        assert (
            len(
                await repos.quality_gates.list_by_status(
                    organization_id, status=QualityGateStatus.PASSED
                )
            )
            == 1
        )


class TestCoverageRepository:
    async def test_list_all_latest_by_type_distinct_types_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        from app.models.coverage import CoverageReport

        await repos.coverage_reports.create(
            CoverageReport(
                organization_id=organization_id, coverage_type=CoverageType.UNIT, percentage=90.0
            )
        )
        await repos.coverage_reports.create(
            CoverageReport(
                organization_id=organization_id, coverage_type=CoverageType.UNIT, percentage=85.0
            )
        )
        assert len(await repos.coverage_reports.list_all(organization_id)) == 2
        latest_two = await repos.coverage_reports.list_latest_by_type(
            organization_id, coverage_type=CoverageType.UNIT, limit=2
        )
        assert len(latest_two) == 2
        assert latest_two[0].percentage == 85.0
        assert CoverageType.UNIT in [
            CoverageType(t)
            for t in await repos.coverage_reports.list_distinct_types(organization_id)
        ]
        assert organization_id in await repos.coverage_reports.list_organization_ids()


class TestPerformanceRepositories:
    async def test_performance_result_list_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.performance_results.create(
            PerformanceResult(
                organization_id=organization_id,
                performance_type=PerformanceTestType.LOAD,
                latency_ms=100.0,
            )
        )
        assert len(await repos.performance_results.list_all(organization_id)) == 1

    async def test_benchmark_result_find_latest_by_name_and_list_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.benchmark_results.create(
            BenchmarkResult(
                organization_id=organization_id,
                name="throughput",
                baseline_value=100.0,
                measured_value=110.0,
            )
        )
        found = await repos.benchmark_results.find_latest_by_name(
            organization_id, name="throughput"
        )
        assert found is not None
        assert len(await repos.benchmark_results.list_all(organization_id)) == 1


class TestSecurityChaosRepositories:
    async def test_security_result_list_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.security_results.create(
            SecurityResult(
                organization_id=organization_id,
                security_type=SecurityTestType.OWASP_TOP_10,
                status=CheckResultStatus.PASSED,
            )
        )
        assert len(await repos.security_results.list_all(organization_id)) == 1

    async def test_chaos_result_list_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.chaos_results.create(
            ChaosResult(
                organization_id=organization_id,
                fault_type=ChaosFaultType.NETWORK_LATENCY,
                status=CheckResultStatus.PASSED,
            )
        )
        assert len(await repos.chaos_results.list_all(organization_id)) == 1


class TestSyntheticContractRepositories:
    async def test_synthetic_check_list_all_and_since(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.synthetic_checks.create(
            SyntheticCheck(
                organization_id=organization_id,
                name="homepage",
                check_type=SyntheticCheckType.AVAILABILITY,
                status=CheckResultStatus.PASSED,
                checked_at=utcnow(),
            )
        )
        assert len(await repos.synthetic_checks.list_all(organization_id)) == 1
        assert (
            len(await repos.synthetic_checks.list_since(organization_id, since=hours_ago(1))) == 1
        )

    async def test_contract_test_list_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.contract_tests.create(
            ContractTest(
                organization_id=organization_id,
                name="checkout-api",
                contract_type=ContractTestType.CONSUMER,
                status=CheckResultStatus.PASSED,
            )
        )
        assert len(await repos.contract_tests.list_all(organization_id)) == 1


class TestPipelineRepository:
    async def test_list_recent_running_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.pipeline_results.create(
            PipelineResult(
                organization_id=organization_id, name="build-pipeline", status=RunStatusEnum.RUNNING
            )
        )
        assert len(await repos.pipeline_results.list_recent(organization_id)) == 1
        assert len(await repos.pipeline_results.list_running(organization_id)) == 1
        assert organization_id in await repos.pipeline_results.list_organization_ids()


class TestReportingRepositories:
    async def test_statistic_find_window_and_range(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        window_start = utcnow()
        await repos.statistics.create(
            QaStatistic(
                organization_id=organization_id, window_start=window_start, window_end=utcnow()
            )
        )
        found = await repos.statistics.find_window(organization_id, window_start=window_start)
        assert found is not None
        assert len(await repos.statistics.list_range(organization_id, since=hours_ago(1))) == 1

    async def test_report_list_recent_filters(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.reports.create(
            QaReport(
                organization_id=organization_id,
                kind=QaReportKind.COVERAGE,
                report_format=ReportFormat.JSON,
                title="Coverage report",
                status=ReportStatus.COMPLETED,
                period_start=hours_ago(1),
                period_end=utcnow(),
            )
        )
        assert (
            len(await repos.reports.list_recent(organization_id, kind=QaReportKind.COVERAGE)) == 1
        )
        assert (
            len(await repos.reports.list_recent(organization_id, status=ReportStatus.COMPLETED))
            == 1
        )

    async def test_audit_list_recent_for_entity_and_since(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        entity_id = uuid.uuid4()
        await repos.audit.create(
            QaAudit(
                organization_id=organization_id,
                action=QaAuditAction.ADMINISTRATIVE,
                entity_type="x",
                entity_id=entity_id,
                summary="s",
                occurred_at=utcnow(),
            )
        )
        assert len(await repos.audit.list_recent(organization_id)) == 1
        assert len(await repos.audit.list_for_entity("x", entity_id)) == 1
        assert len(await repos.audit.list_recent(organization_id, since=hours_ago(1))) == 1
        assert len(await repos.audit.list_recent(organization_id, since=hours_ago(-1))) == 0
