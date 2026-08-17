"""Migration rollback ordering."""

from __future__ import annotations

from collections.abc import Sequence

from app.models.enums import MigrationType


def plan_rollback_order(applied: Sequence[MigrationType]) -> list[MigrationType]:
    """The order migrations should be rolled back in: the exact
    reverse of the order they were applied, with each migration type
    appearing only once (its *last* application, since a rollback of
    the most recent one also undoes anything an earlier one of the
    same type would need to."""
    seen: list[MigrationType] = []
    for migration_type in reversed(applied):
        if migration_type not in seen:
            seen.append(migration_type)
    return seen


__all__ = ["plan_rollback_order"]
