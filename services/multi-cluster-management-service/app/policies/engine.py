"""Policy targeting and drift detection.

**A policy must name at least one target.** A policy with neither a
cluster nor a group id would either apply to nothing (silently useless)
or, if a caller elsewhere assumed "no target means everything," apply to
the entire fleet by accident -- refused outright instead.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID


class TargetRefusal:
    NO_TARGET = "no_target"


@dataclass(frozen=True, slots=True)
class TargetResolution:
    target_cluster_ids: tuple[UUID, ...]
    refusal: str | None
    detail: str

    @property
    def is_resolved(self) -> bool:
        return self.refusal is None


def resolve_targets(
    *,
    cluster_id: UUID | None,
    group_id: UUID | None,
    cluster_ids_in_group: Sequence[UUID] = (),
) -> TargetResolution:
    """The concrete set of clusters one policy applies to.

    A cluster-scoped policy targets exactly that cluster. A group-scoped
    policy targets every cluster currently in the group -- membership is
    resolved by the caller and passed in, since the engine itself has no
    database access and group membership can change between calls.
    """
    if cluster_id is not None:
        return TargetResolution(
            target_cluster_ids=(cluster_id,),
            refusal=None,
            detail="Targets one cluster directly.",
        )
    if group_id is not None:
        return TargetResolution(
            target_cluster_ids=tuple(cluster_ids_in_group),
            refusal=None,
            detail=f"Targets {len(cluster_ids_in_group)} cluster(s) in the group.",
        )
    return TargetResolution(
        target_cluster_ids=(),
        refusal=TargetRefusal.NO_TARGET,
        detail="A policy must target either a specific cluster or a cluster group.",
    )


def detect_drift(desired_definition_hash: str, live_state_hash: str | None) -> bool:
    """Whether a cluster's live policy state has drifted from what was
    propagated.

    ``live_state_hash is None`` (never observed) is **not** drift -- it
    means propagation has not been confirmed yet, which is a different
    fact from "confirmed, and it no longer matches."
    """
    if live_state_hash is None:
        return False
    return live_state_hash != desired_definition_hash


__all__ = ["TargetRefusal", "TargetResolution", "detect_drift", "resolve_targets"]
