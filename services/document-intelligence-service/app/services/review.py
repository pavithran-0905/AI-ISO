"""Human review (docs/063 "HUMAN REVIEW").

Opening a review, assigning it, applying a reviewer's corrections, and
closing it with a decision.

**A correction is stored beside the extraction, never over it.** The
original value is what the extractor produced and the corrected value is
what a human says it should be; keeping both is the only way to measure
how often the extractor is wrong, which is the whole point of having
reviewers. Overwriting the original destroys that signal permanently.

**A review does not reopen.** A completed review is a decision a person
made at a time, and mutating it would rewrite the audit trail. Further
work on the same document opens a *new* review, which is why
:meth:`ReviewService.open` is callable more than once per document.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.exceptions.validation import ValidationError
from shared_core.logging.logger import get_logger

from app.events.document_events import ReviewCompletedEvent
from app.models.enums import DocumentStatus, ReviewDecision, ReviewStatus
from app.models.operations import DocumentAudit, DocumentReview
from app.services.bundle import Repositories
from app.types import EventPublisher

_LOGGER = get_logger(__name__)
_SOURCE_SERVICE = "document-intelligence-service"

DEFAULT_REVIEW_HOURS = 24
"""How long a reviewer has by default. A deadline is set on every review
rather than left null: an undated review never appears in the overdue
sweep, so nothing ever escalates it and it sits in the queue forever."""

_OPEN_STATUSES = frozenset({ReviewStatus.PENDING, ReviewStatus.ASSIGNED, ReviewStatus.IN_PROGRESS})

_DECISION_STATUS: Mapping[ReviewDecision, DocumentStatus] = {
    ReviewDecision.APPROVED: DocumentStatus.APPROVED,
    ReviewDecision.REJECTED: DocumentStatus.REJECTED,
    ReviewDecision.CORRECTED: DocumentStatus.APPROVED,
    ReviewDecision.REPROCESS: DocumentStatus.UPLOADED,
}
"""What each decision does to the document.

