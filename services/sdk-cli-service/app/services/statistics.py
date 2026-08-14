"""Statistics rollup: idempotent per-window aggregation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.reporting import CliStatistic
from app.repositories.reporting import CliStatisticRepository


class StatisticsService:
    """Rolls up one organization's SDK/CLI activity for one window,
    idempotently."""

    def __init__(self, repo: CliStatisticRepository) -> None:
        self._repo = repo

    async def roll_up_window(
        self,
        organization_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        sdk_download_count: int,
        cli_download_count: int,
        command_execution_count: int,
        plugin_install_count: int,
        auth_success_count: int,
        auth_failure_count: int,
    ) -> CliStatistic:
        existing = await self._repo.find_window(organization_id, window_start=window_start)
        if existing is None:
            existing = CliStatistic(
                organization_id=organization_id, window_start=window_start, window_end=window_end
            )
            existing = await self._repo.create(existing)

        existing.window_end = window_end
        existing.sdk_download_count = sdk_download_count
        existing.cli_download_count = cli_download_count
        existing.command_execution_count = command_execution_count
        existing.plugin_install_count = plugin_install_count
        existing.auth_success_count = auth_success_count
        existing.auth_failure_count = auth_failure_count
        return await self._repo.update(existing)


__all__ = ["StatisticsService"]
