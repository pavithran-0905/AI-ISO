"""Release distributions and the regions they target."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.distribution import ReleaseDistribution, ReleaseRegion
from app.models.enums import DistributionStatus, DistributionType
from app.repositories.distribution import ReleaseDistributionRepository, ReleaseRegionRepository


class ReleaseDistributionService:
    def __init__(self, repo: ReleaseDistributionRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        release_version_id: UUID,
        distribution_type: DistributionType,
        target: str = "",
    ) -> ReleaseDistribution:
        return await self._repo.create(
            ReleaseDistribution(
                organization_id=organization_id,
                release_version_id=release_version_id,
                distribution_type=distribution_type,
                target=target,
            )
        )

    async def complete(
        self, distribution: ReleaseDistribution, *, now: datetime
    ) -> ReleaseDistribution:
        distribution.status = DistributionStatus.COMPLETED
        distribution.distributed_at = now
        return await self._repo.update(distribution)


class ReleaseRegionService:
    def __init__(self, repo: ReleaseRegionRepository) -> None:
        self._repo = repo

    async def create(self, organization_id: UUID, *, name: str, region_code: str) -> ReleaseRegion:
        return await self._repo.create(
            ReleaseRegion(organization_id=organization_id, name=name, region_code=region_code)
        )


__all__ = ["ReleaseDistributionService", "ReleaseRegionService"]
