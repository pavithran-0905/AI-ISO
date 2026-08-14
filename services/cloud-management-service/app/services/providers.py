"""Provider registration, region catalog, and provider-side project
grouping."""

from __future__ import annotations

from uuid import UUID

from app.models.accounts import CloudProject, CloudProvider, CloudRegion
from app.models.enums import CloudProviderType
from app.repositories.accounts import (
    CloudProjectRepository,
    CloudProviderRepository,
    CloudRegionRepository,
)


class CloudProviderService:
    def __init__(self, repo: CloudProviderRepository) -> None:
        self._repo = repo

    async def register_provider(
        self,
        organization_id: UUID,
        *,
        provider_type: CloudProviderType,
        name: str,
        config: dict[str, object] | None = None,
    ) -> CloudProvider:
        return await self._repo.create(
            CloudProvider(
                organization_id=organization_id,
                provider_type=provider_type,
                name=name,
                config=config or {},
            )
        )

    async def disable(self, provider: CloudProvider) -> CloudProvider:
        provider.is_enabled = False
        return await self._repo.update(provider)

    async def enable(self, provider: CloudProvider) -> CloudProvider:
        provider.is_enabled = True
        return await self._repo.update(provider)


class CloudRegionService:
    def __init__(self, repo: CloudRegionRepository) -> None:
        self._repo = repo

    async def register_region(
        self, organization_id: UUID, *, provider_id: UUID, code: str, name: str
    ) -> CloudRegion:
        return await self._repo.create(
            CloudRegion(
                organization_id=organization_id, provider_id=provider_id, code=code, name=name
            )
        )


class CloudProjectService:
    def __init__(self, repo: CloudProjectRepository) -> None:
        self._repo = repo

    async def register_project(
        self, organization_id: UUID, *, account_id: UUID, external_project_id: str, name: str
    ) -> CloudProject:
        return await self._repo.create(
            CloudProject(
                organization_id=organization_id,
                account_id=account_id,
                external_project_id=external_project_id,
                name=name,
            )
        )


__all__ = ["CloudProjectService", "CloudProviderService", "CloudRegionService"]
