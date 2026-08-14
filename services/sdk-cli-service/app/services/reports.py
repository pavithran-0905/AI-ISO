"""Report generation: SDK, CLI, usage, download, compatibility, plugin,
and audit reports."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import ReportFormat, ReportKind, ReportStatus
from app.models.reporting import CliReport
from app.repositories.reporting import CliReportRepository


class ReportService:
    """Generates and persists one report."""

    def __init__(self, repo: CliReportRepository) -> None:
        self._repo = repo

    async def generate(
        self,
        organization_id: UUID,
        *,
        kind: ReportKind,
        title: str,
        report_format: ReportFormat,
        period_start: datetime | None,
        period_end: datetime | None,
        content: dict[str, object],
        row_count: int | None,
        generated_by: str | None,
        now: datetime,
    ) -> CliReport:
        return await self._repo.create(
            CliReport(
                organization_id=organization_id,
                kind=kind,
                report_format=report_format,
                title=title,
                status=ReportStatus.COMPLETED,
                period_start=period_start,
                period_end=period_end,
                content=content,
                row_count=row_count,
                generated_by=generated_by,
                generated_at=now,
            )
        )


__all__ = ["ReportService"]
