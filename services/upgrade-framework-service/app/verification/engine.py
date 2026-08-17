"""Health-gate verification aggregation."""

from __future__ import annotations

from collections.abc import Iterable

from app.models.enums import CheckResultStatus

_S = CheckResultStatus


def aggregate_check_results(results: Iterable[CheckResultStatus]) -> CheckResultStatus:
    """The worst outcome among *results*: any ``FAILED`` outranks any
    ``WARNING``, which outranks an all-``PASSED`` run. An empty
    iterable is vacuously ``PASSED`` -- there is nothing to have
    failed."""
    statuses = [_S(result) for result in results]
    if any(status == _S.FAILED for status in statuses):
        return _S.FAILED
    if any(status == _S.WARNING for status in statuses):
        return _S.WARNING
    return _S.PASSED


def is_health_gate_passed(overall: CheckResultStatus) -> bool:
    """Whether an aggregate verification outcome clears the health
    gate. ``WARNING`` is still a pass -- it is advisory, not
    blocking."""
    return CheckResultStatus(overall) != _S.FAILED


__all__ = ["aggregate_check_results", "is_health_gate_passed"]