``CORRECTED`` approves it: a reviewer who fixed the fields has said the
document is now right, and leaving it in review would mean their work
changed nothing. ``REPROCESS`` sends it back to the start of the
pipeline, which is what a reviewer asks for when the extraction was
wrong in a way no field edit can fix."""


@dataclass(slots=True)
class ReviewOutcome:
    """A closed review and what it changed."""

    review: DocumentReview
    corrections_applied: int = 0
    fields_corrected: list[str] = field(default_factory=list)
    document_status: DocumentStatus = DocumentStatus.APPROVED
    requeued: bool = False


class ReviewService:
    """Opens, assigns and closes human reviews."""

    def __init__(
        self,
        *,
        repositories: Repositories,
        publish: EventPublisher,
        default_hours: int = DEFAULT_REVIEW_HOURS,
    ) -> None:
        self._repos = repositories
        self._publish = publish
        self._default_hours = default_hours

    async def open(
        self,
        *,
        organization_id: UUID,
        document_id: UUID,
        reason: str,
        priority: int = 100,
        triggered_by_confidence: float | None = None,
        due_hours: int | None = None,
        assigned_to: str | None = None,
    ) -> DocumentReview:
        """Open a review of a document's current version.

        Raises:
            ValidationError: With no reason given. A review whose reason is
                blank tells the reviewer nothing about what to look at,
                and the queue fills with tasks nobody can action.
            NotFoundError: If the document is not in that organization, or
                has no current version to review.
        """
        if not reason.strip():
            raise ValidationError(
                "A review needs a reason; a reviewer cannot act on a task that "
                "does not say what is wrong."
            )
        document = await self._repos.documents.require_in_org(organization_id, document_id)
        version = await self._repos.versions.require_current(document_id)

        now = datetime.now(UTC)
        review = await self._repos.reviews.create(
            DocumentReview(
                organization_id=organization_id,
                document_id=document.id,
                document_version_id=version.id,
                status=ReviewStatus.ASSIGNED if assigned_to else ReviewStatus.PENDING,
                reason=reason.strip()[:512],
                priority=priority,
                triggered_by_confidence=triggered_by_confidence,
                assigned_to=assigned_to,
                assigned_at=now if assigned_to else None,
                due_at=now + timedelta(hours=due_hours or self._default_hours),
            )
        )
        await self._repos.documents.mark_status(document.id, DocumentStatus.REVIEW_PENDING)
        await self._audit(
            organization_id,
            "review_opened",
            review.id,
            actor=assigned_to,
            summary=reason.strip()[:512],
        )
        return review

    async def assign(
        self, *, organization_id: UUID, review_id: UUID, reviewer_id: str
    ) -> DocumentReview:
        """Assign an open review to a reviewer.

        Raises:
            ValidationError: If the review is already closed.
            NotFoundError: If the review is not in that organization.
        """
        review = await self._repos.reviews.require_in_org(organization_id, review_id)
        self._require_open(review)
        review.assigned_to = reviewer_id
        review.assigned_at = datetime.now(UTC)
        review.status = ReviewStatus.ASSIGNED
        await self._audit(organization_id, "review_assigned", review.id, actor=reviewer_id)
        return review

    async def start(
        self, *, organization_id: UUID, review_id: UUID, reviewer_id: str
    ) -> DocumentReview:
        """Mark a review in progress.

        Raises:
            ValidationError: If the review is already closed.
            NotFoundError: If the review is not in that organization.
        """
        review = await self._repos.reviews.require_in_org(organization_id, review_id)
        self._require_open(review)
        review.status = ReviewStatus.IN_PROGRESS
        review.reviewer_id = reviewer_id
        review.started_at = review.started_at or datetime.now(UTC)
        await self._repos.documents.mark_status(review.document_id, DocumentStatus.IN_REVIEW)
        return review

    async def complete(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        reviewer_id: str,
        decision: ReviewDecision,
        corrections: Mapping[str, str] | None = None,
        comment: str | None = None,
        annotations: Sequence[Mapping[str, object]] = (),
    ) -> ReviewOutcome:
        """Close a review with a decision, applying any corrections.

        Raises:
            ValidationError: If the review is already closed, or if a
                ``CORRECTED`` decision carries no corrections -- which
                would record that a reviewer fixed the document while
                changing nothing, and inflate the correction rate with
                edits that never happened.
            NotFoundError: If the review is not in that organization.
        """
        review = await self._repos.reviews.require_in_org(organization_id, review_id)
        self._require_open(review)
        chosen = ReviewDecision(str(decision))
        if chosen is ReviewDecision.CORRECTED and not corrections:
            raise ValidationError(
                "A CORRECTED decision needs at least one correction; use APPROVED "
                "to accept the extraction as it stands."
            )

        applied = await self._apply_corrections(review, corrections or {}, reviewer_id)
        now = datetime.now(UTC)
        review.status = ReviewStatus.COMPLETED
        review.decision = chosen
        review.reviewer_id = reviewer_id
        review.completed_at = now
        review.comment = comment
        review.annotations = [dict(item) for item in annotations]
        review.corrections_applied = len(applied)
        review.fields_corrected = applied
        if review.started_at is not None:
            review.duration_ms = (now - review.started_at).total_seconds() * 1000

        status = _DECISION_STATUS[chosen]
        document = await self._repos.documents.require_in_org(organization_id, review.document_id)
        document.requires_review = chosen is ReviewDecision.REPROCESS
        document.review_reason = (
            "reviewer requested reprocessing" if chosen is ReviewDecision.REPROCESS else None
        )
        await self._repos.documents.mark_status(review.document_id, status)

        await self._audit(
            organization_id,
            "review_completed",
            review.id,
            actor=reviewer_id,
            summary=f"{chosen!s} with {len(applied)} correction(s)",
            details={"decision": str(chosen), "fields": applied},
        )
        await self._publish(
            ReviewCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "document_id": str(review.document_id),
                    "review_id": str(review.id),
                    "decision": str(chosen),
                    "corrections_applied": len(applied),
                    "fields_corrected": applied,
                    "duration_ms": review.duration_ms,
                    "document_status": str(status),
                },
            )
        )
        return ReviewOutcome(
            review=review,
            corrections_applied=len(applied),
            fields_corrected=applied,
            document_status=status,
            requeued=chosen is ReviewDecision.REPROCESS,
        )

    async def _apply_corrections(
        self, review: DocumentReview, corrections: Mapping[str, str], reviewer_id: str
    ) -> list[str]:
        """Write each correction beside its original value.

        A key naming no extracted field is skipped rather than created: a
        correction to a field the extractor never found is a *new* field,
        and inventing one here would make it indistinguishable from
        something the extractor read off the page.
        """
        applied: list[str] = []
        for key, value in corrections.items():
            field_row = await self._repos.key_values.find_by_key(
                review.document_version_id, key.strip().lower()
            )
            if field_row is None:
                _LOGGER.warning(
                    "review.correction_skipped",
                    extra={"review_id": str(review.id), "key": key},
                )
                continue
            field_row.corrected_value = value
            field_row.corrected_by = reviewer_id
            field_row.is_confirmed = True
            applied.append(field_row.key)
        return applied

    async def escalate(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        escalated_to: str,
        escalation_reason: str,
    ) -> DocumentReview:
        """Escalate an open review to somebody else.

        Raises:
            ValidationError: If the review is already closed.
            NotFoundError: If the review is not in that organization.
        """
        review = await self._repos.reviews.require_in_org(organization_id, review_id)
        self._require_open(review)
        review.status = ReviewStatus.ESCALATED
        review.escalated_to = escalated_to
        review.escalation_reason = escalation_reason[:512]
        review.assigned_to = escalated_to
        review.assigned_at = datetime.now(UTC)
        await self._audit(
            organization_id,
            "review_escalated",
            review.id,
            actor=escalated_to,
            summary=escalation_reason[:512],
        )
        return review

    async def expire_overdue(self, *, now: datetime | None = None, limit: int = 100) -> int:
        """Escalate every review past its deadline, returning how many.

        Escalated rather than expired: a review nobody did is still a
        document nobody checked, and marking it EXPIRED would drop it out
        of every open-work query while leaving the document unreviewed.
        """
        moment = now or datetime.now(UTC)
        overdue = await self._repos.reviews.list_overdue(moment, limit=limit)
        for review in overdue:
            review.status = ReviewStatus.ESCALATED
            review.escalation_reason = (
                f"not completed by {review.due_at.isoformat() if review.due_at else 'the deadline'}"
            )
            await self._audit(
                review.organization_id,
                "review_escalated",
                review.id,
                actor=None,
                summary="escalated automatically after passing its deadline",
            )
        return len(overdue)

    def _require_open(self, review: DocumentReview) -> None:
        """Refuse to change a closed review.

        Raises:
            ValidationError: When the review is not open. A completed
                review is a decision a person made at a time, and
                mutating it rewrites the audit trail.
        """
        if ReviewStatus(str(review.status)) not in _OPEN_STATUSES:
            raise ValidationError(
                f"Review {review.id!s} is {review.status!s} and cannot be changed; "
                "open a new review of the document instead."
            )

    async def _audit(
        self,
        organization_id: UUID,
        action: str,
        review_id: UUID,
        *,
        actor: str | None,
        summary: str | None = None,
        details: Mapping[str, object] | None = None,
    ) -> None:
        """Record one review action in the audit trail."""
        await self._repos.audits.create(
            DocumentAudit(
                organization_id=organization_id,
                action=action,
                entity_type="review",
                entity_id=review_id,
                occurred_at=datetime.now(UTC),
                actor_id=actor,
                summary=summary,
                details=dict(details or {}),
            )
        )


__all__ = ["DEFAULT_REVIEW_HOURS", "ReviewOutcome", "ReviewService"]
