"""QA analytics math: pass/failure/flaky rates, quality scoring, and
flaky-test detection."""

from __future__ import annotations

from collections.abc import Sequence

from app.models.enums import TestResultStatus


def pass_rate(passed: int, total: int) -> float:
    """The fraction of test results that passed, or ``0.0`` if there
    were none to measure."""
    if total <= 0:
        return 0.0
    return passed / total


def failure_rate(failed: int, total: int) -> float:
    """The fraction of test results that failed, or ``0.0`` if there
    were none to measure."""
    if total <= 0:
        return 0.0
    return failed / total


def flaky_rate(flaky: int, total: int) -> float:
    """The fraction of test results flagged flaky, or ``0.0`` if there
    were none to measure."""
    if total <= 0:
        return 0.0
    return flaky / total


def quality_score(
    *, pass_rate_value: float, coverage_percentage: float, quality_gate_pass_rate: float
) -> float:
    """A composite quality score in ``[0.0, 1.0]``, weighting pass
    rate, coverage, and quality-gate pass rate equally."""
    return (pass_rate_value + (coverage_percentage / 100) + quality_gate_pass_rate) / 3


def is_flaky(results: Sequence[TestResultStatus]) -> bool:
    """Whether a test case's own recent results are flaky: it must
    contain both at least one ``PASSED`` and at least one ``FAILED``
    outcome. A test that has only ever passed, or only ever failed, is
    consistently broken or consistently fine -- not flaky."""
    statuses = {TestResultStatus(result) for result in results}
    return TestResultStatus.PASSED in statuses and TestResultStatus.FAILED in statuses


__all__ = ["failure_rate", "flaky_rate", "is_flaky", "pass_rate", "quality_score"]
