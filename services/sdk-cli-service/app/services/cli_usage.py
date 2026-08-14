"""CLI command execution recording."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.cli import CliUsage
from app.repositories.cli import CliUsageRepository


class CliUsageService:
    def __init__(self, repo: CliUsageRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        session_id: UUID | None,
        command_group: str,
        command: str,
        now: datetime,
        succeeded: bool = True,
    ) -> CliUsage:
        return await self._repo.create(
            CliUsage(
                organization_id=organization_id,
                session_id=session_id,
                command_group=command_group,
                command=command,
                executed_at=now,
                succeeded=succeeded,
            )
        )


__all__ = ["CliUsageService"]
