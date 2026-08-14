"""CLI plugin registration and lifecycle.

Wires ``app.cli.plugins.engine``'s pure transition table onto the
repository that persists plugins, publishing ``PluginInstalled`` on
``INSTALLED`` and ``PluginUpdated`` on every other transition.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.cli.plugins.engine import TransitionResult, validate_transition
from app.events.domain_events import PluginInstalledEvent, PluginUpdatedEvent
from app.models.cli import CliPlugin
from app.models.enums import AuditAction, PluginStatus
from app.repositories.cli import CliPluginRepository
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "sdk-cli-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class CliPluginService:
    def __init__(
        self,
        repo: CliPluginRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit

    async def register(
        self,
        organization_id: UUID,
        *,
        name: str,
        version: str,
        checksum_sha256: str,
        is_signed: bool = False,
        marketplace_ref: str | None = None,
    ) -> CliPlugin:
        return await self._repo.create(
            CliPlugin(
                organization_id=organization_id,
                name=name,
                version_label=version,
                checksum_sha256=checksum_sha256,
                is_signed=is_signed,
                marketplace_ref=marketplace_ref,
            )
        )

    async def transition(
        self, plugin: CliPlugin, *, target: PluginStatus, actor_id: str | None, now: datetime
    ) -> CliPlugin:
        """Move *plugin* to *target*, raising
        :class:`TransitionRefusedError` if the transition is not
        allowed."""
        result = validate_transition(plugin.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        plugin.status = target
        await self._repo.update(plugin)

        if self._audit is not None:
            await self._audit.record(
                organization_id=plugin.organization_id,
                action=AuditAction.PLUGIN_MANAGEMENT,
                entity_type="cli_plugin",
                entity_id=plugin.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Plugin {plugin.name!r} moved to {target.value}.",
            )

        if target == PluginStatus.INSTALLED:
            await self._publish(
                PluginInstalledEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=plugin.organization_id,
                    payload={"cli_plugin_id": str(plugin.id), "name": plugin.name},
                )
            )
        else:
            await self._publish(
                PluginUpdatedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=plugin.organization_id,
                    payload={"cli_plugin_id": str(plugin.id), "status": target.value},
                )
            )
        return plugin


__all__ = ["CliPluginService", "TransitionRefusedError"]
