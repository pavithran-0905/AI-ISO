"""Secret generation and rotation.

The raw generated value is returned to the caller exactly once, at
generation time -- never persisted, never re-readable afterward. Only
the masked display form is stored, matching this service's own
``GeneratedSecret`` model docstring.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.models.enums import SecretStatus, SecretType
from app.models.secrets_tls import GeneratedSecret
from app.repositories.secrets_tls import GeneratedSecretRepository
from app.secrets.engine import generate_credential, mask_for_display


@dataclass(frozen=True, slots=True)
class IssuedSecret:
    record: GeneratedSecret
    raw_value: str


class SecretsService:
    def __init__(self, repo: GeneratedSecretRepository) -> None:
        self._repo = repo

    async def generate(
        self, organization_id: UUID, *, secret_name: str, secret_type: SecretType, now: datetime
    ) -> IssuedSecret:
        raw_value = generate_credential()
        record = await self._repo.create(
            GeneratedSecret(
                organization_id=organization_id,
                secret_name=secret_name,
                secret_type=secret_type,
                masked_value=mask_for_display(raw_value),
                generated_at=now,
            )
        )
        return IssuedSecret(record=record, raw_value=raw_value)

    async def rotate(self, secret: GeneratedSecret, *, now: datetime) -> IssuedSecret:
        """Retire *secret* (its own row moves to ``ROTATED``, permanently)
        and issue a brand new ``ACTIVE`` row under the same name -- a
        rotation is a new credential, not an edit of the old one, so the
        superseded row's own history stays intact."""
        secret.status = SecretStatus.ROTATED
        secret.rotated_at = now
        await self._repo.update(secret)

        raw_value = generate_credential()
        record = await self._repo.create(
            GeneratedSecret(
                organization_id=secret.organization_id,
                secret_name=secret.secret_name,
                secret_type=secret.secret_type,
                masked_value=mask_for_display(raw_value),
                generated_at=now,
            )
        )
        return IssuedSecret(record=record, raw_value=raw_value)


__all__ = ["IssuedSecret", "SecretsService"]
