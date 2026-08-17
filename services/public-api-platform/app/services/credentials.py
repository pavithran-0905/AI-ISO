"""API key, personal access token, OAuth client, and OAuth token
issuance and lifecycle.

Publishes ``APIKeyGenerated`` on every issued API key and
``OAuthClientCreated`` on every registered OAuth client -- the two
credential-related events docs/073 names.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

from app.api_keys.engine import TransitionResult, validate_transition
from app.events.domain_events import APIKeyGeneratedEvent, OAuthClientCreatedEvent
from app.models.credentials import ApiKey, OAuthClient, PersonalAccessToken
from app.models.enums import CredentialStatus, DeveloperAuditAction
from app.repositories.credentials import (
    ApiKeyRepository,
    OAuthClientRepository,
    PersonalAccessTokenRepository,
)
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "public-api-platform"
_TOKEN_BYTES = 32


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


def _hash_secret(raw: str) -> str:
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def _generate_secret() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


class ApiKeyService:
    def __init__(
        self,
        repo: ApiKeyRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit

    async def issue(
        self, organization_id: UUID, *, application_id: UUID, now: datetime, max_age_days: int
    ) -> tuple[ApiKey, str]:
        raw_key = _generate_secret()
        key = await self._repo.create(
            ApiKey(
                organization_id=organization_id,
                application_id=application_id,
                key_hash=_hash_secret(raw_key),
                expires_at=now + timedelta(days=max_age_days),
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id=organization_id,
                action=DeveloperAuditAction.CREDENTIAL_CHANGE,
                entity_type="api_key",
                entity_id=key.id,
                occurred_at=now,
                summary=f"API key issued for application {application_id!s}.",
            )
        await self._publish(
            APIKeyGeneratedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"api_key_id": str(key.id), "application_id": str(application_id)},
            )
        )
        return key, raw_key

    async def revoke(self, key: ApiKey, *, now: datetime) -> ApiKey:
        result = validate_transition(key.status, CredentialStatus.REVOKED)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        key.status = CredentialStatus.REVOKED
        key.revoked_at = now
        return await self._repo.update(key)


class PersonalAccessTokenService:
    def __init__(self, repo: PersonalAccessTokenRepository) -> None:
        self._repo = repo

    async def issue(
        self,
        organization_id: UUID,
        *,
        developer_account_id: UUID,
        name: str,
        scopes: list[str],
        now: datetime,
        max_age_days: int,
    ) -> tuple[PersonalAccessToken, str]:
        raw_token = _generate_secret()
        token = await self._repo.create(
            PersonalAccessToken(
                organization_id=organization_id,
                developer_account_id=developer_account_id,
                name=name,
                token_hash=_hash_secret(raw_token),
                scopes=scopes,
                expires_at=now + timedelta(days=max_age_days),
            )
        )
        return token, raw_token

    async def revoke(self, token: PersonalAccessToken, *, now: datetime) -> PersonalAccessToken:
        result = validate_transition(token.status, CredentialStatus.REVOKED)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        token.status = CredentialStatus.REVOKED
        token.revoked_at = now
        return await self._repo.update(token)


class OAuthClientService:
    def __init__(
        self, repo: OAuthClientRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def register(
        self,
        organization_id: UUID,
        *,
        application_id: UUID,
        grant_types: list[str],
        redirect_uris: list[str],
        now: datetime,
    ) -> tuple[OAuthClient, str]:
        raw_secret = _generate_secret()
        client = await self._repo.create(
            OAuthClient(
                organization_id=organization_id,
                application_id=application_id,
                client_id=secrets.token_hex(16),
                client_secret_hash=_hash_secret(raw_secret),
                grant_types=grant_types,
                redirect_uris=redirect_uris,
            )
        )
        await self._publish(
            OAuthClientCreatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"oauth_client_id": str(client.id), "application_id": str(application_id)},
            )
        )
        return client, raw_secret


__all__ = [
    "ApiKeyService",
    "OAuthClientService",
    "PersonalAccessTokenService",
    "TransitionRefusedError",
]
