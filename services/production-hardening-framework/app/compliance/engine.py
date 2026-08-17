"""Compliance rate computation."""

from __future__ import annotations


def compliance_rate(compliant_count: int, total_count: int) -> float:
    """The fraction of evaluated controls currently in compliance. A
    vacuous 100% (as a fraction, ``1.0``) when nothing has been
    evaluated yet -- there is nothing to be non-compliant with."""
    if total_count <= 0:
        return 1.0
    return compliant_count / total_count


def is_compliant_overall(rate: float, *, threshold: float = 1.0) -> bool:
    """Whether an overall compliance rate meets the required
    threshold. Defaults to requiring every evaluated control to be
    compliant."""
    return rate >= threshold


__all__ = ["compliance_rate", "is_compliant_overall"]
