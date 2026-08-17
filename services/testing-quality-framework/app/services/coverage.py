"""Coverage report recording."""

from __future__ import annotations

from uuid import UUID

from app.models.coverage import CoverageReport
from app.models.enums import CoverageType
from app.repositories.coverage import CoverageReportRepository


class CoverageService:
    def __init__(self, repo: CoverageReportRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        coverage_type: CoverageType,
        percentage: float,
        lines_covered: int = 0,
        lines_total: int = 0,
        test_run_id: UUID | None = None,
    ) -> CoverageReport:
        return await self._repo.create(
            CoverageReport(
                organization_id=organization_id,
                test_run_id=test_run_id,
                coverage_type=coverage_type,
                percentage=percentage,
                lines_covered=lines_covered,
                lines_total=lines_total,
            )
        )


__all__ = ["CoverageService"]
