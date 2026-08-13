"""Failover authorization: health-check aggregation and the automatic /
manual gate.

**An automatic failover requires every health check to agree, and a
manual one does not.** Automation is authorized to act on unanimous,
unambiguous evidence only; a human invoking a manual failover has
context this engine cannot see (a known-flaky check, an ongoing
incident call) and is allowed to proceed against a health check that
looks bad, because the alternative -- automation silently downgrading
every manual override into an automatic-shaped decision -- removes the
one thing a manual override is for.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.models.enums import FailoverKind


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    """One health check's outcome, from one probe attempt."""

    check_name: str
    is_healthy: bool
    detail: str


@dataclass(frozen=True, slots=True)
class HealthAssessment:
    """Aggregated health across every check that ran."""

    all_healthy: bool
    healthy_count: int
    total_count: int
    failing_checks: tuple[str, ...]


def assess_health(results: Sequence[HealthCheckResult]) -> HealthAssessment:
    """Aggregate individual health checks into one verdict.

    An empty result set is **not** healthy: no checks having run is not
    evidence of health, it is an absence of evidence, and defaulting it
    to "healthy" would authorize an automatic failover on a target that
    was simply never probed.
    """
    if not results:
        return HealthAssessment(
            all_healthy=False, healthy_count=0, total_count=0, failing_checks=()
        )
    failing = tuple(result.check_name for result in results if not result.is_healthy)
    healthy_count = len(results) - len(failing)
    return HealthAssessment(
        all_healthy=not failing,
        healthy_count=healthy_count,
        total_count=len(results),
        failing_checks=failing,
    )


class AuthorizationRefusal:
    HEALTH_CHECKS_FAILING = "health_checks_failing"
    NO_HEALTH_CHECKS_RAN = "no_health_checks_ran"


@dataclass(frozen=True, slots=True)
class AuthorizationResult:
    is_authorized: bool
    refusal: str | None
    detail: str


def authorize_failover(kind: FailoverKind, assessment: HealthAssessment) -> AuthorizationResult:
    """Whether a failover of *kind* may proceed given *assessment*.

    Manual and failback failovers are always authorized at this layer --
    the human invoking them carries the responsibility a health check
    cannot substitute for. Only ``AUTOMATIC`` is gated here.
    """
    if kind is not FailoverKind.AUTOMATIC:
        return AuthorizationResult(
            is_authorized=True,
            refusal=None,
            detail=f"{kind.value} failover does not require automated health-check authorization.",
        )
    if assessment.total_count == 0:
        return AuthorizationResult(
            is_authorized=False,
            refusal=AuthorizationRefusal.NO_HEALTH_CHECKS_RAN,
            detail=(
                "No health checks ran; an automatic failover cannot authorize itself "
                "on an absence of evidence."
            ),
        )
    if not assessment.all_healthy:
        return AuthorizationResult(
            is_authorized=False,
            refusal=AuthorizationRefusal.HEALTH_CHECKS_FAILING,
            detail=(
                f"{len(assessment.failing_checks)} of {assessment.total_count} health "
                f"checks are failing ({', '.join(assessment.failing_checks)})."
            ),
        )
    return AuthorizationResult(
        is_authorized=True,
        refusal=None,
        detail=f"All {assessment.total_count} health checks passed.",
    )


__all__ = [
    "AuthorizationRefusal",
    "AuthorizationResult",
    "HealthAssessment",
    "HealthCheckResult",
    "assess_health",
    "authorize_failover",
]
