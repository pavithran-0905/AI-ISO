"""Distribution type classification."""

from __future__ import annotations

from app.models.enums import DistributionType

_REGION_SCOPED_TYPES = frozenset({DistributionType.REGIONAL, DistributionType.GLOBAL})


def is_air_gapped(distribution_type: DistributionType) -> bool:
    """Whether a distribution type is inherently air-gapped -- it
    ships as an offline artifact rather than reaching a target over a
    network this platform controls."""
    return DistributionType(distribution_type) in (
        DistributionType.AIR_GAPPED,
        DistributionType.OFFLINE_EXPORT,
    )


def requires_region(distribution_type: DistributionType) -> bool:
    """Whether a distribution type is scoped to a specific
    geographic region."""
    return DistributionType(distribution_type) in _REGION_SCOPED_TYPES


__all__ = ["is_air_gapped", "requires_region"]
