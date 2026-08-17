"""Release channel configuration."""

from __future__ import annotations

from uuid import UUID

from app.models.channels import ReleaseChannelConfig
from app.models.enums import ReleaseChannelType
from app.repositories.channels import ReleaseChannelConfigRepository


class ReleaseChannelConfigService:
    def __init__(self, repo: ReleaseChannelConfigRepository) -> None:
        self._repo = repo

    async def create(
        self, organization_id: UUID, *, name: str, channel_type: ReleaseChannelType
    ) -> ReleaseChannelConfig:
        return await self._repo.create(
            ReleaseChannelConfig(
                organization_id=organization_id, name=name, channel_type=channel_type
            )
        )


__all__ = ["ReleaseChannelConfigService"]
