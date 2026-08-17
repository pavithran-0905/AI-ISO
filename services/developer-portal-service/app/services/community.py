"""Community discussion posts and comments.

Publishes ``CommunityPostCreated`` on every new post, and notifies
Community Reply directly whenever a comment lands on someone else's
post.
"""

from __future__ import annotations

from uuid import UUID

from app.community.engine import TransitionResult, compute_reputation_delta, validate_transition
from app.events.domain_events import CommunityPostCreatedEvent
from app.models.community import CommunityComment, CommunityPost
from app.models.enums import CommunityPostStatus, CommunityPostType
from app.repositories.community import CommunityCommentRepository, CommunityPostRepository
from app.services.notifications import PortalNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "developer-portal-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class CommunityPostService:
    def __init__(
        self, repo: CommunityPostRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def create(
        self,
        organization_id: UUID,
        *,
        user_id: str,
        post_type: CommunityPostType,
        title: str,
        body: str,
        tags: list[str] | None = None,
    ) -> CommunityPost:
        post = await self._repo.create(
            CommunityPost(
                organization_id=organization_id,
                user_id=user_id,
                post_type=post_type,
                title=title,
                body=body,
                tags=tags or [],
            )
        )
        await self._publish(
            CommunityPostCreatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"community_post_id": str(post.id), "post_type": post_type.value},
            )
        )
        return post

    async def transition(
        self, post: CommunityPost, *, target: CommunityPostStatus
    ) -> CommunityPost:
        result = validate_transition(post.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        post.status = target
        return await self._repo.update(post)

    async def accept_comment(
        self, post: CommunityPost, *, comment: CommunityComment
    ) -> CommunityPost:
        """Mark *comment* as the post's own accepted answer, moving the
        post to ``ANSWERED``."""
        post.accepted_comment_id = comment.id
        post = await self.transition(post, target=CommunityPostStatus.ANSWERED)
        return post


class CommunityCommentService:
    def __init__(
        self,
        repo: CommunityCommentRepository,
        *,
        notifier: PortalNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._notifier = notifier

    async def create(
        self, organization_id: UUID, *, post: CommunityPost, user_id: str, body: str
    ) -> CommunityComment:
        comment = await self._repo.create(
            CommunityComment(
                organization_id=organization_id,
                community_post_id=post.id,
                user_id=user_id,
                body=body,
            )
        )
        if user_id != post.user_id and self._notifier is not None:
            await self._notifier.notify_community_reply(post_title=post.title)
        return comment

    async def accept(self, comment: CommunityComment, *, upvotes: int) -> CommunityComment:
        comment.is_accepted = True
        comment.upvotes = upvotes
        return await self._repo.update(comment)

    @staticmethod
    def reputation_for(comment: CommunityComment) -> int:
        return compute_reputation_delta(
            upvotes=comment.upvotes, is_accepted_answer=comment.is_accepted
        )


__all__ = ["CommunityCommentService", "CommunityPostService", "TransitionRefusedError"]
