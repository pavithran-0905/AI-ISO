"""Disaster recovery plan sequencing and compliance classification.

**Recovery order is a topological sort, never the order groups were
declared in.** A plan authored with the database group listed after the
API group but declared as a *dependency* of it must still recover the
database first -- the declared list order is authoring convenience, not
the answer, and treating it as the answer is how a recovery brings up a
service pointed at a database that is not there yet.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.models.enums import ComplianceStatus


class SequencingRefusal:
    CYCLE_DETECTED = "cycle_detected"
    UNKNOWN_DEPENDENCY = "unknown_dependency"


@dataclass(frozen=True, slots=True)
class SequencingResult:
    """The recovery order, or precisely why one could not be computed."""

    order: tuple[str, ...]
    refused: str | None
    detail: str | None

    @property
    def is_sequenced(self) -> bool:
        return self.refused is None


def sequence_recovery_groups(
    group_names: Sequence[str], dependencies: Mapping[str, Sequence[str]]
) -> SequencingResult:
    """Order recovery groups so every group comes after everything it
    depends on.

    ``dependencies[group]`` names the groups that must be recovered
    *before* ``group``. Ties (groups with no ordering constraint between
    them) are broken alphabetically, so the same plan always sequences
    identically regardless of dict iteration order.
    """
    known = set(group_names)
    for group, deps in dependencies.items():
        if group not in known:
            return SequencingResult(
                order=(),
                refused=SequencingRefusal.UNKNOWN_DEPENDENCY,
                detail=f"Dependency list names unknown group {group!r}.",
            )
        for dep in deps:
            if dep not in known:
                return SequencingResult(
                    order=(),
                    refused=SequencingRefusal.UNKNOWN_DEPENDENCY,
                    detail=f"Group {group!r} depends on unknown group {dep!r}.",
                )

    permanent: list[str] = []
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return False
        if node in done:
            return True
        visiting.add(node)
        for dep in sorted(dependencies.get(node, ())):
            if not visit(dep):
                return False
        visiting.discard(node)
        done.add(node)
        permanent.append(node)
        return True

    for group in sorted(known):
        if not visit(group):
            return SequencingResult(
                order=(),
                refused=SequencingRefusal.CYCLE_DETECTED,
                detail=f"A dependency cycle involves group {group!r}.",
            )

    return SequencingResult(order=tuple(permanent), refused=None, detail=None)


def classify_compliance(*, target_minutes: int, achieved_minutes: float | None) -> ComplianceStatus:
    """Whether a measured recovery met its RPO or RTO target.

    ``achieved_minutes is None`` means the objective was never actually
    measured against a real drill or failover -- reported as
    ``NOT_MEASURED``, never assumed met. A target that has never been
    tested is a promise, not a fact.
    """
    if achieved_minutes is None:
        return ComplianceStatus.NOT_MEASURED
    return ComplianceStatus.MET if achieved_minutes <= target_minutes else ComplianceStatus.VIOLATED


__all__ = [
    "SequencingRefusal",
    "SequencingResult",
    "classify_compliance",
    "sequence_recovery_groups",
]
