"""The repository bundle every route works through.

One object rather than nineteen constructor arguments, all sharing one
tenant scope: a bundle where one repository was built without it would
enforce tenant isolation everywhere except the one query that forgot,
and that query is the leak.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.coverage import CoverageReportRepository
from app.repositories.environments import (
    MockServiceRepository,
    TestDataSetRepository,
    TestEnvironmentRepository,
)
from app.repositories.performance import BenchmarkResultRepository, PerformanceResultRepository
from app.repositories.pipeline import PipelineResultRepository
from app.repositories.quality_gates import QualityGateRepository
from app.repositories.reporting import QaAuditRepository, QaReportRepository, QaStatisticRepository
from app.repositories.security_chaos import ChaosResultRepository, SecurityResultRepository
from app.repositories.synthetic_contract import ContractTestRepository, SyntheticCheckRepository
from app.repositories.test_definitions import TestCaseRepository, TestSuiteRepository
from app.repositories.test_execution import TestResultRepository, TestRunRepository


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    test_suites: TestSuiteRepository
    test_cases: TestCaseRepository

    test_runs: TestRunRepository
    test_results: TestResultRepository

    test_environments: TestEnvironmentRepository
    test_data_sets: TestDataSetRepository
    mock_services: MockServiceRepository

    quality_gates: QualityGateRepository

    coverage_reports: CoverageReportRepository

    performance_results: PerformanceResultRepository
    benchmark_results: BenchmarkResultRepository

    security_results: SecurityResultRepository
    chaos_results: ChaosResultRepository

    synthetic_checks: SyntheticCheckRepository
    contract_tests: ContractTestRepository

    pipeline_results: PipelineResultRepository

    statistics: QaStatisticRepository
    reports: QaReportRepository
    audit: QaAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        test_suites=TestSuiteRepository(session, tenant_scope=tenant_scope),
        test_cases=TestCaseRepository(session, tenant_scope=tenant_scope),
        test_runs=TestRunRepository(session, tenant_scope=tenant_scope),
        test_results=TestResultRepository(session, tenant_scope=tenant_scope),
        test_environments=TestEnvironmentRepository(session, tenant_scope=tenant_scope),
        test_data_sets=TestDataSetRepository(session, tenant_scope=tenant_scope),
        mock_services=MockServiceRepository(session, tenant_scope=tenant_scope),
        quality_gates=QualityGateRepository(session, tenant_scope=tenant_scope),
        coverage_reports=CoverageReportRepository(session, tenant_scope=tenant_scope),
        performance_results=PerformanceResultRepository(session, tenant_scope=tenant_scope),
        benchmark_results=BenchmarkResultRepository(session, tenant_scope=tenant_scope),
        security_results=SecurityResultRepository(session, tenant_scope=tenant_scope),
        chaos_results=ChaosResultRepository(session, tenant_scope=tenant_scope),
        synthetic_checks=SyntheticCheckRepository(session, tenant_scope=tenant_scope),
        contract_tests=ContractTestRepository(session, tenant_scope=tenant_scope),
        pipeline_results=PipelineResultRepository(session, tenant_scope=tenant_scope),
        statistics=QaStatisticRepository(session, tenant_scope=tenant_scope),
        reports=QaReportRepository(session, tenant_scope=tenant_scope),
        audit=QaAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
