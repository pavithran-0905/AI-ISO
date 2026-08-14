"""CLI session authentication and lifecycle.

Wires ``app.cli.authentication.engine``'s pure expiry check onto the
repository that persists sessions, publishing
``AuthenticationSucceeded`` on a successful login and notifying
Authentication Failure directly on a failed one -- there is no
``AuthenticationFailed`` domain event in docs/071's own EVENTS list, so
a failed attempt is never persisted as a session at all, only
notified.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.cli.authentication.engine import is_session_expired
from app.events.domain_events import AuthenticationSucceededEvent
from app.models.cli import CliProfile, CliSession
from app.models.enums import CliAuthMethod
from app.repositories.cli import CliSessionRepository
from app.services.notifications import SdkCliNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "sdk-cli-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class AuthenticationFailedError(Exception):
    """Raised when a CLI authentication attempt is reported as failed."""

    def __init__(self, profile_name: str, auth_method: CliAuthMethod) -> None:
        auth_method = CliAuthMethod(auth_method)
        super().__init__(
            f"Authentication failed for profile {profile_name!r} via {auth_method.value}."
        )
        self.profile_name = profile_name
        self.auth_method = auth_method


class CliSessionService:
    def __init__(
        self,
        repo: CliSessionRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: SdkCliNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def authenticate(
        self,
        profile: CliProfile,
        *,
        succeeded: bool,
        max_age_minutes: int,
        now: datetime,
    ) -> CliSession:
        """Record an authentication attempt for *profile*.

        Raises:
            AuthenticationFailedError: If *succeeded* is ``False`` --
                a failed attempt is notified, never persisted as a
                session.
        """
        if not succeeded:
            auth_method = CliAuthMethod(profile.auth_method)
            if self._notifier is not None:
                await self._notifier.notify_authentication_failure(
                    profile_name=profile.profile_name, auth_method=auth_method.value
                )
            raise AuthenticationFailedError(profile.profile_name, auth_method)

        auth_method = CliAuthMethod(profile.auth_method)
        session = await self._repo.create(
            CliSession(
                organization_id=profile.organization_id,
                profile_id=profile.id,
                auth_method=auth_method,
                started_at=now,
                expires_at=now + timedelta(minutes=max_age_minutes),
            )
        )
        await self._publish(
            AuthenticationSucceededEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=profile.organization_id,
                payload={"cli_session_id": str(session.id), "auth_method": auth_method.value},
            )
        )
        return session

    async def force_logout(self, session: CliSession) -> CliSession:
        session.is_enabled = False
        return await self._repo.update(session)

    def is_usable(self, session: CliSession, *, now: datetime) -> bool:
        return session.is_enabled and not is_session_expired(session.expires_at, now=now)


__all__ = ["AuthenticationFailedError", "CliSessionService"]
