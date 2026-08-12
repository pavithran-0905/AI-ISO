"""Repositories for reviews, validation results, jobs, statistics,
reports and the audit trail.

The queue methods here (:meth:`DocumentProcessingJobRepository.claim_due`
and :meth:`DocumentReviewRepository.list_queue`) are the ones two workers
can race on, and each says in its own docstring how it avoids handing the
same row to both.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    JobStatus,
    ReportKind,
    ReportStatus,
    ReviewStatus,
    ValidationOutcome,
)
from app.models.operations import (
    DocumentAudit,
    DocumentProcessingJob,
    DocumentReport,
    DocumentReview,
    DocumentStatistic,
    DocumentValidationResult,
)
from app.repositories.document import MAX_PAGE_SIZE


class DocumentReviewRepository(BaseRepository[DocumentReview]):
    """Human review tasks."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentReview, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, review_id: UUID) -> DocumentReview:
        """Return *review_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such review exists in that organization.
        """
        stmt = self._base_select().where(
            DocumentReview.id == review_id,
            DocumentReview.organization_id == organization_id,
        )
        found: DocumentReview | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(
                f"Review {review_id!s} was not found in organization {organization_id!s}."
            )
        return found

    async def list_queue(
        self,
        organization_id: UUID,
        *,
        assigned_to: str | None = None,
        statuses: Sequence[ReviewStatus] = (ReviewStatus.PENDING, ReviewStatus.ASSIGNED),
        limit: int = 50,
    ) -> Sequence[DocumentReview]:
        """The review queue, most urgent first.

        Ordered by priority, then by due date with unset dates last, then
        by age. A review with no deadline is not more urgent than one due
        today, and the default ``NULLS FIRST`` on an ascending sort would
        put it there.
        """
        stmt = self._base_select().where(
            DocumentReview.organization_id == organization_id,
            DocumentReview.status.in_([str(status) for status in statuses]),
        )
        if assigned_to is not None:
            stmt = stmt.where(DocumentReview.assigned_to == assigned_to)
        stmt = stmt.order_by(
            DocumentReview.priority,
            DocumentReview.due_at.asc().nulls_last(),
            DocumentReview.created_at,
        ).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_document(self, document_id: UUID) -> Sequence[DocumentReview]:
        """Every review of one document, newest first."""
        stmt = (
            self._base_select()
            .where(DocumentReview.document_id == document_id)
            .order_by(DocumentReview.created_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_overdue(self, now: datetime, *, limit: int = 100) -> Sequence[DocumentReview]:
        """Reviews past their deadline and still open.

        Global rather than per-organization: the escalation worker sweeps
        every tenant and has no organization of its own to scope to.
        """
        stmt = (
            select(DocumentReview)
            .where(
                DocumentReview.due_at.is_not(None),
                DocumentReview.due_at < now,
                DocumentReview.status.in_(
                    [
                        str(ReviewStatus.PENDING),
                        str(ReviewStatus.ASSIGNED),
                        str(ReviewStatus.IN_PROGRESS),
                    ]
                ),
                DocumentReview.deleted_at.is_(None),
            )
            .order_by(DocumentReview.due_at)
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def count_by_status(self, organization_id: UUID) -> dict[str, int]:
        """How many reviews sit in each status."""
        stmt = (
            select(DocumentReview.status, func.count())
            .where(
                DocumentReview.organization_id == organization_id,
                DocumentReview.deleted_at.is_(None),
            )
            .group_by(DocumentReview.status)
        )
        rows = (await self._session.execute(stmt)).all()
        return {str(status): int(count) for status, count in rows}


class DocumentValidationResultRepository(BaseRepository[DocumentValidationResult]):
    """Outcomes of validation rules."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentValidationResult, tenant_scope=tenant_scope)

    async def list_for_version(
        self, version_id: UUID, *, outcomes: Sequence[ValidationOutcome] = ()
    ) -> Sequence[DocumentValidationResult]:
        """Findings for one version, blocking ones first."""
        stmt = self._base_select().where(DocumentValidationResult.document_version_id == version_id)
        if outcomes:
            stmt = stmt.where(
                DocumentValidationResult.outcome.in_([str(item) for item in outcomes])
            )
        stmt = stmt.order_by(
            DocumentValidationResult.is_blocking.desc(),
            DocumentValidationResult.rule_name,
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def has_blocking(self, version_id: UUID) -> bool:
        """Whether anything blocking failed on this version."""
        stmt = select(func.count()).where(
            DocumentValidationResult.document_version_id == version_id,
            DocumentValidationResult.outcome == ValidationOutcome.FAILED,
            DocumentValidationResult.is_blocking.is_(True),
            DocumentValidationResult.deleted_at.is_(None),
        )
        return bool((await self._session.execute(stmt)).scalar_one())

    async def delete_for_version(self, version_id: UUID) -> int:
        """Clear a version's findings before re-validating it.

        Re-validation must replace rather than append: without this, a
        rule that failed and was then fixed leaves its old FAILED row
        beside the new PASSED one and the document never validates.
        """
        existing = await self.list_for_version(version_id)
        for finding in existing:
            await self.delete(finding.id)
        return len(existing)


class DocumentProcessingJobRepository(BaseRepository[DocumentProcessingJob]):
    """Pipeline runs."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentProcessingJob, tenant_scope=tenant_scope)

    async def claim_due(self, now: datetime, *, limit: int = 10) -> Sequence[DocumentProcessingJob]:
        """Queued jobs whose time has come, locked for this worker.

        ``FOR UPDATE SKIP LOCKED`` is what makes two workers safe to run
        side by side: the second skips the rows the first is holding
        rather than blocking on them or, worse, processing the same
        document twice. Rows are returned locked, so the caller must
        commit or roll back promptly.
        """
        stmt = (
            select(DocumentProcessingJob)
            .where(
                DocumentProcessingJob.status == JobStatus.QUEUED,
                DocumentProcessingJob.scheduled_at <= now,
                DocumentProcessingJob.deleted_at.is_(None),
            )
            .order_by(
                DocumentProcessingJob.priority,
                DocumentProcessingJob.scheduled_at,
            )
            .limit(min(limit, MAX_PAGE_SIZE))
            .with_for_update(skip_locked=True)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_document(
        self, document_id: UUID, *, limit: int = 20
    ) -> Sequence[DocumentProcessingJob]:
        """Runs against one document, newest first."""
        stmt = (
            self._base_select()
            .where(DocumentProcessingJob.document_id == document_id)
            .order_by(DocumentProcessingJob.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_retryable(
        self, now: datetime, *, limit: int = 50
    ) -> Sequence[DocumentProcessingJob]:
        """Failed jobs with attempts left.

        A job at its attempt ceiling is excluded: retrying it forever is
        how a permanently malformed document occupies a worker for the
        life of the deployment.
        """
        stmt = (
            select(DocumentProcessingJob)
            .where(
                DocumentProcessingJob.status == JobStatus.FAILED,
                DocumentProcessingJob.attempts < DocumentProcessingJob.max_attempts,
                DocumentProcessingJob.scheduled_at <= now,
                DocumentProcessingJob.deleted_at.is_(None),
            )
            .order_by(DocumentProcessingJob.priority, DocumentProcessingJob.scheduled_at)
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def count_by_status(self) -> dict[str, int]:
        """Queue depth per status, across every tenant."""
        stmt = (
            select(DocumentProcessingJob.status, func.count())
            .where(DocumentProcessingJob.deleted_at.is_(None))
            .group_by(DocumentProcessingJob.status)
        )
        rows = (await self._session.execute(stmt)).all()
        return {str(status): int(count) for status, count in rows}


class DocumentStatisticRepository(BaseRepository[DocumentStatistic]):
    """Rolled-up windows of processing statistics."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentStatistic, tenant_scope=tenant_scope)

    async def find_window(
        self, organization_id: UUID, window_start: datetime
    ) -> DocumentStatistic | None:
        """The window beginning at *window_start*, or ``None``.

        Used to make rollup idempotent: a worker that runs twice for the
        same window updates the row rather than adding a second one that
        double-counts every document in it.
        """
        stmt = self._base_select().where(
            DocumentStatistic.organization_id == organization_id,
            DocumentStatistic.window_start == window_start,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_recent(
        self, organization_id: UUID, *, limit: int = 30
    ) -> Sequence[DocumentStatistic]:
        """The most recent windows, newest first."""
        stmt = (
            self._base_select()
            .where(DocumentStatistic.organization_id == organization_id)
            .order_by(DocumentStatistic.window_start.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> list[UUID]:
        """Every organization that has documents.

        Global on purpose: the rollup worker needs the tenant list and
        cannot get it from a tenant-scoped query.
        """
        from app.models.document import Document  # noqa: PLC0415 -- avoids a cycle

        stmt = select(Document.organization_id).where(Document.deleted_at.is_(None)).distinct()
        return [row[0] for row in (await self._session.execute(stmt)).all()]


class DocumentReportRepository(BaseRepository[DocumentReport]):
    """Generated reports."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentReport, tenant_scope=tenant_scope)

    async def list_for_org(
        self,
        organization_id: UUID,
        *,
        kind: ReportKind | None = None,
        status: ReportStatus | None = None,
        limit: int = 50,
    ) -> Sequence[DocumentReport]:
        """Reports, newest first."""
        stmt = self._base_select().where(DocumentReport.organization_id == organization_id)
        if kind is not None:
            stmt = stmt.where(DocumentReport.kind == kind)
        if status is not None:
            stmt = stmt.where(DocumentReport.status == status)
        stmt = stmt.order_by(DocumentReport.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_pending(self, *, limit: int = 20) -> Sequence[DocumentReport]:
        """Reports queued for generation, oldest first."""
        stmt = (
            select(DocumentReport)
            .where(
                DocumentReport.status == ReportStatus.PENDING,
                DocumentReport.deleted_at.is_(None),
            )
            .order_by(DocumentReport.created_at)
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class DocumentAuditRepository(BaseRepository[DocumentAudit]):
    """The audit trail."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentAudit, tenant_scope=tenant_scope)

    async def list_for_entity(
        self, entity_id: UUID, *, limit: int = 100
    ) -> Sequence[DocumentAudit]:
        """Everything that happened to one entity, newest first."""
        stmt = (
            self._base_select()
            .where(DocumentAudit.entity_id == entity_id)
            .order_by(DocumentAudit.occurred_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_org(
        self,
        organization_id: UUID,
        *,
        action: str | None = None,
        actor_id: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> Sequence[DocumentAudit]:
        """The trail for one organization, newest first."""
        stmt = self._base_select().where(DocumentAudit.organization_id == organization_id)
        if action is not None:
            stmt = stmt.where(DocumentAudit.action == action)
        if actor_id is not None:
            stmt = stmt.where(DocumentAudit.actor_id == actor_id)
        if since is not None:
            stmt = stmt.where(DocumentAudit.occurred_at >= since)
        stmt = stmt.order_by(DocumentAudit.occurred_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "DocumentAuditRepository",
    "DocumentProcessingJobRepository",
    "DocumentReportRepository",
    "DocumentReviewRepository",
    "DocumentStatisticRepository",
    "DocumentValidationResultRepository",
]
