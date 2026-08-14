"""Cluster compliance scoring and reassessment scheduling.

**A cluster never scanned against a framework is `NOT_ASSESSED`, never
`COMPLIANT`.** Silence is not evidence of compliance -- it is the
absence of an assessment, and treating it as a pass is exactly the gap a
real audit exists to close.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models.enums import ClusterComplianceStatus

MAX_SCORE = 100.0


def classify_compliance_score(
    score: float | None, *, compliant_threshold: float, partial_threshold: float
) -> ClusterComplianceStatus:
    """Classify a 0-100 compliance score.

    ``score is None`` means the cluster has never been assessed against
    this framework at all.

    Raises:
        ValueError: When *compliant_threshold* does not strictly exceed
            *partial_threshold*, or either falls outside ``[0, 100]``.
    """
    if not 0.0 <= partial_threshold <= MAX_SCORE or not 0.0 <= compliant_threshold <= MAX_SCORE:
        raise ValueError("Both thresholds must fall within [0, 100].")
    if compliant_threshold <= partial_threshold:
        raise ValueError(
            f"compliant_threshold ({compliant_threshold}) must exceed "
            f"partial_threshold ({partial_threshold})."
        )
    if score is None:
        return ClusterComplianceStatus.NOT_ASSESSED
    if score >= compliant_threshold:
        return ClusterComplianceStatus.COMPLIANT
    if score >= partial_threshold:
        return ClusterComplianceStatus.PARTIALLY_COMPLIANT
    return ClusterComplianceStatus.NON_COMPLIANT


def compute_remediation_due(assessed_at: datetime, *, grace_days: int) -> datetime:
    """The deadline by which a non-compliant finding must be remediated.

    Raises:
        ValueError: On a negative grace period.
    """
    if grace_days < 0:
        raise ValueError(f"grace_days must be non-negative; got {grace_days}.")
    return assessed_at + timedelta(days=grace_days)


def is_reassessment_due(
    assessed_at: datetime | None, *, now: datetime, reassessment_days: int
) -> bool:
    """Whether a cluster's compliance standing against one framework
    needs to be checked again.

    ``assessed_at is None`` (never assessed) is always due -- there is
    nothing to have gone stale.
    """
    if assessed_at is None:
        return True
    return now - assessed_at >= timedelta(days=reassessment_days)


__all__ = ["classify_compliance_score", "compute_remediation_due", "is_reassessment_due"]
