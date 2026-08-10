"""Optimization, evaluation, statistics, reporting, and audit
(docs/061 "PROMPT OPTIMIZATION", "PROMPT EVALUATION", "ANALYTICS",
"REPORTING", "AUDIT").
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar
from uuid import UUID

from shared_core.exceptions.conflict import ConflictError
from shared_core.logging.logger import get_logger

from app.evaluation import scoring
from app.events.prompt_events import (
    PromptEvaluatedEvent,
    PromptExecutedEvent,
    PromptOptimizedEvent,
)
from app.models.analytics import (
    PromptAudit,
    PromptOptimization,
    PromptReport,
    PromptStatistic,
)
from app.models.enums import (
    AuditAction,
    ExecutionStatus,
    OptimizationStatus,
    PromptLifecycleStatus,
    ReportFormat,
    ReportKind,
    ReportStatus,
    VersionBump,
)
from app.models.prompt import Prompt, PromptVersion
from app.models.testing import PromptExecution
from app.optimization import engine as optimizer
from app.optimization.tokens import estimate_cost_usd
from app.repositories.analytics import (
    PromptAuditRepository,
    PromptOptimizationRepository,
    PromptReportRepository,
    PromptStatisticRepository,
)
from app.repositories.governance import PromptSecurityScanRepository
from app.repositories.prompt import PromptRepository, PromptVersionRepository
from app.repositories.testing import PromptExecutionRepository
from app.services.prompt import PromptService
from app.types import EventPublisher

logger = get_logger("app.services.analytics")

_SOURCE_SERVICE = "prompt-management-service"
_TOP_PROMPT_LIMIT = 10


class OptimizationService:
    """Suggests improvements and turns accepted ones into drafts."""

    def __init__(
        self,
        optimizations: PromptOptimizationRepository,
        prompts: PromptService,
        *,
        publish_event: EventPublisher,
        usd_per_1k_tokens: float = 0.002,
    ) -> None:
        self._optimizations = optimizations
        self._prompts = prompts
        self._publish_event = publish_event
        self._usd_per_1k_tokens = usd_per_1k_tokens

    async def analyse(
        self,
        version: PromptVersion,
        *,
        min_saving_ratio: float = optimizer.DEFAULT_MIN_SAVING_RATIO,
    ) -> list[PromptOptimization]:
        """Analyse *version* and persist every suggestion found.

        Nothing is applied. A prompt's wording is the artefact under
        approval here, so rewriting it without a human accepting the
        change would bypass the whole governance workflow.
        """
        report = optimizer.analyse(version.body, min_saving_ratio=min_saving_ratio)
        stored: list[PromptOptimization] = []
        for suggestion in report.suggestions:
            stored.append(
                await self._optimizations.create(
                    PromptOptimization(
                        organization_id=version.organization_id,
                        prompt_version_id=version.id,
                        kind=suggestion.kind,
                        status=OptimizationStatus.SUGGESTED,
                        rationale=suggestion.rationale,
                        suggested_body=suggestion.suggested_body,
                        original_tokens=suggestion.original_tokens,
                        optimized_tokens=suggestion.optimized_tokens,
                        token_saving=suggestion.token_saving,
                        saving_ratio=suggestion.saving_ratio,
                        estimated_cost_saving_usd=estimate_cost_usd(
                            suggestion.token_saving, usd_per_1k_tokens=self._usd_per_1k_tokens
                        ),
                        suggested_at=datetime.now(UTC),
                    )
                )
            )
        return stored

    async def accept(
        self,
        optimization: PromptOptimization,
        prompt: Prompt,
        *,
        accepted_by: str | None = None,
    ) -> PromptVersion:
        """Accept a suggestion, creating a new draft revision from it.

        Goes through :meth:`PromptService.add_version` rather than
        writing a row directly, so an accepted optimization lands in
        exactly the same review-and-approval path as any hand-written
        edit. An optimization that could publish itself would be a hole
        straight through the governance workflow.

        Raises:
            ConflictError: If the suggestion was already decided, or is
                advisory and carries no rewrite to apply.
        """
        if optimization.status != OptimizationStatus.SUGGESTED:
            raise ConflictError(f"This suggestion was already {optimization.status!s}.")
        if not optimization.suggested_body:
            raise ConflictError(
                "This is an advisory finding with no proposed rewrite; it identifies "
                "a problem for a human to fix rather than a change to apply."
            )

        version = await self._prompts.add_version(
            prompt,
            body=optimization.suggested_body,
            component=VersionBump.PATCH,
            changelog=f"Applied optimization: {optimization.rationale}",
            created_by=accepted_by,
        )
        optimization.status = OptimizationStatus.ACCEPTED
        optimization.decided_at = datetime.now(UTC)
        optimization.decided_by = accepted_by
        optimization.resulting_version_id = version.id
        await self._optimizations.update(optimization)

        await self._publish_event(
            PromptOptimizedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=prompt.organization_id,
                payload={
                    "prompt_id": str(prompt.id),
                    "optimization_id": str(optimization.id),
                    "resulting_version": version.version_number,
                    "token_saving": optimization.token_saving,
                },
            )
        )
        return version

    async def reject(
        self, optimization: PromptOptimization, *, rejected_by: str | None = None
    ) -> PromptOptimization:
        """Decline a suggestion.

        Raises:
            ConflictError: If it was already decided.
        """
        if optimization.status != OptimizationStatus.SUGGESTED:
            raise ConflictError(f"This suggestion was already {optimization.status!s}.")
        optimization.status = OptimizationStatus.REJECTED
        optimization.decided_at = datetime.now(UTC)
        optimization.decided_by = rejected_by
        return await self._optimizations.update(optimization)


class ExecutionRecordingService:
    """Records prompt executions reported by the services that ran them."""

    def __init__(
        self,
        executions: PromptExecutionRepository,
        prompts: PromptRepository,
        *,
        publish_event: EventPublisher,
    ) -> None:
        self._executions = executions
        self._prompts = prompts
        self._publish_event = publish_event

    async def record(
        self,
        prompt: Prompt,
        version: PromptVersion,
        *,
        status: ExecutionStatus = ExecutionStatus.SUCCEEDED,
        masked_prompt: str | None = None,
        model_provider: str | None = None,
        model_name: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: float | None = None,
        cost_usd: float = 0.0,
        executed_by: str | None = None,
        agent_id: str | None = None,
        workflow_id: str | None = None,
        ab_test_id: UUID | None = None,
        ab_arm: str | None = None,
        result_metadata: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> PromptExecution:
        """Record one production use of a prompt.

        ``masked_prompt`` is what gets stored, and the caller is
        expected to have masked it -- :class:`~app.services.rendering
        .RenderedResult` hands back exactly that field for this
        purpose. Storing the unmasked body would put resolved secrets
        into execution history.
        """
        now = datetime.now(UTC)
        execution = await self._executions.create(
            PromptExecution(
                organization_id=prompt.organization_id,
                prompt_id=prompt.id,
                prompt_version_id=version.id,
                ab_test_id=ab_test_id,
                ab_arm=ab_arm,
                status=status,
                model_provider=model_provider,
                model_name=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                rendered_prompt=masked_prompt,
                result_metadata=dict(result_metadata or {}),
                executed_at=now,
                executed_by=executed_by,
                agent_id=agent_id,
                workflow_id=workflow_id,
                error=error,
            )
        )
        prompt.execution_count += 1
        prompt.last_executed_at = now
        await self._prompts.update(prompt)

        await self._publish_event(
            PromptExecutedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=prompt.organization_id,
                payload={
                    "prompt_id": str(prompt.id),
                    "version_number": version.version_number,
                    "status": str(status),
                    "total_tokens": execution.total_tokens,
                },
            )
        )
        return execution


class EvaluationService:
    """Scores a prompt's own output quality."""

    def __init__(
        self,
        versions: PromptVersionRepository,
        *,
        publish_event: EventPublisher,
    ) -> None:
        self._versions = versions
        self._publish_event = publish_event

    async def evaluate_output(
        self,
        version: PromptVersion,
        actual: str,
        *,
        expected: str | None = None,
        required_points: list[str] | None = None,
        repeated_outputs: list[str] | None = None,
        grounding: list[str] | None = None,
        latency_ms: float | None = None,
        total_tokens: int | None = None,
        cost_usd: float | None = None,
    ) -> scoring.EvaluationReport:
        """Score one output and roll the result onto its revision.

        The rolled-up ``average_score`` is what makes comparing two
        revisions cheap; recomputing it from every evaluation on each
        read would make the comparison view scale with history.
        """
        report = scoring.evaluate(
            actual,
            expected=expected,
            required_points=required_points or [],
            repeated_outputs=repeated_outputs or [],
            grounding=grounding or [],
            latency_ms=latency_ms,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
        )
        version.average_score = (
            report.overall
            if version.average_score is None
            else (version.average_score + report.overall) / 2
        )
        await self._versions.update(version)

        await self._publish_event(
            PromptEvaluatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=version.organization_id,
                payload={
                    "prompt_version_id": str(version.id),
                    "overall": round(report.overall, 4),
                    "metrics": [str(s.metric) for s in report.scores],
                },
            )
        )
        return report


