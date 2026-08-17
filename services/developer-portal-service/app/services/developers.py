"""Developer profiles, portal sessions, bookmarks, and favorites.

Publishes ``DeveloperLoggedIn`` on every new session.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from app.events.domain_events import DeveloperLoggedInEvent
from app.models.developers import (
    DeveloperBookmark,
    DeveloperFavorite,
    DeveloperProfile,
    DeveloperSession,
)
from app.models.enums import DeveloperSessionStatus, SearchContentType
from app.portal.engine import is_session_expired
from app.repositories.developers import (
    DeveloperBookmarkRepository,
    DeveloperFavoriteRepository,
    DeveloperProfileRepository,
    DeveloperSessionRepository,
)
from app.types import EventPublisher

_SOURCE_SERVICE = "developer-portal-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class DeveloperProfileService:
    def __init__(self, repo: DeveloperProfileRepository) -> None:
        self._repo = repo

    async def get_or_create(self, organization_id: UUID, *, user_id: str) -> DeveloperProfile:
        existing = await self._repo.find_by_user(organization_id, user_id=user_id)
        if existing is not None:
            return existing
        return await self._repo.create(
            DeveloperProfile(organization_id=organization_id, user_id=user_id)
        )

    async def update(
        self,
        profile: DeveloperProfile,
        *,
        display_name: str | None = None,
        bio: str | None = None,
        avatar_url: str | None = None,
    ) -> DeveloperProfile:
        if display_name is not None:
            profile.display_name = display_name
        if bio is not None:
            profile.bio = bio
        if avatar_url is not None:
            profile.avatar_url = avatar_url
        return await self._repo.update(profile)


class DeveloperSessionService:
    def __init__(
        self, repo: DeveloperSessionRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def login(
        self, organization_id: UUID, *, user_id: str, now: datetime, max_age_hours: int
    ) -> DeveloperSession:
        session = await self._repo.create(
            DeveloperSession(
                organization_id=organization_id,
                user_id=user_id,
                issued_at=now,
                expires_at=now + timedelta(hours=max_age_hours),
            )
        )
        await self._publish(
            DeveloperLoggedInEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"user_id": user_id},
            )
        )
        return session

    async def expire(self, session: DeveloperSession) -> DeveloperSession:
        session.status = DeveloperSessionStatus.EXPIRED
        return await self._repo.update(session)

    @staticmethod
    def is_expired(session: DeveloperSession, *, now: datetime) -> bool:
        return is_session_expired(expires_at=session.expires_at, now=now)


class BookmarkService:
    def __init__(self, repo: DeveloperBookmarkRepository) -> None:
        self._repo = repo

    async def add(
        self,
        organization_id: UUID,
        *,
        user_id: str,
        content_type: SearchContentType,
        content_id: UUID,
    ) -> DeveloperBookmark:
        existing = await self._repo.find(
            organization_id, user_id=user_id, content_type=content_type, content_id=content_id
        )
        if existing is not None:
            return existing
        return await self._repo.create(
            DeveloperBookmark(
                organization_id=organization_id,
                user_id=user_id,
                content_type=content_type,
                content_id=content_id,
            )
        )


class FavoriteService:
    def __init__(self, repo: DeveloperFavoriteRepository) -> None:
        self._repo = repo

    async def add(
        self,
        organization_id: UUID,
        *,
        user_id: str,
        content_type: SearchContentType,
        content_id: UUID,
    ) -> DeveloperFavorite:
        existing = await self._repo.find(
            organization_id, user_id=user_id, content_type=content_type, content_id=content_id
        )
        if existing is not None:
            return existing
        return await self._repo.create(
            DeveloperFavorite(
                organization_id=organization_id,
                user_id=user_id,
                content_type=content_type,
                content_id=content_id,
            )
        )


__all__ = [
    "BookmarkService",
    "DeveloperProfileService",
    "DeveloperSessionService",
    "FavoriteService",
]
