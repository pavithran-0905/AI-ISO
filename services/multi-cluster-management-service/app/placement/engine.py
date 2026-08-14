"""Workload placement: affinity/anti-affinity evaluation across the
fleet.

**A candidate must satisfy every required label and violate none of the
forbidden ones -- there is no partial credit.** A placement engine that
scored "8 of 10 required labels matched" as good enough would place a
workload somewhere its own stated requirements say it should not run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PlacementCandidate:
    """One cluster as the placement engine needs to see it."""

    cluster_id: UUID
    labels: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class PlacementEvaluation:
    is_eligible: bool
    unmet_requirements: tuple[str, ...]
    violated_exclusions: tuple[str, ...]


def evaluate_affinity(
    cluster_labels: Mapping[str, str],
    *,
    required_labels: Mapping[str, str],
    forbidden_labels: Mapping[str, str],
) -> PlacementEvaluation:
    """Whether one cluster satisfies a workload's affinity rules.

    A required label must be present on the cluster with exactly the
    required value; a forbidden label fails eligibility if present with
    exactly the forbidden value (a forbidden key present with a
    *different* value does not violate the exclusion -- the rule names a
    specific value to avoid, not the key's mere existence).
    """
    unmet = tuple(key for key, value in required_labels.items() if cluster_labels.get(key) != value)
    violated = tuple(
        key for key, value in forbidden_labels.items() if cluster_labels.get(key) == value
    )
    return PlacementEvaluation(
        is_eligible=not unmet and not violated,
        unmet_requirements=unmet,
        violated_exclusions=violated,
    )


def select_placement_candidates(
    candidates: Sequence[PlacementCandidate],
    *,
    required_labels: Mapping[str, str],
    forbidden_labels: Mapping[str, str],
) -> tuple[UUID, ...]:
    """Every candidate cluster eligible for a workload, in the order
    given."""
    return tuple(
        candidate.cluster_id
        for candidate in candidates
        if evaluate_affinity(
            candidate.labels, required_labels=required_labels, forbidden_labels=forbidden_labels
        ).is_eligible
    )


__all__ = [
    "PlacementCandidate",
    "PlacementEvaluation",
    "evaluate_affinity",
    "select_placement_candidates",
]
