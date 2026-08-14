"""Remote configuration authoring and resolution.

Like app version policy, there is no ``POST`` route -- configuration
entries are administratively authored (or, in tests, created directly
through this service) and only ever read over HTTP.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.configuration.engine import ConfigurationEntry, resolve_configuration
from app.models.configuration import MobileConfiguration
from app.models.enums import MobilePlatform
from app.repositories.configuration import MobileConfigurationRepository


class ConfigurationService:
    def __init__(self, repo: MobileConfigurationRepository) -> None:
        self._repo = repo

    async def create_entry(
        self,
        organization_id: UUID,
        *,
        key: str,
        value: dict[str, Any],
        environment: str = "production",
        platform: MobilePlatform | None = None,
        is_enabled: bool = True,
        rollback_of_id: UUID | None = None,
    ) -> MobileConfiguration:
        return await self._repo.create(
            MobileConfiguration(
                organization_id=organization_id,
                key=key,
                value=value,
                environment=environment,
                platform=platform,
                is_enabled=is_enabled,
                rollback_of_id=rollback_of_id,
            )
        )

    async def resolve(
        self, organization_id: UUID, *, platform: MobilePlatform, environment: str
    ) -> dict[str, Any]:
        rows = await self._repo.list_for_environment(organization_id, environment=environment)
        entries = [
            ConfigurationEntry(
                key=row.key,
                value=row.value,
                environment=row.environment,
                platform=MobilePlatform(row.platform) if row.platform is not None else None,
                is_enabled=row.is_enabled,
            )
            for row in rows
        ]
        return resolve_configuration(entries, platform=platform, environment=environment)


__all__ = ["ConfigurationService"]
