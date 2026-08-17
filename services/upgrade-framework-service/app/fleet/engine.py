"""Wave-based fleet rollout planning."""

from __future__ import annotations

from collections.abc import Sequence


def plan_waves(targets: Sequence[str], *, wave_size: int) -> list[list[str]]:
    """Split *targets* into ordered, fixed-size waves for a wave-based
    rollout -- deterministic chunking, preserving input order within
    and across waves.

    Raises:
        ValueError: If *wave_size* is not positive.
    """
    if wave_size <= 0:
        raise ValueError(f"wave_size must be positive, got {wave_size!r}.")
    return [list(targets[index : index + wave_size]) for index in range(0, len(targets), wave_size)]


__all__ = ["plan_waves"]
