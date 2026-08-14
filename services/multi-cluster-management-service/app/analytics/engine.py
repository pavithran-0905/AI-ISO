"""Fleet analytics: rates with an honest denominator.

**A rate with a zero denominator is `None`, never `0.0` or `1.0`.** Zero
upgrades attempted in a window is not a 0% success rate (nothing failed)
and not a 100% one (nothing succeeded either) -- it is a window with no
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
    """A compliant/non-compliant tally, kept apart from its rate -- see
    :mod:`app.compliance.engine`'s ``NOT_ASSESSED`` for why the counts
    themselves matter as much as the percentage."""

    compliant: int
    non_compliant: int
    not_assessed: int

    @property
    def rate(self) -> float | None:
        """The fraction of *assessed* clusters that are compliant.

        ``not_assessed`` is excluded from the denominator deliberately:
        a cluster nobody has scanned should not silently drag a
        compliance percentage down (or prop one up) for a framework it
        was never actually checked against.
        """
        return success_rate(self.compliant, self.non_compliant)


def fleet_availability(healthy: int, total: int) -> float | None:
    """The fraction of the fleet currently healthy.

    Raises:
        ValueError: When *healthy* exceeds *total*, or either is
            negative.
    """
    if healthy < 0 or total < 0:
        raise ValueError("healthy and total must both be non-negative.")
    if healthy > total:
        raise ValueError(f"healthy ({healthy}) cannot exceed total ({total}).")
    if total == 0:
        return None
    return healthy / total


__all__ = ["ComplianceRate", "fleet_availability", "success_rate"]
