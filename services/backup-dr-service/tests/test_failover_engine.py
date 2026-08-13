"""Tests for app.failover.engine: health aggregation and authorization gating."""

from __future__ import annotations

from app.failover.engine import (
    AuthorizationRefusal,
    HealthCheckResult,
    assess_health,
    authorize_failover,
)
from app.models.enums import FailoverKind


def _check(name: str, healthy: bool) -> HealthCheckResult:
    return HealthCheckResult(check_name=name, is_healthy=healthy, detail="")


class TestAssessHealth:
    def test_empty_results_not_healthy(self) -> None:
        result = assess_health([])
        assert not result.all_healthy
        assert result.total_count == 0
        assert result.healthy_count == 0

    def test_all_healthy(self) -> None:
        result = assess_health([_check("db", True), _check("cache", True)])
        assert result.all_healthy
        assert result.healthy_count == 2
        assert result.failing_checks == ()

    def test_some_failing(self) -> None:
        result = assess_health([_check("db", True), _check("cache", False)])
        assert not result.all_healthy
        assert result.healthy_count == 1
        assert result.failing_checks == ("cache",)

    def test_all_failing(self) -> None:
        result = assess_health([_check("db", False), _check("cache", False)])
        assert not result.all_healthy
        assert result.healthy_count == 0
        assert set(result.failing_checks) == {"db", "cache"}


class TestAuthorizeFailover:
    def test_manual_always_authorized_even_if_unhealthy(self) -> None:
        assessment = assess_health([_check("db", False)])
        result = authorize_failover(FailoverKind.MANUAL, assessment)
        assert result.is_authorized
        assert result.refusal is None

    def test_manual_authorized_with_no_checks(self) -> None:
        assessment = assess_health([])
        result = authorize_failover(FailoverKind.MANUAL, assessment)
        assert result.is_authorized

    def test_failback_always_authorized(self) -> None:
        assessment = assess_health([_check("db", False)])
        result = authorize_failover(FailoverKind.FAILBACK, assessment)
        assert result.is_authorized

    def test_automatic_requires_checks(self) -> None:
        assessment = assess_health([])
        result = authorize_failover(FailoverKind.AUTOMATIC, assessment)
        assert not result.is_authorized
        assert result.refusal == AuthorizationRefusal.NO_HEALTH_CHECKS_RAN

    def test_automatic_requires_unanimous_health(self) -> None:
        assessment = assess_health([_check("db", True), _check("cache", False)])
        result = authorize_failover(FailoverKind.AUTOMATIC, assessment)
        assert not result.is_authorized
        assert result.refusal == AuthorizationRefusal.HEALTH_CHECKS_FAILING
        assert "cache" in result.detail

    def test_automatic_authorized_when_all_healthy(self) -> None:
        assessment = assess_health([_check("db", True), _check("cache", True)])
        result = authorize_failover(FailoverKind.AUTOMATIC, assessment)
        assert result.is_authorized
        assert result.refusal is None
