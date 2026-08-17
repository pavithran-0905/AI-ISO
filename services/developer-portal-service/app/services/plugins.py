"""Plugin submission publishing workflow.

Publishes ``PluginSubmitted`` on every new submission and
``PluginPublished`` on approval; notifies Plugin Approved and Plugin
Rejected directly on the reviewer's own decision.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import PluginPublishedEvent, PluginSubmittedEvent
from app.models.enums import PluginReviewDecision, PluginSubmissionStatus, PortalAuditAction
from app.models.plugins import PluginReview, PluginSubmission
from app.plugins.engine import TransitionResult, validate_transition
from app.repositories.plugins import PluginReviewRepository, PluginSubmissionRepository
from app.services.audit import AuditService
from app.services.notifications import PortalNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "developer-portal-service"

_DECISION_TARGET: dict[PluginReviewDecision, PluginSubmissionStatus] = {
    PluginReviewDecision.APPROVED: PluginSubmissionStatus.APPROVED,
    PluginReviewDecision.REJECTED: PluginSubmissionStatus.REJECTED,
}


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class PluginSubmissionService:
    def __init__(
        self,
        repo: PluginSubmissionRepository,
        review_repo: PluginReviewRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
        notifier: PortalNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._review_repo = review_repo
        self._publish = publish
        self._audit = audit
        self._notifier = notifier

    async def submit(
        self,
        organization_id: UUID,
        *,
        user_id: str,
        plugin_name: str,
        version: str,
        checksum_sha256: str,
        now: datetime,
    ) -> PluginSubmission:
        submission = await self._repo.create(
            PluginSubmission(
                organization_id=organization_id,
                user_id=user_id,
                plugin_name=plugin_name,
                version_label=version,
                checksum_sha256=checksum_sha256,
                submitted_at=now,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id=organization_id,
                action=PortalAuditAction.PLUGIN_PUBLICATION,
                entity_type="plugin_submission",
                entity_id=submission.id,
                occurred_at=now,
                actor_id=user_id,
                summary=f"Plugin {plugin_name!r} version {version!r} submitted.",
            )
        await self._publish(
            PluginSubmittedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"plugin_submission_id": str(submission.id), "plugin_name": plugin_name},
            )
        )
        return submission

    async def begin_validation(self, submission: PluginSubmission) -> PluginSubmission:
        result = validate_transition(submission.status, PluginSubmissionStatus.VALIDATING)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        submission.status = PluginSubmissionStatus.VALIDATING
        return await self._repo.update(submission)

    async def submit_for_approval(
        self, submission: PluginSubmission, *, now: datetime
    ) -> PluginSubmission:
        result = validate_transition(submission.status, PluginSubmissionStatus.PENDING_APPROVAL)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        submission.status = PluginSubmissionStatus.PENDING_APPROVAL
        submission.validated_at = now
        return await self._repo.update(submission)

    async def review(
        self,
        submission: PluginSubmission,
        *,
        reviewer_id: str,
        decision: PluginReviewDecision,
        comments: str = "",
        now: datetime,
    ) -> PluginReview:
        """Record a reviewer's decision, transitioning the submission's
        own status for ``APPROVED``/``REJECTED`` decisions."""
        review = await self._review_repo.create(
            PluginReview(
                organization_id=submission.organization_id,
                plugin_submission_id=submission.id,
                reviewer_id=reviewer_id,
                decision=decision,
                comments=comments,
                reviewed_at=now,
            )
        )

        target = _DECISION_TARGET.get(decision)
        if target is None:
            return review  # CHANGES_REQUESTED: feedback only, no status transition

        result = validate_transition(submission.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        submission.status = target
        await self._repo.update(submission)

        if self._audit is not None:
            await self._audit.record(
                organization_id=submission.organization_id,
                action=PortalAuditAction.PLUGIN_PUBLICATION,
                entity_type="plugin_submission",
                entity_id=submission.id,
                occurred_at=now,
                actor_id=reviewer_id,
                summary=f"Plugin {submission.plugin_name!r} {decision.value} by {reviewer_id!r}.",
            )

        if target == PluginSubmissionStatus.APPROVED:
            await self._publish(
                PluginPublishedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=submission.organization_id,
                    payload={
                        "plugin_submission_id": str(submission.id),
                        "plugin_name": submission.plugin_name,
                    },
                )
            )
            if self._notifier is not None:
                await self._notifier.notify_plugin_approved(plugin_name=submission.plugin_name)
        elif target == PluginSubmissionStatus.REJECTED and self._notifier is not None:
            await self._notifier.notify_plugin_rejected(
                plugin_name=submission.plugin_name, reason=comments or "no reason given"
            )
        return review


__all__ = ["PluginSubmissionService", "TransitionRefusedError"]
