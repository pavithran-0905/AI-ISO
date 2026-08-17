"""Unit tests for every pure engine module -- the same checks the
hand-verification script already ran, formalized as pytest so they
gate CI, plus edge cases the script didn't cover."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.analytics.engine import hardening_score, is_production_ready, production_readiness_score
from app.certificates.engine import is_expired as cert_is_expired
from app.certificates.engine import is_expiring_soon
from app.certification.engine import compute_risk_score, should_grant
from app.certification.engine import is_expired as certification_is_expired
from app.compliance.engine import compliance_rate, is_compliant_overall
from app.disaster_recovery.engine import rpo_met, rto_met
from app.hardening.engine import TransitionRefusal, is_job_stuck, validate_transition
from app.models.enums import FindingSeverity, HardeningRunStatus, RuntimeProtectionEventType
from app.operational_readiness.engine import readiness_rate
from app.runtime_protection.engine import is_critical_event
from app.security.engine import classify_risk_score, is_critical
from app.vulnerability.engine import is_remediation_overdue, sla_days_for

NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)


class TestHardeningEngine:
    def test_pending_to_running(self) -> None:
        assert validate_transition(
            HardeningRunStatus.PENDING, HardeningRunStatus.RUNNING
        ).is_allowed

    def test_succeeded_is_terminal(self) -> None:
        result = validate_transition(HardeningRunStatus.SUCCEEDED, HardeningRunStatus.RUNNING)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_invalid_transition(self) -> None:
        result = validate_transition(HardeningRunStatus.PENDING, HardeningRunStatus.SUCCEEDED)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_job_stuck_past_max_age(self) -> None:
        assert is_job_stuck(
            HardeningRunStatus.RUNNING,
            started_at=NOW - timedelta(hours=5),
            now=NOW,
            max_age_hours=4,
        )

    def test_job_not_stuck_within_max_age(self) -> None:
        assert not is_job_stuck(
            HardeningRunStatus.RUNNING,
            started_at=NOW - timedelta(hours=1),
            now=NOW,
            max_age_hours=4,
        )

    def test_job_not_stuck_when_pending(self) -> None:
        assert not is_job_stuck(
            HardeningRunStatus.PENDING, started_at=None, now=NOW, max_age_hours=4
        )


class TestSecurityEngine:
    def test_risk_score_low(self) -> None:
        assert classify_risk_score(10.0) == FindingSeverity.LOW

    def test_risk_score_medium(self) -> None:
        assert classify_risk_score(30.0) == FindingSeverity.MEDIUM

    def test_risk_score_high(self) -> None:
        assert classify_risk_score(60.0) == FindingSeverity.HIGH

    def test_risk_score_critical(self) -> None:
        assert classify_risk_score(90.0) == FindingSeverity.CRITICAL

    def test_is_critical_true(self) -> None:
        assert is_critical(FindingSeverity.CRITICAL)

    def test_is_critical_false(self) -> None:
        assert not is_critical(FindingSeverity.HIGH)


class TestVulnerabilityEngine:
    def test_sla_critical_shortest(self) -> None:
        assert sla_days_for(FindingSeverity.CRITICAL) < sla_days_for(FindingSeverity.LOW)

    def test_overdue_critical(self) -> None:
        assert is_remediation_overdue(
            detected_at=NOW - timedelta(days=10), now=NOW, severity=FindingSeverity.CRITICAL
        )

    def test_not_overdue_critical(self) -> None:
        assert not is_remediation_overdue(
            detected_at=NOW - timedelta(days=1), now=NOW, severity=FindingSeverity.CRITICAL
        )


class TestComplianceEngine:
    def test_compliance_rate_basic(self) -> None:
        assert compliance_rate(9, 10) == 0.9

    def test_compliance_rate_vacuous(self) -> None:
        assert compliance_rate(0, 0) == 1.0

    def test_is_compliant_overall_true(self) -> None:
        assert is_compliant_overall(1.0)

    def test_is_compliant_overall_false(self) -> None:
        assert not is_compliant_overall(0.9)


class TestCertificationEngine:
    def test_risk_score_zero_when_perfect(self) -> None:
        assert (
            compute_risk_score(hardening_rate=1.0, compliance_rate=1.0, readiness_rate=1.0) == 0.0
        )

    def test_risk_score_high_when_poor(self) -> None:
        assert (
            compute_risk_score(hardening_rate=0.0, compliance_rate=0.0, readiness_rate=0.0) == 100.0
        )

    def test_should_grant_true(self) -> None:
        assert should_grant(20.0, threshold=50.0)

    def test_should_grant_false(self) -> None:
        assert not should_grant(80.0, threshold=50.0)

    def test_certification_not_expired_no_date(self) -> None:
        assert not certification_is_expired(expires_at=None, now=NOW)

    def test_certification_expired(self) -> None:
        assert certification_is_expired(expires_at=NOW - timedelta(days=1), now=NOW)

    def test_certification_not_expired_future(self) -> None:
        assert not certification_is_expired(expires_at=NOW + timedelta(days=1), now=NOW)


class TestOperationalReadinessEngine:
    def test_readiness_rate_basic(self) -> None:
        assert readiness_rate(8, 10) == 0.8

    def test_readiness_rate_honest_zero(self) -> None:
        assert readiness_rate(0, 0) == 0.0


class TestDisasterRecoveryEngine:
    def test_rto_met(self) -> None:
        assert rto_met(actual_recovery_seconds=30.0, target_rto_seconds=60.0)

    def test_rto_not_met(self) -> None:
        assert not rto_met(actual_recovery_seconds=90.0, target_rto_seconds=60.0)

    def test_rpo_met(self) -> None:
        assert rpo_met(actual_data_loss_seconds=5.0, target_rpo_seconds=10.0)

    def test_rpo_not_met(self) -> None:
        assert not rpo_met(actual_data_loss_seconds=15.0, target_rpo_seconds=10.0)


class TestCertificatesEngine:
    def test_expiring_soon(self) -> None:
        assert is_expiring_soon(expires_at=NOW + timedelta(days=10), now=NOW, warning_days=30)

    def test_not_expiring_soon(self) -> None:
        assert not is_expiring_soon(expires_at=NOW + timedelta(days=60), now=NOW, warning_days=30)

    def test_cert_expired(self) -> None:
        assert cert_is_expired(expires_at=NOW - timedelta(days=1), now=NOW)

    def test_cert_not_expired(self) -> None:
        assert not cert_is_expired(expires_at=NOW + timedelta(days=1), now=NOW)


class TestRuntimeProtectionEngine:
    def test_critical_severity_is_critical_event(self) -> None:
        assert is_critical_event(
            event_type=RuntimeProtectionEventType.ANOMALY, severity=FindingSeverity.CRITICAL
        )

    def test_privilege_escalation_always_critical(self) -> None:
        assert is_critical_event(
            event_type=RuntimeProtectionEventType.PRIVILEGE_ESCALATION, severity=FindingSeverity.LOW
        )

    def test_threat_detection_always_critical(self) -> None:
        assert is_critical_event(
            event_type=RuntimeProtectionEventType.THREAT_DETECTION, severity=FindingSeverity.LOW
        )

    def test_anomaly_low_not_critical(self) -> None:
        assert not is_critical_event(
            event_type=RuntimeProtectionEventType.ANOMALY, severity=FindingSeverity.LOW
        )


class TestAnalyticsEngine:
    def test_hardening_score_basic(self) -> None:
        assert hardening_score(8, 10) == 0.8

    def test_hardening_score_honest_zero(self) -> None:
        assert hardening_score(0, 0) == 0.0

    def test_production_readiness_score_perfect(self) -> None:
        score = production_readiness_score(
            hardening_rate=1.0, compliance_rate=1.0, operational_readiness_rate=1.0, dr_rate=1.0
        )
        assert score == 1.0

    def test_is_production_ready_true(self) -> None:
        assert is_production_ready(0.9, threshold=0.8)

    def test_is_production_ready_false(self) -> None:
        assert not is_production_ready(0.7, threshold=0.8)
