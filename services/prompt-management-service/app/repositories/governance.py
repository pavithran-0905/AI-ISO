"""Repositories for :class:`~app.models.governance.PromptReview`,
:class:`~app.models.governance.PromptApproval`, and
:class:`~app.models.governance.PromptSecurityScan`.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ApprovalStatus, ReviewDecision, ScanStatus
from app.models.governance import PromptApproval, PromptReview, PromptSecurityScan


class PromptReviewRepository(BaseRepository[PromptReview]):
    """CRUD plus lookup for :class:`PromptReview`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptReview, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, review_id: UUID) -> PromptReview:
        """Return *review_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such review exists in that organization.
        """
        stmt = self._base_select().where(
            PromptReview.id == review_id, PromptReview.organization_id == organization_id
        )
        result = await self._session.execute(stmt)
        found: PromptReview | None = result.scalars().first()
        if found is None:
            raise NotFoundError(
                f"PromptReview {review_id!s} was not found in organization {organization_id!s}."
            )
        return found

    async def list_for_version(self, prompt_version_id: UUID) -> list[PromptReview]:
        """Every review of one revision, newest first."""
        stmt = (
            self._base_select()
            .where(PromptReview.prompt_version_id == prompt_version_id)
            .order_by(PromptReview.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def has_unresolved_mandatory(self, prompt_version_id: UUID) -> bool:
        """Whether a mandatory review is still outstanding.

        Decided **per reviewer, on that reviewer's latest mandatory
        verdict**, because a reviewer can be asked more than once about
        the same revision: :meth:`~app.services.governance.ReviewService.request`
        refuses only a second *pending* request, so re-review after
        ``CHANGES_REQUESTED`` is a supported flow. Counting every row
        instead would leave the superseded objection blocking forever,
        making the revision permanently unpublishable and the second
        round pointless -- the only escape being to cut a byte-identical
        revision purely to reset review state.

        Unresolved means the reviewer has not said yes:

        - ``PENDING`` -- they were asked and have not answered.
        - ``CHANGES_REQUESTED`` -- they asked for changes; publishing
          over that is publishing over an open objection.
        - ``REJECTED`` -- the strongest objection there is. It blocks for
          the same reason ``CHANGES_REQUESTED`` does, and more so:
          treating a rejection as "resolved because it is final" would
          let a mandatory reviewer's outright no be the one verdict the
          gate ignores.

        Only ``APPROVED`` resolves a reviewer.
        """
        stmt = (
            self._base_select()
            .where(
                PromptReview.prompt_version_id == prompt_version_id,
                PromptReview.is_mandatory.is_(True),
            )
            .order_by(PromptReview.created_at.desc(), PromptReview.id.desc())
        )
        result = await self._session.execute(stmt)

        latest_by_reviewer: dict[str, PromptReview] = {}
        for row in result.scalars().all():
            # Newest first, so the first row seen per reviewer is theirs.
            latest_by_reviewer.setdefault(row.reviewer_id, row)
        return any(row.decision != ReviewDecision.APPROVED for row in latest_by_reviewer.values())

    async def count_by_decision(self, prompt_version_id: UUID) -> dict[str, int]:
        """How many reviews of each decision one revision has."""
        stmt = self._base_select().where(PromptReview.prompt_version_id == prompt_version_id)
        result = await self._session.execute(stmt)
        counts: dict[str, int] = {}
        for row in result.scalars().all():
            key = str(row.decision)
            counts[key] = counts.get(key, 0) + 1
        return counts


class PromptApprovalRepository(BaseRepository[PromptApproval]):
    """CRUD plus lookup for :class:`PromptApproval`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptApproval, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, approval_id: UUID) -> PromptApproval:
        """Return *approval_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such approval exists in that organization.
        """
        stmt = self._base_select().where(
            PromptApproval.id == approval_id,
            PromptApproval.organization_id == organization_id,
        )
        result = await self._session.execute(stmt)
        found: PromptApproval | None = result.scalars().first()
        if found is None:
            raise NotFoundError(
                f"PromptApproval {approval_id!s} was not found in organization "
                f"{organization_id!s}."
            )
        return found

    async def list_for_version(self, prompt_version_id: UUID) -> list[PromptApproval]:
        """Every approval row for one revision."""
        stmt = (
            self._base_select()
            .where(PromptApproval.prompt_version_id == prompt_version_id)
            .order_by(PromptApproval.requested_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_approved(self, prompt_version_id: UUID) -> int:
        """How many distinct approvers have approved one revision.

        Counts distinct ``approver_id`` rather than rows: the same
        person approving twice must not satisfy a two-approver gate,
        which is the entire reason multi-approval exists.
        """
        stmt = self._base_select().where(
            PromptApproval.prompt_version_id == prompt_version_id,
            PromptApproval.status == ApprovalStatus.APPROVED,
        )
        result = await self._session.execute(stmt)
        return len({row.approver_id for row in result.scalars().all() if row.approver_id})

    async def list_pending_expired(
        self, moment: datetime, *, limit: int = 200
    ) -> list[PromptApproval]:
        """Pending approvals whose own deadline has passed.

        Backs the approval-expiry sweep. A request that sits unanswered
        forever silently blocks a publish with no signal anything is
        wrong -- visibly lapsing is strictly better.
        """
        stmt = (
            self._base_select()
            .where(
                PromptApproval.status == ApprovalStatus.PENDING,
                PromptApproval.expires_at <= moment,
            )
            .order_by(PromptApproval.expires_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_pending_for_org(
        self, organization_id: UUID, *, limit: int = 200
    ) -> list[PromptApproval]:
        """Every still-open approval request in one organization."""
        stmt = (
            self._base_select()
            .where(
                PromptApproval.organization_id == organization_id,
                PromptApproval.status == ApprovalStatus.PENDING,
            )
            .order_by(PromptApproval.requested_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class PromptSecurityScanRepository(BaseRepository[PromptSecurityScan]):
    """CRUD plus lookup for :class:`PromptSecurityScan`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptSecurityScan, tenant_scope=tenant_scope)

    async def list_for_version(self, prompt_version_id: UUID) -> list[PromptSecurityScan]:
        """Every scan of one revision, newest first."""
        stmt = (
            self._base_select()
            .where(PromptSecurityScan.prompt_version_id == prompt_version_id)
            .order_by(PromptSecurityScan.scanned_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def latest_for_version(self, prompt_version_id: UUID) -> PromptSecurityScan | None:
        """The most recent scan of one revision, or ``None``."""
        stmt = (
            self._base_select()
            .where(PromptSecurityScan.prompt_version_id == prompt_version_id)
            .order_by(PromptSecurityScan.scanned_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_blocking(
        self, organization_id: UUID, *, limit: int = 200
    ) -> list[PromptSecurityScan]:
        """Scans currently blocking a publish in one organization."""
        stmt = (
            self._base_select()
            .where(
                PromptSecurityScan.organization_id == organization_id,
                PromptSecurityScan.status == ScanStatus.BLOCKED,
            )
            .order_by(PromptSecurityScan.scanned_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_findings_in_window(
        self, organization_id: UUID, *, since: datetime, until: datetime
    ) -> int:
        """Total findings recorded for one organization in a window."""
        stmt = self._base_select().where(
            PromptSecurityScan.organization_id == organization_id,
            PromptSecurityScan.scanned_at >= since,
            PromptSecurityScan.scanned_at < until,
        )
        result = await self._session.execute(stmt)
        return sum(row.finding_count for row in result.scalars().all())


__all__ = [
    "PromptApprovalRepository",
    "PromptReviewRepository",
    "PromptSecurityScanRepository",
]
