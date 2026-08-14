"""Compliance score-to-status classification and remediation
scheduling.

**An account nobody has scanned against a framework is
`NOT_ASSESSED`, never `COMPLIANT`.** Silence is not evidence of
compliance.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models.enums import CloudComplianceStatus

MAX_SCORE = 100.0


def classify_compliance_status(
    score: float | None, *, compliant_threshold: float, partial_threshold: float
) -> CloudComplianceStatus:
    """Classify a compliance status from a 0-100 score.

    ``None`` (never assessed) is always ``NOT_ASSESSED``, regardless of
    the thresholds.

    Raises:
        ValueError: If *score* is given but outside ``[0, 100]``.
    """
    if score is None:
        return CloudComplianceStatus.NOT_ASSESSED
    if not 0.0 <= score <= MAX_SCORE:
        raise ValueError(f"score must be within [0, {MAX_SCORE}]; got {score}.")
    if score >= compliant_threshold:
        return CloudComplianceStatus.COMPLIANT
    if score >= partial_threshold:
        return CloudComplianceStatus.PARTIALLY_COMPLIANT
    return CloudComplianceStatus.NON_COMPLIANT


def compute_remediation_due_at(assessed_at: datetime, *, grace_days: int) -> datetime | None:
    """The remediation deadline for a non-compliant assessment.

    Raises:
        ValueError: On a non-positive *grace_days*.
    """
    if grace_days < 1:
        raise ValueError(f"grace_days must be at least 1; got {grace_days}.")
    return assessed_at + timedelta(days=grace_days)


def is_reassessment_due(
    assessed_at: datetime | None, *, now: datetime, reassessment_days: int
) -> bool:
    """Whether an account is due for reassessment against a framework.

    ``assessed_at is None`` (never assessed) is always due.
    """
    if assessed_at is None:
        return True
    return now - assessed_at >= timedelta(days=reassessment_days)


__all__ = [
    "MAX_SCORE",
    "classify_compliance_status",
    "compute_remediation_due_at",
    "is_reassessment_due",
]
