"""Security finding severity classification."""

from __future__ import annotations

from app.models.enums import FindingSeverity

_SEVERITY_BREAKPOINTS: tuple[tuple[float, FindingSeverity], ...] = (
    (25.0, FindingSeverity.LOW),
    (50.0, FindingSeverity.MEDIUM),
    (75.0, FindingSeverity.HIGH),
)


def classify_risk_score(risk_score: float) -> FindingSeverity:
    """Classify a 0-100 risk score into a severity band: below 25 is
    ``LOW``, below 50 is ``MEDIUM``, below 75 is ``HIGH``, and 75 or
    beyond is ``CRITICAL``."""
    for breakpoint, severity in _SEVERITY_BREAKPOINTS:
        if risk_score < breakpoint:
            return severity
    return FindingSeverity.CRITICAL


def is_critical(severity: FindingSeverity) -> bool:
    """Whether a severity level warrants an immediate notification."""
    return FindingSeverity(severity) == FindingSeverity.CRITICAL


__all__ = ["classify_risk_score", "is_critical"]
