"""Feature entitlement limit checking.

**``None`` always means unlimited, never "zero."** A feature limit that
was never set is not the same fact as a feature capped at zero -- the
former grants unrestricted use, the latter blocks it entirely.
"""

from __future__ import annotations


def is_within_limit(current_usage: int, *, limit_value: int | None) -> bool:
    """Whether *current_usage* is within an entitlement's limit.

    ``limit_value is None`` means unlimited -- always within limit.

    Raises:
        ValueError: On a negative *current_usage*.
    """
    if current_usage < 0:
        raise ValueError(f"current_usage must be non-negative; got {current_usage}.")
    if limit_value is None:
        return True
    return current_usage < limit_value


def is_feature_entitled(*, is_enabled: bool, limit_value: int | None, current_usage: int) -> bool:
    """Whether a feature may be used right now: enabled, and within its
    limit."""
    if not is_enabled:
        return False
    return is_within_limit(current_usage, limit_value=limit_value)


__all__ = ["is_feature_entitled", "is_within_limit"]
