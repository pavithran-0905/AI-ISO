"""Application/container deployment onto edge devices."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import ApplicationDeploymentStrategy, ApplicationStatus
from app.models.operations import EdgeApplication
from app.repositories.operations import EdgeApplicationRepository


class ApplicationService:
    def __init__(self, repo: EdgeApplicationRepository) -> None:
        self._repo = repo

    async def deploy(
        self,
        organization_id: UUID,
        *,
        device_id: UUID,
        name: str,
        version_label: str,
        deployment_strategy: ApplicationDeploymentStrategy,
    ) -> EdgeApplication:
        return await self._repo.create(
            EdgeApplication(
                organization_id=organization_id,
                device_id=device_id,
                name=name,
                version_label=version_label,
                deployment_strategy=deployment_strategy,
                status=ApplicationStatus.PENDING,
            )
        )

    async def mark_deployed(
        self, application: EdgeApplication, *, now: datetime
    ) -> EdgeApplication:
        application.status = ApplicationStatus.DEPLOYED
        application.deployed_at = now
        return await self._repo.update(application)

    async def mark_failed(self, application: EdgeApplication) -> EdgeApplication:
        application.status = ApplicationStatus.FAILED
        return await self._repo.update(application)


__all__ = ["ApplicationService"]
