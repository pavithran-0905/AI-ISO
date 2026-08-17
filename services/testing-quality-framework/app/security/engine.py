"""Security scan result classification."""

from __future__ import annotations

from app.models.enums import CheckResultStatus


def classify_security_result(
    findings_count: int, *, warning_threshold: int = 1, failure_threshold: int = 5
) -> CheckResultStatus:
    """Classify a security scan by its own findings count: zero
    findings is ``PASSED``, at least *warning_threshold* but fewer than
    *failure_threshold* is ``WARNING``, *failure_threshold* or more is
    ``FAILED``."""
    if findings_count >= failure_threshold:
        return CheckResultStatus.FAILED
    if findings_count >= warning_threshold:
        return CheckResultStatus.WARNING
    return CheckResultStatus.PASSED


__all__ = ["classify_security_result"]
