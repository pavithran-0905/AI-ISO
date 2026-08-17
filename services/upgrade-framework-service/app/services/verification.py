"""Health-gate verification.

A caller-reported-outcome service, the same shape
``services/installation-deployment-service``'s own ``PreflightService``/
``VerificationService`` used (Prompt 075): this process can only
genuinely probe infrastructure it already holds a live connection to;
everything else docs/076 names under HEALTH-GATED UPGRADES needs a
target's own health probe to report back.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import CheckResultStatus, VerificationCheckType
from app.models.verification import VerificationResult
from app.repositories.verification import VerificationResultRepository
from app.verification.engine import aggregate_check_results


class VerificationService:
    def __init__(self, repo: VerificationResultRepository) -> None:
        self._repo = repo

    async def record_result(
        self,
        organization_id: UUID,
        *,
        upgrade_job_id: UUID,
        check_type: VerificationCheckType,
        status: CheckResultStatus,
        detail: str = "",
        now: datetime,
    ) -> VerificationResult:
        return await self._repo.create(
            VerificationResult(
                organization_id=organization_id,
                upgrade_job_id=upgrade_job_id,
                check_type=check_type,
                status=status,
                detail=detail,
                verified_at=now,
            )
        )

    async def compute_overall(self, upgrade_job_id: UUID) -> CheckResultStatus:
        results = await self._repo.list_for_job(upgrade_job_id)
        return aggregate_check_results(CheckResultStatus(result.status) for result in results)


__all__ = ["VerificationService"]
