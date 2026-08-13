"""Backup analytics: success rates and compliance percentages with an
honest denominator.

**A rate with a zero denominator is `None`, never `0.0` or `1.0`.** Zero
backup jobs in a window is not a 0% success rate (nothing failed) and
not a 100% one (nothing succeeded either) -- it is a window with no
evidence, and reporting either number invents a claim the data does not
support.
"""

from __future__ import annotations

from dataclasses import dataclass


def success_rate(succeeded: int, failed: int) -> float | None:
    """The fraction of attempts that succeeded, or ``None`` with no
    attempts.

    Raises:
        ValueError: On a negative count, which cannot be a real tally.
    """
    if succeeded < 0 or failed < 0:
        raise ValueError("succeeded and failed must both be non-negative.")
    total = succeeded + failed
    if total == 0:
        return None
    return succeeded / total


@dataclass(frozen=True, slots=True)
class ComplianceRate:
    """A met/violated tally, kept apart from its rate -- see
    :mod:`app.dr_plans.engine`'s ``ComplianceStatus.NOT_MEASURED`` for
    why the counts themselves matter as much as the percentage."""

    met: int
    violated: int
    not_measured: int

    @property
    def rate(self) -> float | None:
        """The fraction of *measured* attempts that met their target.

        ``not_measured`` is excluded from the denominator deliberately:
        a plan nobody has tested should not silently drag a compliance
        percentage down (or, averaged the other way, prop one up) for an
        objective that was never actually checked.
        """
        return success_rate(self.met, self.violated)


def storage_growth_rate(bytes_current: int, bytes_previous: int) -> float | None:
    """Relative change in storage consumption between two periods.

    ``None`` when the previous period had zero bytes -- dividing by zero
    would either crash or, if guarded naively, report an infinite or
    undefined growth rate that renders as garbage on a dashboard.
    """
    if bytes_previous == 0:
        return None
    return (bytes_current - bytes_previous) / bytes_previous


__all__ = ["ComplianceRate", "storage_growth_rate", "success_rate"]
