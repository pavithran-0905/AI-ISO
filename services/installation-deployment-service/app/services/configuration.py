"""Configuration wizard profiles -- upserted by name, one row per
wizard step a caller has completed."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models.configuration import ConfigurationProfile
from app.models.enums import ConfigurationSection
from app.repositories.configuration import ConfigurationProfileRepository


class ConfigurationProfileService:
    def __init__(self, repo: ConfigurationProfileRepository) -> None:
        self._repo = repo

    async def save(
        self,
        organization_id: UUID,
        *,
        name: str,
        section: ConfigurationSection,
        config: dict[str, Any],
    ) -> ConfigurationProfile:
        existing = await self._repo.find_by_name(organization_id, name=name)
        if existing is not None:
            existing.section = section
            existing.config = config
            return await self._repo.update(existing)
        return await self._repo.create(
            ConfigurationProfile(
                organization_id=organization_id, name=name, section=section, config=config
            )
        )


__all__ = ["ConfigurationProfileService"]
