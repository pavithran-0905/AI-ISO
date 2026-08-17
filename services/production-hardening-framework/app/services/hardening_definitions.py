"""Hardening profile definitions."""

from __future__ import annotations

from uuid import UUID

from app.models.enums import CisBenchmark, HardeningTargetType
from app.models.hardening_definitions import HardeningProfile
from app.repositories.hardening_definitions import HardeningProfileRepository


class HardeningProfileService:
    def __init__(self, repo: HardeningProfileRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        name: str,
        target_type: HardeningTargetType,
        benchmark: CisBenchmark,
        description: str = "",
    ) -> HardeningProfile:
        return await self._repo.create(
            HardeningProfile(
                organization_id=organization_id,
                name=name,
                target_type=target_type,
                benchmark=benchmark,
                description=description,
            )
        )


__all__ = ["HardeningProfileService"]
