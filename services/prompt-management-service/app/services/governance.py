"""Review, approval, and security-gate governance (docs/061
"GOVERNANCE", "SECURITY": Approval Gates).

The publish gate lives here rather than in
:class:`~app.services.prompt.PromptService`: whether a revision *may*
be published is a governance question, while actually publishing it is
a lifecycle mechanic. Keeping them apart means the lifecycle service
cannot accidentally bypass a gate, because it has no idea one exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.exceptions.conflict import ConflictError

from app.events.prompt_events import (
    PromptApprovalRequestedEvent,
    PromptSecurityViolationEvent,
)
from app.models.analytics import PromptAudit
from app.models.enums import (
    ApprovalStatus,
    AuditAction,
    ReviewDecision,
    ScanStatus,
    SecuritySeverity,
)
from app.models.governance import PromptApproval, PromptReview, PromptSecurityScan
from app.models.prompt import PromptVersion
from app.repositories.analytics import PromptAuditRepository
from app.repositories.governance import (
    PromptApprovalRepository,
    PromptReviewRepository,
    PromptSecurityScanRepository,
)
from app.repositories.template import PromptVariableRepository
from app.security import scanner
from app.types import EventPublisher

_SOURCE_SERVICE = "prompt-management-service"


@dataclass(frozen=True, slots=True)
class GateResult:
    """Whether a revision may be published, and why not if it may not."""

    allowed: bool
    blockers: tuple[str, ...] = ()

    @property
    def reason(self) -> str:
        """A single human-readable explanation."""
        if self.allowed:
            return "All publication gates are satisfied."
        return " ".join(self.blockers)


@dataclass(slots=True)
class ReviewSummary:
    """How one revision's review round currently stands."""

    approved: int = 0
    changes_requested: int = 0
    rejected: int = 0
    pending: int = 0
    mandatory_outstanding: bool = False
    by_decision: dict[str, int] = field(default_factory=dict)


class ReviewService:
    """Records reviewer verdicts on a revision."""

    def __init__(self, reviews: PromptReviewRepository) -> None:
        self._reviews = reviews

    async def request(
        self,
        version: PromptVersion,
        *,
        reviewer_id: str,
        is_mandatory: bool = False,
    ) -> PromptReview:
        """Ask *reviewer_id* to review *version*.

        Raises:
            ConflictError: If that reviewer already has a review open on
                this revision. Two open requests for one person would
                make ``count_by_decision`` double-count their eventual
                verdict.
        """
        existing = await self._reviews.list_for_version(version.id)
        if any(
            row.reviewer_id == reviewer_id and row.decision == ReviewDecision.PENDING
            for row in existing
        ):
            raise ConflictError(
                f"Reviewer {reviewer_id!r} already has an open review on version "
                f"{version.version_number}."
            )
        return await self._reviews.create(
            PromptReview(
                organization_id=version.organization_id,
                prompt_version_id=version.id,
                reviewer_id=reviewer_id,
                decision=ReviewDecision.PENDING,
                is_mandatory=is_mandatory,
            )
        )

    async def submit(
        self,
        review: PromptReview,
        *,
        decision: ReviewDecision,
        comments: str | None = None,
        requested_changes: list[str] | None = None,
    ) -> PromptReview:
        """Record a reviewer's verdict.

        Raises:
            ConflictError: If the review was already decided, or the
                caller tries to record ``PENDING`` as a verdict --
                pending is the absence of one.
        """
        if review.decision != ReviewDecision.PENDING:
            raise ConflictError(f"This review was already decided as {review.decision!s}.")
        if decision == ReviewDecision.PENDING:
            raise ConflictError("PENDING is not a verdict; it is the absence of one.")

        review.decision = decision
        review.comments = comments
        review.requested_changes = list(requested_changes or [])
        review.submitted_at = datetime.now(UTC)
        return await self._reviews.update(review)

    async def summarise(self, prompt_version_id: UUID) -> ReviewSummary:
        """How one revision's review round currently stands."""
        counts = await self._reviews.count_by_decision(prompt_version_id)
        return ReviewSummary(
            approved=counts.get(str(ReviewDecision.APPROVED), 0),
            changes_requested=counts.get(str(ReviewDecision.CHANGES_REQUESTED), 0),
            rejected=counts.get(str(ReviewDecision.REJECTED), 0),
            pending=counts.get(str(ReviewDecision.PENDING), 0),
            mandatory_outstanding=await self._reviews.has_unresolved_mandatory(prompt_version_id),
            by_decision=counts,
        )


