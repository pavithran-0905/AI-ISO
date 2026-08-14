"""CLI version registration.

Publishes ``CLIReleased`` when a version is registered enabled -- the
CLI has no draft/publish workflow of its own the way SDK releases do,
so registration and release are the same act.
"""

from __future__ import annotations

from uuid import UUID

from app.events.domain_events import CliReleasedEvent
from app.models.cli import CliVersion
from app.repositories.cli import CliVersionRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "sdk-cli-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class CliVersionService:
    def __init__(
        self, repo: CliVersionRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def register_version(
        self, organization_id: UUID, *, version: str, api_compatibility_version: str
    ) -> CliVersion:
        cli_version = await self._repo.create(
            CliVersion(
                organization_id=organization_id,
                version_label=version,
                api_compatibility_version=api_compatibility_version,
            )
        )
        await self._publish(
            CliReleasedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"cli_version_id": str(cli_version.id), "version": version},
            )
        )
        return cli_version


__all__ = ["CliVersionService"]
