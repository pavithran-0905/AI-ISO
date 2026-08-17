"""Upgrade plan dependency version checks."""

from __future__ import annotations

from uuid import UUID

from app.dependencies.engine import classify_dependency_check
from app.models.upgrade import UpgradeDependency
from app.repositories.upgrade import UpgradeDependencyRepository


class UpgradeDependencyService:
    def __init__(self, repo: UpgradeDependencyRepository) -> None:
        self._repo = repo

    async def check(
        self,
        organization_id: UUID,
        *,
        upgrade_plan_id: UUID,
        dependency_name: str,
        required_version: str,
        found_version: str,
    ) -> UpgradeDependency:
        status = classify_dependency_check(
            required_version=required_version, found_version=found_version
        )
        return await self._repo.create(
            UpgradeDependency(
                organization_id=organization_id,
                upgrade_plan_id=upgrade_plan_id,
                dependency_name=dependency_name,
                required_version=required_version,
                found_version=found_version,
                status=status,
            )
        )


__all__ = ["UpgradeDependencyService"]
