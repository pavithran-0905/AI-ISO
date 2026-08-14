"""Cloud resource drift detection and severity classification.

**Drift is a comparison of two state hashes, never a claim about intent
this service cannot see** -- the same discipline
``app.gitops.engine`` established in
``services/multi-cluster-management-service`` and
``app.digital_twins.engine`` continued in
``services/edge-management-service``.
"""

from __future__ import annotations

from app.models.enums import DriftSeverity


def has_drifted(desired_state_hash: str | None, live_state_hash: str | None) -> bool:
    """Whether a resource's live state disagrees with its desired
    state.

    Either hash being unavailable is never reported as drifted -- an
    absence of evidence on either side is not evidence of drift.
    """
    if desired_state_hash is None or live_state_hash is None:
        return False
    return desired_state_hash != live_state_hash


def classify_drift_severity(
    drifted_field_count: int, *, high_threshold: int, critical_threshold: int
) -> DriftSeverity:
    """Classify drift severity from how many fields disagree.

    Raises:
        ValueError: On a negative *drifted_field_count*.
    """
    if drifted_field_count < 0:
        raise ValueError(f"drifted_field_count must be non-negative; got {drifted_field_count}.")
    if drifted_field_count >= critical_threshold:
        return DriftSeverity.CRITICAL
    if drifted_field_count >= high_threshold:
        return DriftSeverity.HIGH
    if drifted_field_count > 0:
        return DriftSeverity.MEDIUM
    return DriftSeverity.LOW


__all__ = ["classify_drift_severity", "has_drifted"]
