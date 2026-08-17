"""Aggregate production readiness computation.

Shared by ``GET /production-readiness`` (computed live, never
persisted -- docs/079's own DATABASE TABLES section has no dedicated
table for this endpoint's own result) and ``ProductionReadinessSweepWorker``
(which uses the same computation to detect the edge-triggered moment an
organization first crosses the "ready" threshold).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.analytics.engine import hardening_score, is_production_ready, production_readiness_score
from app.compliance.engine import compliance_rate as compute_compliance_rate
from app.models.enums import CheckResultStatus
from app.operational_readiness.engine import readiness_rate
from app.services.bundle import Repositories

_SAMPLE_LIMIT = 200


@dataclass(frozen=True, slots=True)
class ProductionReadinessResult:
    score: float
    is_ready: bool
    hardening_rate: float
    compliance_rate: float
    operational_readiness_rate: float
    disaster_recovery_rate: float


class ProductionReadinessService:
    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    async def compute(
        self, organization_id: UUID, *, threshold: float
    ) -> ProductionReadinessResult:
        hardening_results = await self._repos.hardening_results.list_recent(
            organization_id, limit=_SAMPLE_LIMIT
        )
        h_passed = sum(
            1
            for row in hardening_results
            if CheckResultStatus(row.status) == CheckResultStatus.PASSED
        )
        h_rate = hardening_score(h_passed, len(hardening_results))

        compliance_results = await self._repos.compliance_results.list_all(
            organization_id, limit=_SAMPLE_LIMIT
        )
        c_compliant = sum(1 for row in compliance_results if row.is_compliant)
        c_rate = compute_compliance_rate(c_compliant, len(compliance_results))

        operational_checks = await self._repos.operational_readiness.list_all(
            organization_id, limit=_SAMPLE_LIMIT
        )
        o_passed = sum(
            1
            for row in operational_checks
            if CheckResultStatus(row.status) == CheckResultStatus.PASSED
        )
        o_rate = readiness_rate(o_passed, len(operational_checks))

        dr_checks = await self._repos.disaster_recovery_checks.list_all(
            organization_id, limit=_SAMPLE_LIMIT
        )
        dr_passed = sum(
            1 for row in dr_checks if CheckResultStatus(row.status) == CheckResultStatus.PASSED
        )
        dr_rate = readiness_rate(dr_passed, len(dr_checks))

        score = production_readiness_score(
            hardening_rate=h_rate,
            compliance_rate=c_rate,
            operational_readiness_rate=o_rate,
            dr_rate=dr_rate,
        )
        return ProductionReadinessResult(
            score=score,
            is_ready=is_production_ready(score, threshold=threshold),
            hardening_rate=h_rate,
            compliance_rate=c_rate,
            operational_readiness_rate=o_rate,
            disaster_recovery_rate=dr_rate,
        )


__all__ = ["ProductionReadinessResult", "ProductionReadinessService"]
