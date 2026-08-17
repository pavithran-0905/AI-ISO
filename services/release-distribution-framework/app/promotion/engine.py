"""Release promotion path validation.

docs/080's own "RELEASE PROMOTION" section names a maturity ladder
(Development -> QA -> UAT -> Production, Canary -> Stable, Stable ->
LTS) that doesn't map one-to-one onto the channel vocabulary this
service's own ``ReleaseChannelType`` uses (there is no distinct "QA"
or "UAT" channel -- see docs/080's own "RELEASE CHANNELS" section).
This engine bridges the two: the literal Canary -> Stable and Stable
-> LTS transitions are preserved exactly, and the Development -> QA ->
UAT -> Production maturity idea is generalized into this service's own
channel maturity ladder (DEVELOPMENT -> ALPHA -> BETA ->
RELEASE_CANDIDATE -> STABLE).
"""

from __future__ import annotations

from app.models.enums import ReleaseChannelType

_C = ReleaseChannelType

ALLOWED_PROMOTIONS: dict[ReleaseChannelType, frozenset[ReleaseChannelType]] = {
    _C.DEVELOPMENT: frozenset({_C.ALPHA, _C.NIGHTLY}),
    _C.NIGHTLY: frozenset({_C.ALPHA}),
    _C.ALPHA: frozenset({_C.BETA}),
    _C.BETA: frozenset({_C.RELEASE_CANDIDATE}),
    _C.RELEASE_CANDIDATE: frozenset({_C.STABLE}),
    _C.CANARY: frozenset({_C.STABLE}),
    _C.STABLE: frozenset(
        {_C.LTS, _C.OEM, _C.REGIONAL, _C.PRIVATE_ENTERPRISE, _C.CUSTOMER_SPECIFIC}
    ),
    _C.LTS: frozenset(),
    _C.OEM: frozenset(),
    _C.PRIVATE_ENTERPRISE: frozenset(),
    _C.REGIONAL: frozenset(),
    _C.CUSTOMER_SPECIFIC: frozenset(),
}


def is_valid_promotion(*, from_channel: ReleaseChannelType, to_channel: ReleaseChannelType) -> bool:
    """Whether a release version may be promoted directly from
    *from_channel* to *to_channel*."""
    from_channel = ReleaseChannelType(from_channel)
    to_channel = ReleaseChannelType(to_channel)
    return to_channel in ALLOWED_PROMOTIONS.get(from_channel, frozenset())


__all__ = ["ALLOWED_PROMOTIONS", "is_valid_promotion"]