class StatisticsService:
    """Rolls prompt activity up into windows ("ANALYTICS")."""

    def __init__(
        self,
        statistics: PromptStatisticRepository,
        prompts: PromptRepository,
        executions: PromptExecutionRepository,
        optimizations: PromptOptimizationRepository,
        scans: PromptSecurityScanRepository,
    ) -> None:
        self._statistics = statistics
        self._prompts = prompts
        self._executions = executions
        self._optimizations = optimizations
        self._scans = scans

    async def rollup(
        self, organization_id: UUID, *, window_start: datetime, window_end: datetime
    ) -> PromptStatistic:
        """Compute and store one window's statistics."""
        all_prompts = await self._prompts.list_for_org(organization_id, limit=10_000)
        published = sum(1 for p in all_prompts if p.status == PromptLifecycleStatus.PUBLISHED)

        by_type: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for prompt in all_prompts:
            by_type[str(prompt.prompt_type)] = by_type.get(str(prompt.prompt_type), 0) + 1
            by_category[str(prompt.category)] = by_category.get(str(prompt.category), 0) + 1

        executions = await self._executions.list_in_window(
            organization_id, since=window_start, until=window_end
        )
        succeeded = sum(1 for e in executions if e.status == ExecutionStatus.SUCCEEDED)
        failed = sum(1 for e in executions if e.status == ExecutionStatus.FAILED)
        latencies = [e.latency_ms for e in executions if e.latency_ms is not None]
        costs = [e.cost_usd for e in executions if e.cost_usd]

        per_prompt: dict[str, int] = {}
        for execution in executions:
            key = str(execution.prompt_id)
            per_prompt[key] = per_prompt.get(key, 0) + 1
        top = sorted(per_prompt.items(), key=lambda item: item[1], reverse=True)[:_TOP_PROMPT_LIMIT]

        return await self._statistics.create(
            PromptStatistic(
                organization_id=organization_id,
                window_start=window_start,
                window_end=window_end,
                total_prompts=len(all_prompts),
                published_prompts=published,
                execution_count=len(executions),
                executions_succeeded=succeeded,
                executions_failed=failed,
                total_tokens=sum(e.total_tokens for e in executions),
                average_latency_ms=(sum(latencies) / len(latencies)) if latencies else None,
                average_cost_usd=(sum(costs) / len(costs)) if costs else None,
                optimization_token_savings=await self._optimizations.accepted_savings_in_window(
                    organization_id, since=window_start, until=window_end
                ),
                security_findings=await self._scans.count_findings_in_window(
                    organization_id, since=window_start, until=window_end
                ),
                by_prompt_type=by_type,
                by_category=by_category,
                top_prompts=[
                    {"prompt_id": prompt_id, "executions": count} for prompt_id, count in top
                ],
            )
        )

    async def dashboard(self, organization_id: UUID) -> dict[str, Any]:
        """The live snapshot a dashboard reads on load."""
        latest = await self._statistics.latest(organization_id)
        return {
            "latest_window": {
                "total_prompts": latest.total_prompts if latest else None,
                "published_prompts": latest.published_prompts if latest else None,
                "execution_count": latest.execution_count if latest else None,
                "executions_failed": latest.executions_failed if latest else None,
                "average_latency_ms": latest.average_latency_ms if latest else None,
                "optimization_token_savings": (
                    latest.optimization_token_savings if latest else None
                ),
                "computed_through": latest.window_end.isoformat() if latest else None,
            }
        }

    async def trend(self, organization_id: UUID, *, since_days: int = 30) -> list[PromptStatistic]:
        """Recent windows, oldest first, for a trend chart."""
        since = datetime.now(UTC) - timedelta(days=since_days)
        return await self._statistics.list_since(organization_id, since=since)


