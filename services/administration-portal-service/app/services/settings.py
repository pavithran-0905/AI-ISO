"""Platform settings and system configuration.

Configuration changes publish ``ConfigurationChanged``; platform
settings have no matching domain event since docs/070 does not name
one for them -- they are simple key/value administrative state.
"""

from __future__ import annotations

from uuid import UUID

from app.events.domain_events import ConfigurationChangedEvent, FeatureFlagUpdatedEvent
from app.models.settings import FeatureFlag, PlatformSetting, SystemConfiguration
from app.repositories.settings import (
    FeatureFlagRepository,
    PlatformSettingRepository,
    SystemConfigurationRepository,
)
from app.types import EventPublisher

_SOURCE_SERVICE = "administration-portal-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class PlatformSettingService:
    def __init__(self, repo: PlatformSettingRepository) -> None:
        self._repo = repo

    async def upsert(
        self,
        organization_id: UUID,
        *,
        key: str,
        value: dict[str, object],
        description: str | None = None,
    ) -> PlatformSetting:
        existing = await self._repo.find_by_key(organization_id, key=key)
        if existing is not None:
            existing.value = value
            if description is not None:
                existing.description = description
            return await self._repo.update(existing)
        return await self._repo.create(
            PlatformSetting(
                organization_id=organization_id, key=key, value=value, description=description
            )
        )


class SystemConfigurationService:
    def __init__(
        self, repo: SystemConfigurationRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def upsert(
        self,
        organization_id: UUID,
        *,
        key: str,
        value: dict[str, object],
        environment: str = "production",
    ) -> SystemConfiguration:
        existing = await self._repo.find_by_key(organization_id, key=key)
        if existing is not None:
            existing.value = value
            existing.environment = environment
            existing.is_validated = True
            configuration = await self._repo.update(existing)
        else:
            configuration = await self._repo.create(
                SystemConfiguration(
                    organization_id=organization_id,
                    key=key,
                    value=value,
                    environment=environment,
                    is_validated=True,
                )
            )
        await self._publish(
            ConfigurationChangedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"key": key, "environment": environment},
            )
        )
        return configuration


class FeatureFlagService:
    def __init__(
        self, repo: FeatureFlagRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def create_flag(
        self,
        organization_id: UUID,
        *,
        name: str,
        scope: str,
        target_ref: str | None = None,
        rollout_percentage: float = 100.0,
    ) -> FeatureFlag:
        return await self._repo.create(
            FeatureFlag(
                organization_id=organization_id,
                name=name,
                scope=scope,
                target_ref=target_ref,
                rollout_percentage=rollout_percentage,
            )
        )

    async def update_flag(
        self,
        flag: FeatureFlag,
        *,
        is_enabled: bool | None = None,
        is_killed: bool | None = None,
        rollout_percentage: float | None = None,
    ) -> FeatureFlag:
        if is_enabled is not None:
            flag.is_enabled = is_enabled
        if is_killed is not None:
            flag.is_killed = is_killed
        if rollout_percentage is not None:
            flag.rollout_percentage = rollout_percentage
        flag = await self._repo.update(flag)
        await self._publish(
            FeatureFlagUpdatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=flag.organization_id,
                payload={"feature_flag_id": str(flag.id), "name": flag.name},
            )
        )
        return flag


__all__ = ["FeatureFlagService", "PlatformSettingService", "SystemConfigurationService"]
