"""CLI update attempts.

Wires ``app.cli.engine``'s pure transition table onto the repository
that persists update attempts. **This service records an update
attempt's outcome; it never downloads or applies a real CLI binary
itself** -- see this package's README "Scope boundary".
``PENDING -> DOWNLOADING`` always happens; whether the attempt then
reaches ``APPLIED`` or ``FAILED`` is reported by the caller, exactly
the pattern ``services/license-billing-service``'s own
``PaymentCreateRequest.succeeded`` established. Publishes
``CLIDownloaded`` only when an attempt actually reaches ``APPLIED``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import CliDownloadedEvent
from app.models.cli import CliUpdate
from app.models.enums import CliUpdateStatus
from app.repositories.cli import CliUpdateRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "sdk-cli-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class CliUpdateService:
    def __init__(
        self, repo: CliUpdateRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def attempt_update(
        self,
        organization_id: UUID,
        *,
        from_version: str,
        to_version: str,
        succeeded: bool,
        now: datetime,
    ) -> CliUpdate:
        update = await self._repo.create(
            CliUpdate(
                organization_id=organization_id,
                from_version=from_version,
                to_version=to_version,
                checked_at=now,
            )
        )

        # This method fully controls its own sequence -- PENDING ->
        # DOWNLOADING -> APPLIED/FAILED -- so every step here is one
        # ``app.cli.engine.ALLOWED_TRANSITIONS`` already guarantees is
        # valid; ``app.cli.engine``'s own tests cover the table itself.
        update.status = CliUpdateStatus.DOWNLOADING
        await self._repo.update(update)

        update.status = CliUpdateStatus.APPLIED if succeeded else CliUpdateStatus.FAILED
        if succeeded:
            update.applied_at = now
        await self._repo.update(update)

        if succeeded:
            await self._publish(
                CliDownloadedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=organization_id,
                    payload={"cli_update_id": str(update.id), "to_version": to_version},
                )
            )
        return update


__all__ = ["CliUpdateService"]
