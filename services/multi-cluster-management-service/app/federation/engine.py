"""Cross-cluster distribution planning.

**A resource is never distributed to its own source.** Federating a
secret or config from cluster A back onto cluster A is not
cross-cluster federation, it is a no-op dressed up as one, and a caller
that included the source in its own target list made a mistake worth
surfacing rather than silently absorbing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID


class DistributionRefusal:
    NO_TARGETS = "no_targets"


@dataclass(frozen=True, slots=True)
class DistributionPlan:
    source_cluster_id: UUID
    target_cluster_ids: tuple[UUID, ...]
    refusal: str | None
    detail: str

    @property
    def is_planned(self) -> bool:
        return self.refusal is None


def plan_distribution(
    source_cluster_id: UUID, requested_target_ids: Sequence[UUID]
) -> DistributionPlan:
    """Plan distributing one resource from *source_cluster_id* to every
    other cluster in *requested_target_ids*.

    The source is excluded from its own target list even if a caller
    included it, and duplicates are collapsed -- the resulting order
    matches first appearance in *requested_target_ids*.
    """
    seen: set[UUID] = set()
    targets: list[UUID] = []
    for target_id in requested_target_ids:
        if target_id == source_cluster_id or target_id in seen:
            continue
        seen.add(target_id)
        targets.append(target_id)

    if not targets:
        return DistributionPlan(
            source_cluster_id=source_cluster_id,
            target_cluster_ids=(),
            refusal=DistributionRefusal.NO_TARGETS,
            detail="No distinct target clusters remain after excluding the source.",
        )
    return DistributionPlan(
        source_cluster_id=source_cluster_id,
        target_cluster_ids=tuple(targets),
        refusal=None,
        detail=f"Distributing to {len(targets)} target cluster(s).",
    )


__all__ = ["DistributionPlan", "DistributionRefusal", "plan_distribution"]