class ReportService:
    """Generates the documents docs/061's own "REPORTING" section asks for.

    Only ``USAGE``, ``OPTIMIZATION``, ``SECURITY``, and ``AUDIT`` have
    real builders; the rest return empty rows -- the same "not every
    report kind needs a bespoke builder in the first cut" scope
    decision every prior AI-IOS ``ReportService`` made, stated rather
    than disguised.
    """

    def __init__(
        self,
        reports: PromptReportRepository,
        prompts: PromptRepository,
        optimizations: PromptOptimizationRepository,
        scans: PromptSecurityScanRepository,
        audits: PromptAuditRepository,
        *,
        max_rows: int = 10_000,
    ) -> None:
        self._reports = reports
        self._prompts = prompts
        self._optimizations = optimizations
        self._scans = scans
        self._audits = audits
        self._max_rows = max_rows

    async def generate(
        self,
        organization_id: UUID,
        *,
        kind: ReportKind,
        report_format: ReportFormat = ReportFormat.JSON,
        title: str | None = None,
        generated_by: str | None = None,
    ) -> PromptReport:
        """Build and store one report.

        A build failure never raises to the caller -- it is recorded on
        the row as ``FAILED`` with an ``error``, so a broken report is
        visible rather than a lost request.
        """
        started = datetime.now(UTC)
        record = await self._reports.create(
            PromptReport(
                organization_id=organization_id,
                kind=kind,
                report_format=report_format,
                title=title or f"{kind!s} report",
                status=ReportStatus.RUNNING,
                generated_by=generated_by,
            )
        )
        try:
            content = await self._build(organization_id, kind)
        except Exception as exc:
            record.status = ReportStatus.FAILED
            record.error = str(exc)
            logger.warning(
                "Could not build a report.",
                extra={"extra_fields": {"kind": str(kind), "error": str(exc)}},
            )
            return await self._reports.update(record)

        record.status = ReportStatus.COMPLETED
        record.content = content
        record.row_count = len(content.get("rows", []))
        record.generated_at = datetime.now(UTC)
        record.duration_ms = (record.generated_at - started).total_seconds() * 1_000
        return await self._reports.update(record)

    async def _build(self, organization_id: UUID, kind: ReportKind) -> dict[str, Any]:
        builder = self._BUILDERS.get(kind)
        return await builder(self, organization_id) if builder else {"rows": []}

    async def _build_usage(self, organization_id: UUID) -> dict[str, Any]:
        prompts = await self._prompts.list_for_org(organization_id, limit=self._max_rows)
        return {
            "rows": [
                {
                    "slug": p.slug,
                    "prompt_type": str(p.prompt_type),
                    "category": str(p.category),
                    "status": str(p.status),
                    "current_version": p.current_version_number,
                    "execution_count": p.execution_count,
                    "last_executed_at": (
                        p.last_executed_at.isoformat() if p.last_executed_at else None
                    ),
                }
                for p in prompts
            ]
        }

    async def _build_optimization(self, organization_id: UUID) -> dict[str, Any]:
        rows = await self._optimizations.list_open(organization_id, limit=self._max_rows)
        return {
            "rows": [
                {
                    "kind": str(row.kind),
                    "status": str(row.status),
                    "token_saving": row.token_saving,
                    "saving_ratio": round(row.saving_ratio, 4),
                    "estimated_cost_saving_usd": row.estimated_cost_saving_usd,
                    "rationale": row.rationale,
                }
                for row in rows
            ]
        }

    async def _build_security(self, organization_id: UUID) -> dict[str, Any]:
        rows = await self._scans.list_blocking(organization_id, limit=self._max_rows)
        return {
            "rows": [
                {
                    "prompt_version_id": str(row.prompt_version_id),
                    "status": str(row.status),
                    "highest_severity": str(row.highest_severity),
                    "finding_count": row.finding_count,
                    "scanned_at": row.scanned_at.isoformat(),
                }
                for row in rows
            ]
        }

    async def _build_audit(self, organization_id: UUID) -> dict[str, Any]:
        rows = await self._audits.list_for_org(organization_id, limit=self._max_rows)
        return {
            "rows": [
                {
                    "action": str(row.action),
                    "entity_type": row.entity_type,
                    "entity_reference": row.entity_reference,
                    "actor_id": row.actor_id,
                    "occurred_at": row.occurred_at.isoformat(),
                    "succeeded": row.succeeded,
                }
                for row in rows
            ]
        }

    _BUILDERS: ClassVar[dict[ReportKind, Any]] = {
        ReportKind.USAGE: _build_usage,
        ReportKind.OPTIMIZATION: _build_optimization,
        ReportKind.SECURITY: _build_security,
        ReportKind.AUDIT: _build_audit,
    }

    async def list_for_org(
        self, organization_id: UUID, *, kind: ReportKind | None = None
    ) -> list[PromptReport]:
        """Reports, newest first."""
        return await self._reports.list_for_org(organization_id, kind=kind)


