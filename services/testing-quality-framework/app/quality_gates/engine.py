"""Quality gate evaluation."""

from __future__ import annotations

from app.models.enums import QualityGateStatus


def evaluate_gate(
    *, value: float, threshold: float, higher_is_better: bool = True
) -> QualityGateStatus:
    """Evaluate a measured *value* against its own *threshold*.

    For a "higher is better" gate (coverage, a pass rate), the gate
    passes when ``value >= threshold``. For a "lower is better" gate
    (a latency ceiling, a findings-count ceiling), it passes when
    ``value <= threshold``.
    """
    if higher_is_better:
        return QualityGateStatus.PASSED if value >= threshold else QualityGateStatus.FAILED
    return QualityGateStatus.PASSED if value <= threshold else QualityGateStatus.FAILED


def all_gates_passed(statuses: list[QualityGateStatus]) -> bool:
    """Whether every gate in *statuses* passed -- a release is only
    approved when none of its own gates failed."""
    return all(QualityGateStatus(status) == QualityGateStatus.PASSED for status in statuses)


__all__ = ["all_gates_passed", "evaluate_gate"]
