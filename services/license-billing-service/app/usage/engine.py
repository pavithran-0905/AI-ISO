"""Usage aggregation.

**Aggregation sums exactly the records handed to it -- nothing is
inferred or estimated for a gap.** A metering pipeline that dropped
events produces a rollup that is honestly lower, never silently padded
to look complete.
"""

from __future__ import annotations

from collections.abc import Sequence


def aggregate_quantities(quantities: Sequence[float]) -> float:
    """The total of every quantity, or ``0.0`` for an empty sequence --
    zero events metered is a real total, not a missing one."""
    return sum(quantities)


def compute_overage(*, total_usage: float, limit_value: float) -> float:
    """How far *total_usage* exceeds *limit_value*, or ``0.0`` if it
    does not.

    Raises:
        ValueError: On a negative *total_usage* or *limit_value*.
    """
    if total_usage < 0 or limit_value < 0:
        raise ValueError("total_usage and limit_value must both be non-negative.")
    return max(0.0, total_usage - limit_value)


__all__ = ["aggregate_quantities", "compute_overage"]