class AuditService:
    """Writes and reads the append-only prompt audit trail."""

    def __init__(self, audits: PromptAuditRepository) -> None:
        self._audits = audits

    async def record(
        self,
        organization_id: UUID,
        *,
        action: AuditAction,
        entity_type: str,
        summary: str,
        entity_id: UUID | None = None,
        entity_reference: str | None = None,
        actor_id: str | None = None,
        actor_type: str = "user",
        succeeded: bool = True,
        changes: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
    ) -> PromptAudit:
        """Append one entry."""
        return await self._audits.create(
            PromptAudit(
                organization_id=organization_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_reference=entity_reference,
                actor_id=actor_id,
                actor_type=actor_type,
                occurred_at=datetime.now(UTC),
                summary=summary,
                succeeded=succeeded,
                changes=dict(changes or {}),
                context=dict(context or {}),
                request_id=request_id,
                ip_address=ip_address,
            )
        )

    async def list_entries(self, organization_id: UUID, *, limit: int = 200) -> list[PromptAudit]:
        """Audit entries, newest first."""
        return await self._audits.list_for_org(organization_id, limit=limit)

    async def summary(self, organization_id: UUID, *, days: int = 30) -> dict[str, Any]:
        """How much of each action has happened lately."""
        since = datetime.now(UTC) - timedelta(days=days)
        counts = await self._audits.count_by_action(organization_id, since=since)
        return {"since": since.isoformat(), "total": sum(counts.values()), "by_action": counts}


__all__ = [
    "AuditService",
    "EvaluationService",
    "ExecutionRecordingService",
    "OptimizationService",
    "ReportService",
    "StatisticsService",
]
