"""CLI profile creation, ensuring at most one default per organization.

Wires ``app.cli.profiles.engine``'s pure default-selection logic onto
the repository that persists profiles, publishing ``ProfileCreated``.
"""

from __future__ import annotations

from uuid import UUID

from app.cli.profiles.engine import profiles_to_unset
from app.events.domain_events import ProfileCreatedEvent
from app.models.cli import CliProfile
from app.models.enums import CliAuthMethod
from app.repositories.cli import CliProfileRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "sdk-cli-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class CliProfileService:
    def __init__(
        self, repo: CliProfileRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def create_profile(
        self,
        organization_id: UUID,
        *,
        profile_name: str,
        auth_method: CliAuthMethod,
        organization_context: UUID | None = None,
        project_context: UUID | None = None,
        region_context: str | None = None,
        is_default: bool = False,
    ) -> CliProfile:
        profile = await self._repo.create(
            CliProfile(
                organization_id=organization_id,
                profile_name=profile_name,
                auth_method=auth_method,
                organization_context=organization_context,
                project_context=project_context,
                region_context=region_context,
                is_default=is_default,
            )
        )
        if is_default:
            await self._enforce_single_default(organization_id, new_default_id=profile.id)
        await self._publish(
            ProfileCreatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"cli_profile_id": str(profile.id), "profile_name": profile_name},
            )
        )
        return profile

    async def make_default(self, profile: CliProfile) -> CliProfile:
        profile.is_default = True
        await self._repo.update(profile)
        await self._enforce_single_default(profile.organization_id, new_default_id=profile.id)
        return profile

    async def _enforce_single_default(self, organization_id: UUID, *, new_default_id: UUID) -> None:
        existing_default_ids = await self._repo.list_default_ids(organization_id)
        for profile_id in profiles_to_unset(existing_default_ids, new_default_id=new_default_id):
            stale_default = await self._repo.require_by_id(profile_id)
            stale_default.is_default = False
            await self._repo.update(stale_default)


__all__ = ["CliProfileService"]
