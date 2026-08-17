"""Imports every model so ``Base.metadata`` sees every table."""

from __future__ import annotations

from app.models.coverage import CoverageReport
from app.models.environments import MockService, TestDataSet, TestEnvironment
from app.models.performance import BenchmarkResult, PerformanceResult
from app.models.pipeline import PipelineResult
from app.models.quality_gates import QualityGate
from app.models.reporting import QaAudit, QaReport, QaStatistic
from app.models.security_chaos import ChaosResult, SecurityResult
from app.models.synthetic_contract import ContractTest, SyntheticCheck
from app.models.test_definitions import TestCase, TestSuite
from app.models.test_execution import TestResult, TestRun

__all__ = [
    "BenchmarkResult",
    "ChaosResult",
    "ContractTest",
    "CoverageReport",
    "MockService",
    "PerformanceResult",
    "PipelineResult",
    "QaAudit",
    "QaReport",
    "QaStatistic",
    "QualityGate",
    "SecurityResult",
    "SyntheticCheck",
    "TestCase",
    "TestDataSet",
    "TestEnvironment",
    "TestResult",
    "TestRun",
    "TestSuite",
]
