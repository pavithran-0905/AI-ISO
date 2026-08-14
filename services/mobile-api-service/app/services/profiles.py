"""Mobile profile read/update, with lazy default creation."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models.devices import MobileProfile
from app.repositories.devices import MobileProfileRepository


class ProfileService:
    def __init__(self, repo: MobileProfileRepository) -> None:
        self._repo = repo

    async def get_or_create(self, organization_id: UUID, *, user_id: str) -> MobileProfile:
        existing = await self._repo.find_by_user(organization_id, user_id=user_id)
        if existing is not None:
            return existing
        return await self._repo.create(
            MobileProfile(organization_id=organization_id, user_id=user_id)
        )

    async def update(
        self,
        profile: MobileProfile,
        *,
        display_name: str | None = None,
        locale: str | None = None,
        timezone: str | None = None,
        preferences: dict[str, Any] | None = None,
    ) -> MobileProfile:
        if display_name is not None:
            profile.display_name = display_name
        if locale is not None:
            profile.locale = locale
        if timezone is not None:
            profile.timezone = timezone
        if preferences is not None:
            profile.preferences = preferences
        return await self._repo.update(profile)


__all__ = ["ProfileService"]
