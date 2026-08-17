"""The credential expiry sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Expires every active API key, personal access token, and OAuth token
past its own ``expires_at``, and notifies Credential Expiring once a
still-active credential enters its own expiry warning window.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api_keys.engine import is_expired, is_expiring_soon
from app.models.enums import CredentialStatus, OAuthTokenStatus
from app.services.bundle import build_repositories
from app.services.notifications import DeveloperNotifier

logger = get_logger("app.workers.credential_expiry_sweep")


class CredentialExpirySweepWorker:
    """Expires stale credentials and warns of imminent expiry across
    API keys, personal access tokens, and OAuth tokens."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: DeveloperNotifier,
        warning_days: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._warning_days = warning_days

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's active credentials, returning how
        many were checked."""
        now = datetime.now(UTC)
        checked = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.api_keys.list_organization_ids():
                for key in await repos.api_keys.list_active(organization_id):
                    if is_expired(expires_at=key.expires_at, now=now):
                        key.status = CredentialStatus.EXPIRED
                        await repos.api_keys.update(key)
                    elif is_expiring_soon(
                        expires_at=key.expires_at, now=now, warning_days=self._warning_days
                    ):
                        await self._notifier.notify_credential_expiring(
                            credential_kind="API key", expires_at=key.expires_at.isoformat()
                        )
                    checked += 1

            for organization_id in await repos.personal_access_tokens.list_organization_ids():
                for token in await repos.personal_access_tokens.list_active(organization_id):
                    if is_expired(expires_at=token.expires_at, now=now):
                        token.status = CredentialStatus.EXPIRED
                        await repos.personal_access_tokens.update(token)
                    elif is_expiring_soon(
                        expires_at=token.expires_at, now=now, warning_days=self._warning_days
                    ):
                        await self._notifier.notify_credential_expiring(
                            credential_kind="personal access token",
                            expires_at=token.expires_at.isoformat(),
                        )
                    checked += 1

            for organization_id in await repos.oauth_tokens.list_organization_ids():
                for oauth_token in await repos.oauth_tokens.list_active(organization_id):
                    if is_expired(expires_at=oauth_token.expires_at, now=now):
                        oauth_token.status = OAuthTokenStatus.EXPIRED
                        await repos.oauth_tokens.update(oauth_token)
                    checked += 1

            await session.commit()

        logger.info(
            "credential expiry sweep completed", extra={"extra_fields": {"checked": checked}}
        )
        return checked


__all__ = ["CredentialExpirySweepWorker"]
