"""Disaster recovery planning: plan authoring, recovery sequencing, DR
test execution, and RPO/RTO compliance reporting.

Wires ``app.dr_plans.engine``'s pure sequencing and compliance
classification onto the repositories that persist plans, tests, and
recovery reports, and publishes ``DRTestCompleted`` /
``RecoveryValidated``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.dr_plans.engine import SequencingResult, classify_compliance, sequence_recovery_groups
from app.events.domain_events import DRTestCompletedEvent, RecoveryValidatedEvent
from app.models.enums import (
    ComplianceStatus,
    DrPlanStatus,
    DrTestKind,
    DrTestStatus,
    RecoveryPriority,
)
from app.models.recovery import DrPlan, DrTest, RecoveryReport
from app.repositories.recovery import DrPlanRepository, DrTestRepository, RecoveryReportRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "backup-dr-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class DrPlanService:
    """Authors DR plans and computes their recovery sequencing."""

    def __init__(self, repo: DrPlanRepository) -> None:
        self._repo = repo

    async def create_plan(
        self,
        organization_id: UUID,
        *,
        name: str,
        description: str | None,
        priority: RecoveryPriority,
        rpo_minutes: int,
        rto_minutes: int,
        recovery_groups: list[dict[str, object]],
        dependencies: dict[str, list[str]],
        owner: str | None,
    ) -> DrPlan:
        group_names = [str(group["name"]) for group in recovery_groups]
        sequencing = sequence_recovery_groups(group_names, dependencies)
        return await self._repo.create(
            DrPlan(
                organization_id=organization_id,
                name=name,
                description=description,
                status=DrPlanStatus.DRAFT,
                priority=priority,
                rpo_minutes=rpo_minutes,
                rto_minutes=rto_minutes,
                recovery_groups=recovery_groups,
                dependencies=dependencies,
                owner=owner,
                labels={"sequencing_valid": str(sequencing.is_sequenced)},
            )
        )

    def sequence(self, plan: DrPlan) -> SequencingResult:
        group_names = [str(group["name"]) for group in plan.recovery_groups]
        return sequence_recovery_groups(group_names, plan.dependencies)


class DrTestService:
    """Runs DR drills and records their measured RPO/RTO against the
    plan's targets."""

    def __init__(
        self,
        repo: DrTestRepository,
        plan_repo: DrPlanRepository,
        *,
        publish: EventPublisher = _noop_publisher,
    ) -> None:
        self._repo = repo
        self._plan_repo = plan_repo
        self._publish = publish

    async def run_test(
        self,
        organization_id: UUID,
        *,
        dr_plan: DrPlan,
        test_kind: DrTestKind,
        achieved_rpo_minutes: float | None,
        achieved_rto_minutes: float | None,
        findings: list[dict[str, object]],
        summary: str | None,
        started_at: datetime,
        completed_at: datetime,
    ) -> DrTest:
        rpo_status = classify_compliance(
            target_minutes=dr_plan.rpo_minutes, achieved_minutes=achieved_rpo_minutes
        )
        rto_status = classify_compliance(
            target_minutes=dr_plan.rto_minutes, achieved_minutes=achieved_rto_minutes
        )
        overall = (
            DrTestStatus.PASSED
            if rpo_status is not ComplianceStatus.VIOLATED
            and rto_status is not ComplianceStatus.VIOLATED
            else DrTestStatus.FAILED
        )
        test = await self._repo.create(
            DrTest(
                organization_id=organization_id,
                dr_plan_id=dr_plan.id,
                test_kind=test_kind,
                status=overall,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=(completed_at - started_at).total_seconds() * 1000.0,
                achieved_rpo_minutes=achieved_rpo_minutes,
                achieved_rto_minutes=achieved_rto_minutes,
                rpo_status=rpo_status,
                rto_status=rto_status,
                findings=findings,
                summary=summary,
            )
        )
        dr_plan.last_tested_at = completed_at
        await self._plan_repo.update(dr_plan)

        await self._publish(
            DRTestCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "dr_test_id": str(test.id),
                    "dr_plan_id": str(dr_plan.id),
                    "status": str(overall),
                    "rpo_status": str(rpo_status),
                    "rto_status": str(rto_status),
                },
            )
        )
        return test


class RecoveryReportService:
    """Assembles the compliance-facing summary of one DR test or
    failover."""

    def __init__(
        self, repo: RecoveryReportRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def generate_for_test(
        self, organization_id: UUID, dr_test: DrTest, dr_plan: DrPlan, *, now: datetime
    ) -> RecoveryReport:
        overall_status = (
            ComplianceStatus.MET
            if dr_test.rpo_status is ComplianceStatus.MET
            and dr_test.rto_status is ComplianceStatus.MET
            else (
                ComplianceStatus.VIOLATED
                if ComplianceStatus.VIOLATED in (dr_test.rpo_status, dr_test.rto_status)
                else ComplianceStatus.NOT_MEASURED
            )
        )
        report = await self._repo.create(
            RecoveryReport(
                organization_id=organization_id,
                dr_test_id=dr_test.id,
                rpo_target_minutes=dr_plan.rpo_minutes,
                rpo_achieved_minutes=dr_test.achieved_rpo_minutes,
                rto_target_minutes=dr_plan.rto_minutes,
                rto_achieved_minutes=dr_test.achieved_rto_minutes,
                compliance_status=overall_status,
                summary=dr_test.summary,
                generated_at=now,
            )
        )
        await self._publish(
            RecoveryValidatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "recovery_report_id": str(report.id),
                    "compliance_status": str(overall_status),
                },
            )
        )
        return report


__all__ = ["DrPlanService", "DrTestService", "RecoveryReportService"]
