"""Migration execution: schema/config/plugin/API/data-transformation
steps carried out during an upgrade job.

Publishes ``MigrationCompleted`` on every terminal migration status,
and notifies Migration Failed directly on a ``FAILED`` one.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.events.domain_events import MigrationCompletedEvent
from app.models.enums import MigrationType, UpgradeJobStatus
from app.models.migrations import ConfigurationMigration, MigrationHistory, PluginMigration
from app.repositories.migrations import (
    ConfigurationMigrationRepository,
    MigrationHistoryRepository,
    PluginMigrationRepository,
)
from app.services.notifications import UpgradeNotifier
from app.types import EventPublisher
from app.upgrade.engine import TransitionResult, validate_transition

_SOURCE_SERVICE = "upgrade-framework-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class MigrationService:
    def __init__(
        self,
        repo: MigrationHistoryRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: UpgradeNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def start(
        self,
        organization_id: UUID,
        *,
        upgrade_job_id: UUID,
        migration_type: MigrationType,
        now: datetime,
    ) -> MigrationHistory:
        return await self._repo.create(
            MigrationHistory(
                organization_id=organization_id,
                upgrade_job_id=upgrade_job_id,
                migration_type=migration_type,
                status=UpgradeJobStatus.RUNNING,
                started_at=now,
            )
        )

    async def complete(
        self, migration: MigrationHistory, *, status: UpgradeJobStatus, now: datetime
    ) -> MigrationHistory:
        result = validate_transition(migration.status, status)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        migration.status = status
        migration.completed_at = now
        migration = await self._repo.update(migration)
        await self._publish(
            MigrationCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=migration.organization_id,
                payload={
                    "upgrade_job_id": str(migration.upgrade_job_id),
                    "migration_type": str(migration.migration_type),
                    "status": status.value,
                },
            )
        )
        if status == UpgradeJobStatus.FAILED and self._notifier is not None:
            await self._notifier.notify_migration_failed(
                migration_type=str(migration.migration_type), detail="migration step failed"
            )
        return migration


class ConfigurationMigrationService:
    def __init__(self, repo: ConfigurationMigrationRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        upgrade_job_id: UUID,
        config_key: str,
        old_value: dict[str, Any],
        new_value: dict[str, Any],
        now: datetime,
    ) -> ConfigurationMigration:
        return await self._repo.create(
            ConfigurationMigration(
                organization_id=organization_id,
                upgrade_job_id=upgrade_job_id,
                config_key=config_key,
                old_value=old_value,
                new_value=new_value,
                applied_at=now,
            )
        )


class PluginMigrationService:
    def __init__(self, repo: PluginMigrationRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        upgrade_job_id: UUID,
        plugin_name: str,
        from_version: str,
        to_version: str,
        status: UpgradeJobStatus = UpgradeJobStatus.SUCCEEDED,
    ) -> PluginMigration:
        return await self._repo.create(
            PluginMigration(
                organization_id=organization_id,
                upgrade_job_id=upgrade_job_id,
                plugin_name=plugin_name,
                from_version=from_version,
                to_version=to_version,
                status=status,
            )
        )


__all__ = [
    "ConfigurationMigrationService",
    "MigrationService",
    "PluginMigrationService",
    "TransitionRefusedError",
]
