"""Device configuration versioning and rollback.

Wires ``app.configuration.engine``'s pure rollback validation onto the
repository that persists each applied configuration version as its own
immutable row.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.configuration.engine import RollbackValidation, validate_rollback
from app.models.operations import EdgeConfiguration
from app.repositories.operations import EdgeConfigurationRepository


class RollbackRefusedError(Exception):
    def __init__(self, validation: RollbackValidation) -> None:
        super().__init__(validation.detail)
        self.validation = validation


class ConfigurationService:
    def __init__(self, repo: EdgeConfigurationRepository) -> None:
        self._repo = repo

    async def apply(
        self,
        organization_id: UUID,
        *,
        device_id: UUID,
        config_key: str,
        config_value: dict[str, object],
        revision: int,
        now: datetime,
    ) -> EdgeConfiguration:
        active = await self._repo.active_for_key(device_id, config_key=config_key)
        if active is not None:
            active.is_current = False
            await self._repo.update(active)
        return await self._repo.create(
            EdgeConfiguration(
                organization_id=organization_id,
                device_id=device_id,
                config_key=config_key,
                config_value=config_value,
                revision=revision,
                is_current=True,
                applied_at=now,
            )
        )

    async def roll_back(
        self,
        device_id: UUID,
        *,
        config_key: str,
        target_revision: int,
        now: datetime,
    ) -> EdgeConfiguration:
        """Reactivate an earlier applied configuration revision.

        Raises:
            RollbackRefusedError: If *target_revision* was never applied,
                or is already the active revision.
        """
        revisions = await self._repo.list_for_device(device_id)
        matching = [row for row in revisions if row.config_key == config_key]
        active = next((row for row in matching if row.is_current), None)
        target = next((row for row in matching if row.revision == target_revision), None)

        validation = validate_rollback(
            target_revision,
            current_version=active.revision if active is not None else 0,
            known_versions=frozenset(row.revision for row in matching),
        )
        if not validation.is_valid or target is None:
            raise RollbackRefusedError(validation)

        if active is not None:
            active.is_current = False
            await self._repo.update(active)
        target.is_current = True
        target.applied_at = now
        return await self._repo.update(target)


__all__ = ["ConfigurationService", "RollbackRefusedError"]
