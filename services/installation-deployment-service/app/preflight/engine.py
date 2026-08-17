"""Pre-flight infrastructure readiness aggregation.

``aggregate_check_results`` is the shared worst-of-N rule -- reused
unmodified by ``app.verification.engine`` for post-install/post-upgrade
verification, since both are "many named checks, one overall outcome"
problems with an identical worst-case rule (mirroring
``services/developer-portal-service``'s own precedent of one engine
function reused by more than one caller).
"""

from __future__ import annotations

from collections.abc import Iterable

from app.models.enums import CheckResultStatus

_S = CheckResultStatus


def aggregate_check_results(results: Iterable[CheckResultStatus]) -> CheckResultStatus:
    """The worst outcome among *results*: any ``FAILED`` outranks any
    ``WARNING``, which outranks an all-``PASSED`` run. An empty
    iterable is vacuously ``PASSED`` -- there is nothing to have
    failed."""
    statuses = [_S(result) for result in results]
    if any(status == _S.FAILED for status in statuses):
        return _S.FAILED
    if any(status == _S.WARNING for status in statuses):
        return _S.WARNING
    return _S.PASSED


def is_ready(overall: CheckResultStatus) -> bool:
    """Whether an aggregate outcome represents a green light to
    proceed. ``WARNING`` is still a go -- it is advisory, not
    blocking."""
    return CheckResultStatus(overall) != _S.FAILED


__all__ = ["aggregate_check_results", "is_ready"]
