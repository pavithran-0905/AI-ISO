"""Governance policy evaluation: tag, naming, and quota policies.

**A policy evaluation names every violation it found, never just a
pass/fail bit.** A caller acting on a refusal (blocking provisioning,
flagging a resource) needs to say *why*, not just *that*.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PolicyEvaluation:
    is_compliant: bool
    violations: tuple[str, ...] = field(default_factory=tuple)
    detail: str = ""


def evaluate_tag_policy(tags: dict[str, str], *, required_keys: frozenset[str]) -> PolicyEvaluation:
    """Whether *tags* carries every key in *required_keys*, with a
    non-empty value for each."""
    missing = sorted(key for key in required_keys if not tags.get(key, "").strip())
    if missing:
        return PolicyEvaluation(
            is_compliant=False,
            violations=tuple(f"missing required tag: {key}" for key in missing),
            detail=f"{len(missing)} required tag(s) missing or empty.",
        )
    return PolicyEvaluation(is_compliant=True, detail="All required tags are present.")


def evaluate_naming_policy(name: str, *, pattern: str) -> PolicyEvaluation:
    """Whether *name* matches *pattern* (a full-match regular
    expression)."""
    if re.fullmatch(pattern, name) is None:
        return PolicyEvaluation(
            is_compliant=False,
            violations=(f"name {name!r} does not match pattern {pattern!r}",),
            detail="Name does not conform to the naming policy.",
        )
    return PolicyEvaluation(is_compliant=True, detail="Name conforms to the naming policy.")


def evaluate_quota_policy(*, current_count: int, max_count: int) -> PolicyEvaluation:
    """Whether *current_count* is within *max_count*.

    Raises:
        ValueError: On a negative *current_count* or non-positive
            *max_count*.
    """
    if current_count < 0:
        raise ValueError(f"current_count must be non-negative; got {current_count}.")
    if max_count < 1:
        raise ValueError(f"max_count must be at least 1; got {max_count}.")
    if current_count > max_count:
        return PolicyEvaluation(
            is_compliant=False,
            violations=(f"quota exceeded: {current_count} of {max_count} allowed",),
            detail=f"Over quota by {current_count - max_count}.",
        )
    return PolicyEvaluation(
        is_compliant=True, detail=f"Within quota ({current_count}/{max_count})."
    )


__all__ = [
    "PolicyEvaluation",
    "evaluate_naming_policy",
    "evaluate_quota_policy",
    "evaluate_tag_policy",
]
