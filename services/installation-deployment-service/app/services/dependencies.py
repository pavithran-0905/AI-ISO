"""Dependency version-compatibility checks."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.dependencies.engine import classify_dependency_check
from app.models.validation import DependencyCheck
from app.repositories.validation import DependencyCheckRepository


class DependencyCheckService:
    def __init__(self, repo: DependencyCheckRepository) -> None:
        self._repo = repo

    async def check(
        self,
        organization_id: UUID,
        *,
        dependency_name: str,
        required_version: str,
        found_version: str,
        installation_session_id: UUID | None = None,
        now: datetime,
    ) -> DependencyCheck:
        status = classify_dependency_check(
            required_version=required_version, found_version=found_version
        )
        return await self._repo.create(
            DependencyCheck(
                organization_id=organization_id,
                installation_session_id=installation_session_id,
                dependency_name=dependency_name,
                required_version=required_version,
                found_version=found_version,
                status=status,
                checked_at=now,
            )
        )


__all__ = ["DependencyCheckService"]
