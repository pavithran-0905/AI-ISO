"""SLO/SLI compliance evaluation.

Whether "compliant" means "at least" or "at most" the target value
depends on the SLI's own kind: latency, error rate, recovery time, and
resource utilization are compliant at or *below* their target;
availability, throughput, and success rate are compliant at or
*above* it. ``CUSTOM`` has no inherent direction, so callers must say.
"""

from __future__ import annotations

from app.models.enums import SliType

_LOWER_IS_BETTER = frozenset(
    {SliType.LATENCY, SliType.ERROR_RATE, SliType.RECOVERY_TIME, SliType.RESOURCE_UTILIZATION}
)
_HIGHER_IS_BETTER = frozenset({SliType.AVAILABILITY, SliType.THROUGHPUT, SliType.SUCCESS_RATE})


def higher_is_better_for(sli_type: SliType, *, default: bool = True) -> bool:
    """The compliance direction for a given SLI kind.

    ``CUSTOM`` (and any kind in neither known set) falls back to
    *default*, since it carries no inherent direction of its own.
    """
    sli_type = SliType(sli_type)
    if sli_type in _LOWER_IS_BETTER:
        return False
    if sli_type in _HIGHER_IS_BETTER:
        return True
    return default


def is_slo_compliant(
    *,
    actual_value: float,
    target_value: float,
    sli_type: SliType,
    higher_is_better: bool | None = None,
) -> bool:
    """Whether *actual_value* meets *target_value* for the given SLI."""
    direction = higher_is_better_for(sli_type) if higher_is_better is None else higher_is_better
    return actual_value >= target_value if direction else actual_value <= target_value


__all__ = ["higher_is_better_for", "is_slo_compliant"]
