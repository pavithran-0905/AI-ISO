"""Documentation page authoring, publication, and reader feedback.

Publishes ``DocumentationPublished`` on every ``-> PUBLISHED``
transition.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.documentation.engine import TransitionResult, validate_transition
from app.events.domain_events import DocumentationPublishedEvent
from app.models.documentation import DocumentationFeedback, DocumentationPage, DocumentationVersion
from app.models.enums import ContentStatus, FeedbackSentiment, PortalAuditAction
from app.repositories.documentation import (
    DocumentationFeedbackRepository,
    DocumentationPageRepository,
    DocumentationVersionRepository,
)
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "developer-portal-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class DocumentationPageService:
    def __init__(
        self,
        repo: DocumentationPageRepository,
        version_repo: DocumentationVersionRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._version_repo = version_repo
        self._publish = publish
        self._audit = audit

    async def create(
        self,
        organization_id: UUID,
        *,
        slug: str,
        title: str,
        content: str,
        category: str = "general",
    ) -> DocumentationPage:
        return await self._repo.create(
            DocumentationPage(
                organization_id=organization_id,
                slug=slug,
                title=title,
                content=content,
                category=category,
            )
        )

    async def transition(
        self,
        page: DocumentationPage,
        *,
        target: ContentStatus,
        now: datetime,
        actor_id: str | None = None,
    ) -> DocumentationPage:
        """Move *page* to *target*, raising :class:`TransitionRefusedError`
        if the transition is not allowed. Snapshots the page's own
        content into ``documentation_versions`` on every publish."""
        result = validate_transition(page.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        page.status = target
        if target == ContentStatus.PUBLISHED:
            page.published_at = now
        await self._repo.update(page)

        if target == ContentStatus.PUBLISHED:
            await self._version_repo.create(
                DocumentationVersion(
                    organization_id=page.organization_id,
                    documentation_page_id=page.id,
                    version_label=now.strftime("%Y%m%d%H%M%S"),
                    content=page.content,
                    published_at=now,
                )
            )

        if self._audit is not None:
            await self._audit.record(
                organization_id=page.organization_id,
                action=PortalAuditAction.DOCUMENTATION_CHANGE,
                entity_type="documentation_page",
                entity_id=page.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Documentation page {page.slug!r} moved to {target.value}.",
            )
        if target == ContentStatus.PUBLISHED:
            await self._publish(
                DocumentationPublishedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=page.organization_id,
                    payload={
                        "documentation_page_id": str(page.id),
                        "slug": page.slug,
                        "title": page.title,
                    },
                )
            )
        return page


class DocumentationFeedbackService:
    def __init__(self, repo: DocumentationFeedbackRepository) -> None:
        self._repo = repo

    async def submit(
        self,
        organization_id: UUID,
        *,
        documentation_page_id: UUID,
        user_id: str,
        sentiment: FeedbackSentiment,
        comment: str = "",
    ) -> DocumentationFeedback:
        return await self._repo.create(
            DocumentationFeedback(
                organization_id=organization_id,
                documentation_page_id=documentation_page_id,
                user_id=user_id,
                sentiment=sentiment,
                comment=comment,
            )
        )


__all__ = ["DocumentationFeedbackService", "DocumentationPageService", "TransitionRefusedError"]
