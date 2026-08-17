"""Secret generation, masking, and rotation staleness.

Vault integration (docs/075's "SECRETS MANAGEMENT" names HashiCorp
Vault) is a declared seam -- per
``shared_core.security.secrets``'s own module docstring, external
secret-manager backends are future work across this entire codebase,
not something this service implements independently.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from shared_core.security.secrets import mask_secret

_DEFAULT_LENGTH = 32


def generate_credential(length: int = _DEFAULT_LENGTH) -> str:
    """Generate a cryptographically random, URL-safe credential of at
    least *length* bytes of entropy."""
    return secrets.token_urlsafe(length)


def mask_for_display(value: str) -> str:
    """The masked form of a secret, safe to store and display -- the
    raw value itself is never persisted anywhere in this service."""
    return mask_secret(value)


def is_rotation_due(*, generated_at: datetime, now: datetime, max_age_days: int) -> bool:
    """Whether a secret has aged past its own configured maximum
    lifetime and should be rotated."""
    return now >= generated_at + timedelta(days=max_age_days)


__all__ = ["generate_credential", "is_rotation_due", "mask_for_display"]
