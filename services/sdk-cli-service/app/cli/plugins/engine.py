"""CLI plugin lifecycle transitions.

**A plugin only moves between adjacent, explicitly allowed states.**
Skipping straight from ``AVAILABLE`` to ``REMOVED`` would remove a
plugin nobody ever actually installed.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import PluginStatus

_S = PluginStatus

ALLOWED_TRANSITIONS: dict[PluginStatus, frozenset[PluginStatus]] = {
    _S.AVAILABLE: frozenset({_S.INSTALLED}),
    _S.INSTALLED: frozenset({_S.DEPRECATED, _S.REMOVED}),
    _S.DEPRECATED: frozenset({_S.REMOVED}),
    _S.REMOVED: frozenset({_S.AVAILABLE}),
}
"""Every valid next state. A removed plugin can return to ``AVAILABLE``
for reinstallation -- unlike a release, a plugin isn't inherently
one-shot."""


class TransitionRefusal:
    INVALID_TRANSITION = "invalid_transition"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_transition(current: PluginStatus, target: PluginStatus) -> TransitionResult:
    """Whether a CLI plugin may move from *current* to *target*.

    Both arguments are coerced through :class:`PluginStatus` before
    use, since a plain-``String``-typed column can carry a plain ``str``
    rather than the enum instance for a freshly materialized row.
    """
    current = PluginStatus(current)
    target = PluginStatus(target)
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        allowed_names = ", ".join(sorted(state.value for state in allowed)) or "none"
        return TransitionResult(
            is_allowed=False,
            refusal=TransitionRefusal.INVALID_TRANSITION,
            detail=(
                f"{current.value} cannot transition to {target.value}; "
                f"allowed next states are: {allowed_names}."
            ),
        )
    return TransitionResult(
        is_allowed=True, refusal=None, detail=f"{current.value} -> {target.value} is allowed."
    )


__all__ = ["ALLOWED_TRANSITIONS", "TransitionRefusal", "TransitionResult", "validate_transition"]
