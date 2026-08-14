"""Password policy validation, IP allowlist matching, and session
expiry -- the pure decisions behind security administration.

**Every violation a password fails is named, never just a pass/fail
bit** -- an administrator writing a policy needs to know *which* rule
rejected a password to explain it to the user who hit it.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class PasswordPolicyResult:
    is_valid: bool
    violations: tuple[str, ...]


def validate_password_policy(
    password: str,
    *,
    min_length: int,
    require_upper: bool,
    require_lower: bool,
    require_digit: bool,
    require_symbol: bool,
) -> PasswordPolicyResult:
    """Validate *password* against a configurable policy, naming every
    rule it fails.

    Raises:
        ValueError: On a non-positive *min_length*.
    """
    if min_length < 1:
        raise ValueError(f"min_length must be at least 1; got {min_length}.")

    violations: list[str] = []
    if len(password) < min_length:
        violations.append(f"must be at least {min_length} characters long")
    if require_upper and not any(char.isupper() for char in password):
        violations.append("must contain an uppercase letter")
    if require_lower and not any(char.islower() for char in password):
        violations.append("must contain a lowercase letter")
    if require_digit and not any(char.isdigit() for char in password):
        violations.append("must contain a digit")
    if require_symbol and not any(not char.isalnum() for char in password):
        violations.append("must contain a symbol")
    return PasswordPolicyResult(is_valid=not violations, violations=tuple(violations))


def is_ip_allowed(ip_address: str, *, allowed_cidrs: Sequence[str]) -> bool:
    """Whether *ip_address* falls within any of *allowed_cidrs*.

    An empty *allowed_cidrs* means no restriction is configured -- every
    address is allowed.

    Raises:
        ValueError: If *ip_address* or any entry in *allowed_cidrs* is
            not a valid IP address / network.
    """
    if not allowed_cidrs:
        return True
    address = ipaddress.ip_address(ip_address)
    return any(address in ipaddress.ip_network(cidr, strict=False) for cidr in allowed_cidrs)


def is_session_expired(*, started_at: datetime, max_age_minutes: int, now: datetime) -> bool:
    """Whether an administrator session has outlived its configured
    maximum age.

    Raises:
        ValueError: On a non-positive *max_age_minutes*.
    """
    if max_age_minutes < 1:
        raise ValueError(f"max_age_minutes must be at least 1; got {max_age_minutes}.")
    return now >= started_at + timedelta(minutes=max_age_minutes)


__all__ = [
    "PasswordPolicyResult",
    "is_ip_allowed",
    "is_session_expired",
    "validate_password_policy",
]