class ApprovalService:
    """Runs the approval gate on a revision ("Approval Workflow")."""

    def __init__(
        self,
        approvals: PromptApprovalRepository,
        audit: PromptAuditRepository,
        *,
        publish_event: EventPublisher,
    ) -> None:
        self._approvals = approvals
        self._audit = audit
        self._publish_event = publish_event

    async def request(
        self,
        version: PromptVersion,
        *,
        required_approvals: int = 1,
        expiry_seconds: float = 604_800.0,
        requested_by: str | None = None,
    ) -> PromptApproval:
        """Open an approval gate on *version*.

        Raises:
            ValueError: If *required_approvals* is not positive.
        """
        if required_approvals < 1:
            raise ValueError(f"required_approvals must be at least 1, got {required_approvals!r}.")
        now = datetime.now(UTC)
        approval = await self._approvals.create(
            PromptApproval(
                organization_id=version.organization_id,
                prompt_version_id=version.id,
                status=ApprovalStatus.PENDING,
                required_approvals=required_approvals,
                requested_by=requested_by,
                requested_at=now,
                expires_at=now + timedelta(seconds=expiry_seconds),
            )
        )
        await self._publish_event(
            PromptApprovalRequestedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=version.organization_id,
                payload={
                    "prompt_version_id": str(version.id),
                    "version_number": version.version_number,
                    "required_approvals": required_approvals,
                },
            )
        )
        return approval

    async def decide(
        self,
        approval: PromptApproval,
        *,
        approver_id: str,
        approve: bool,
        reason: str | None = None,
    ) -> PromptApproval:
        """Record one approver's decision.

        Raises:
            ConflictError: If the gate is no longer pending. An expired
                or withdrawn request must be reopened rather than
                answered late -- silently accepting a decision on a
                lapsed gate would make the expiry meaningless.
        """
        if approval.status != ApprovalStatus.PENDING:
            raise ConflictError(
                f"This approval is {approval.status!s}, not pending; it cannot be decided."
            )

        approval.approver_id = approver_id
        approval.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
        approval.reason = reason
        approval.decided_at = datetime.now(UTC)
        approval = await self._approvals.update(approval)

        await self._audit.create(
            PromptAudit(
                organization_id=approval.organization_id,
                action=AuditAction.APPROVAL_DECIDED,
                entity_type="prompt_version",
                entity_id=approval.prompt_version_id,
                actor_id=approver_id,
                occurred_at=datetime.now(UTC),
                summary=(f"Approval {'granted' if approve else 'rejected'} by {approver_id}."),
                succeeded=approve,
            )
        )
        return approval

    async def expire_lapsed(self, moment: datetime, *, limit: int = 200) -> int:
        """Mark every pending approval past its deadline as expired.

        Returns how many lapsed. Backs the approval-expiry sweep: a
        request that sits unanswered forever silently blocks a publish
        with no signal anything is wrong.
        """
        lapsed = await self._approvals.list_pending_expired(moment, limit=limit)
        for approval in lapsed:
            approval.status = ApprovalStatus.EXPIRED
            approval.decided_at = moment
            await self._approvals.update(approval)
        return len(lapsed)

    async def is_satisfied(self, version: PromptVersion, *, required: int) -> bool:
        """Whether enough distinct approvers have approved *version*."""
        return await self._approvals.count_approved(version.id) >= required


class SecurityService:
    """Scans revisions and records the findings ("SECURITY")."""

    def __init__(
        self,
        scans: PromptSecurityScanRepository,
        variables: PromptVariableRepository,
        *,
        publish_event: EventPublisher,
    ) -> None:
        self._scans = scans
        self._variables = variables
        self._publish_event = publish_event

    async def scan_version(
        self,
        version: PromptVersion,
        *,
        restricted_keywords: list[str] | None = None,
        scanned_by: str | None = None,
        block_on_critical: bool = True,
    ) -> PromptSecurityScan:
        """Scan *version*'s body and persist the result.

        Declared variables are read from the database rather than
        passed in, so the undeclared-variable check reflects what the
        revision actually declares -- a caller supplying its own list
        could accidentally suppress the finding.
        """
        declared = [row.name for row in await self._variables.list_for_version(version.id)]
        report = scanner.scan(
            version.body,
            declared_variable_names=declared,
            restricted_keywords=restricted_keywords or [],
        )
        blocked = block_on_critical and report.status == ScanStatus.BLOCKED

        scan = await self._scans.create(
            PromptSecurityScan(
                organization_id=version.organization_id,
                prompt_version_id=version.id,
                status=report.status,
                highest_severity=report.highest_severity,
                findings=report.to_dicts(),
                finding_count=len(report.findings),
                scanned_at=datetime.now(UTC),
                scanned_by=scanned_by,
                blocked_publish=blocked,
            )
        )
        if report.findings:
            await self._publish_event(
                PromptSecurityViolationEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=version.organization_id,
                    payload={
                        "prompt_version_id": str(version.id),
                        "status": str(report.status),
                        "highest_severity": str(report.highest_severity),
                        "finding_count": len(report.findings),
                        "findings": [str(f.finding) for f in report.findings],
                    },
                )
            )
        return scan


class PublicationGate:
    """Decides whether a revision may be published.

    Every blocker is collected rather than short-circuiting on the
    first: someone preparing a publish wants the full list of what to
    fix, not one round trip per problem.
    """

    def __init__(
        self,
        reviews: PromptReviewRepository,
        approvals: PromptApprovalRepository,
        scans: PromptSecurityScanRepository,
    ) -> None:
        self._reviews = reviews
        self._approvals = approvals
        self._scans = scans

    async def evaluate(
        self,
        version: PromptVersion,
        *,
        required_approvals: int = 1,
        require_scan: bool = True,
        block_on_critical: bool = True,
    ) -> GateResult:
        """Check every publication gate against *version*."""
        blockers: list[str] = []

        if await self._reviews.has_unresolved_mandatory(version.id):
            # Not "still outstanding": a mandatory reviewer who rejected
            # or asked for changes has answered, and saying so blocks a
            # publish just as an unanswered request does.
            blockers.append("A mandatory reviewer has not approved this revision.")

        approved = await self._approvals.count_approved(version.id)
        if approved < required_approvals:
            blockers.append(
                f"{approved} of {required_approvals} required approvals have been granted."
            )

        latest = await self._scans.latest_for_version(version.id)
        if latest is None:
            if require_scan:
                blockers.append("No security scan has been run against this revision.")
        elif block_on_critical and latest.highest_severity == SecuritySeverity.CRITICAL:
            blockers.append(
                f"The latest security scan found {latest.finding_count} finding(s) "
                "including a critical one."
            )

        return GateResult(allowed=not blockers, blockers=tuple(blockers))


__all__ = [
    "ApprovalService",
    "GateResult",
    "PublicationGate",
    "ReviewService",
    "ReviewSummary",
    "SecurityService",
]
