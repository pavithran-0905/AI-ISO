"""Zero-touch provisioning: device identity/credential validation.

**A credential is never trusted merely because a caller supplied one.**
An empty reference or an already-expired credential is refused at
enrollment time -- accepting it and discovering the problem the first
time this service actually tries to reach the device turns a
configuration mistake into an operational incident.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class CredentialRefusal:
    EMPTY_REFERENCE = "empty_reference"
    ALREADY_EXPIRED = "already_expired"


@dataclass(frozen=True, slots=True)
class CredentialValidation:
    is_valid: bool
    refusal: str | None
    detail: str


def validate_credential(
    credential_ref: str, *, expires_at: datetime | None, now: datetime
) -> CredentialValidation:
    """Whether a credential reference is usable right now.

    The actual certificate/secret this reference points to is never seen
    or validated here -- that is secrets-management-service's job. This
    checks only what this service's own row can know: that a reference
    was actually supplied, and that it has not already expired.
    """
    if not credential_ref.strip():
        return CredentialValidation(
            is_valid=False,
            refusal=CredentialRefusal.EMPTY_REFERENCE,
            detail="No credential reference was supplied.",
        )
    if expires_at is not None and expires_at <= now:
        return CredentialValidation(
            is_valid=False,
            refusal=CredentialRefusal.ALREADY_EXPIRED,
            detail=f"Credential expired at {expires_at.isoformat()}.",
        )
    return CredentialValidation(is_valid=True, refusal=None, detail="Credential is usable.")


def is_credential_expired(expires_at: datetime | None, *, now: datetime) -> bool:
    """Whether a credential has passed its expiry.

    ``expires_at is None`` means "does not expire" -- never treated as
    expired by the passage of time alone.
    """
    return expires_at is not None and expires_at <= now


__all__ = [
    "CredentialRefusal",
    "CredentialValidation",
    "is_credential_expired",
    "validate_credential",
]
