"""Import every model so ``Base.metadata`` sees all 18 tables."""

from __future__ import annotations

from app.models.baselines import BenchmarkBaseline
from app.models.benchmark_definitions import BenchmarkProfile, BenchmarkSuite
from app.models.benchmark_execution import BenchmarkResult, BenchmarkRun
from app.models.capacity import CapacityForecast, CapacityModel
from app.models.optimization import OptimizationRecommendation
from app.models.performance import PerformanceMetric, PerformanceProfile
from app.models.regressions import PerformanceRegression
from app.models.reporting import BenchmarkAudit, BenchmarkReport, BenchmarkStatistic
from app.models.slo import SloResult
from app.models.statistics_tables import LatencyStatistics, ThroughputStatistics
from app.models.utilization import ResourceUtilization

__all__ = [
    "BenchmarkAudit",
    "BenchmarkBaseline",
    "BenchmarkProfile",
    "BenchmarkReport",
    "BenchmarkResult",
    "BenchmarkRun",
    "BenchmarkStatistic",
    "BenchmarkSuite",
    "CapacityForecast",
    "CapacityModel",
    "LatencyStatistics",
    "OptimizationRecommendation",
    "PerformanceMetric",
    "PerformanceProfile",
    "PerformanceRegression",
    "ResourceUtilization",
    "SloResult",
    "ThroughputStatistics",
]
