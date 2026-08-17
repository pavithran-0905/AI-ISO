"""Unit tests for every pure engine module -- the same checks the
hand-verification script already ran, formalized as pytest so they
gate CI, plus edge cases the script didn't cover."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.analytics.engine import average_duration_seconds, rollback_frequency, success_rate
from app.dependencies.engine import (
    classify_dependency_check,
    is_version_at_least,
    parse_semantic_version,
)
from app.deployment.engine import TransitionRefusal as JobTransitionRefusal
from app.deployment.engine import is_job_stuck
from app.deployment.engine import validate_transition as validate_job_transition
from app.installer.engine import TransitionRefusal as SessionTransitionRefusal
from app.installer.engine import validate_transition as validate_session_transition
from app.models.enums import CheckResultStatus, DeploymentJobStatus, InstallationSessionStatus
from app.preflight.engine import aggregate_check_results, is_ready
from app.rollback.engine import can_rollback_to
from app.secrets.engine import generate_credential, is_rotation_due, mask_for_display
from app.tls.engine import classify_certificate_status, generate_self_signed_certificate
from app.upgrade.engine import is_major_upgrade, is_upgrade_path_valid
from app.verification.engine import compute_verification_outcome, is_deployment_verified

NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)


class TestInstallerEngine:
    def test_pending_to_running(self) -> None:
        assert validate_session_transition(
            InstallationSessionStatus.PENDING, InstallationSessionStatus.RUNNING
        ).is_allowed

    def test_running_to_succeeded(self) -> None:
        assert validate_session_transition(
            InstallationSessionStatus.RUNNING, InstallationSessionStatus.SUCCEEDED
        ).is_allowed

    def test_succeeded_is_terminal(self) -> None:
        result = validate_session_transition(
            InstallationSessionStatus.SUCCEEDED, InstallationSessionStatus.RUNNING
        )
        assert not result.is_allowed
        assert result.refusal == SessionTransitionRefusal.TERMINAL_STATE

    def test_pending_to_succeeded_invalid(self) -> None:
        result = validate_session_transition(
            InstallationSessionStatus.PENDING, InstallationSessionStatus.SUCCEEDED
        )
        assert not result.is_allowed
        assert result.refusal == SessionTransitionRefusal.INVALID_TRANSITION


class TestDeploymentEngine:
    def test_pending_to_running(self) -> None:
        assert validate_job_transition(
            DeploymentJobStatus.PENDING, DeploymentJobStatus.RUNNING
        ).is_allowed

    def test_failed_is_terminal(self) -> None:
        result = validate_job_transition(DeploymentJobStatus.FAILED, DeploymentJobStatus.RUNNING)
        assert not result.is_allowed
        assert result.refusal == JobTransitionRefusal.TERMINAL_STATE

    def test_job_stuck_past_max_age(self) -> None:
        assert is_job_stuck(
            DeploymentJobStatus.RUNNING,
            started_at=NOW - timedelta(hours=5),
            now=NOW,
            max_age_hours=4,
        )

    def test_job_not_stuck_within_max_age(self) -> None:
        assert not is_job_stuck(
            DeploymentJobStatus.RUNNING,
            started_at=NOW - timedelta(hours=1),
            now=NOW,
            max_age_hours=4,
        )

    def test_job_not_stuck_when_not_running(self) -> None:
        assert not is_job_stuck(
            DeploymentJobStatus.PENDING, started_at=None, now=NOW, max_age_hours=4
        )


class TestPreflightEngine:
    def test_all_passed(self) -> None:
        assert (
            aggregate_check_results([CheckResultStatus.PASSED, CheckResultStatus.PASSED])
            == CheckResultStatus.PASSED
        )

    def test_warning_outranks_passed(self) -> None:
        assert (
            aggregate_check_results([CheckResultStatus.PASSED, CheckResultStatus.WARNING])
            == CheckResultStatus.WARNING
        )

    def test_failed_outranks_warning(self) -> None:
        assert (
            aggregate_check_results([CheckResultStatus.WARNING, CheckResultStatus.FAILED])
            == CheckResultStatus.FAILED
        )

    def test_empty_is_passed(self) -> None:
        assert aggregate_check_results([]) == CheckResultStatus.PASSED

    def test_is_ready_true_for_warning(self) -> None:
        assert is_ready(CheckResultStatus.WARNING)

    def test_is_ready_false_for_failed(self) -> None:
        assert not is_ready(CheckResultStatus.FAILED)


class TestDependenciesEngine:
    def test_parse_tolerates_v_prefix_and_suffix(self) -> None:
        assert parse_semantic_version("v1.2.3-beta").major == 1

    def test_parse_rejects_malformed(self) -> None:
        with pytest.raises(ValueError, match="not a valid"):
            parse_semantic_version("not-a-version")

    def test_is_version_at_least_true(self) -> None:
        assert is_version_at_least("1.5.0", "1.2.0")

    def test_is_version_at_least_false(self) -> None:
        assert not is_version_at_least("1.1.0", "1.2.0")

    def test_classify_missing_dependency(self) -> None:
        assert (
            classify_dependency_check(required_version="1.0.0", found_version="")
            == CheckResultStatus.FAILED
        )

    def test_classify_older_found(self) -> None:
        assert (
            classify_dependency_check(required_version="2.0.0", found_version="1.9.9")
            == CheckResultStatus.FAILED
        )

    def test_classify_newer_major_is_warning(self) -> None:
        assert (
            classify_dependency_check(required_version="1.0.0", found_version="2.0.0")
            == CheckResultStatus.WARNING
        )

    def test_classify_exact_match(self) -> None:
        assert (
            classify_dependency_check(required_version="1.2.3", found_version="1.2.3")
            == CheckResultStatus.PASSED
        )


class TestUpgradeEngine:
    def test_forward_path_valid(self) -> None:
        assert is_upgrade_path_valid(from_version="1.0.0", to_version="1.1.0")

    def test_backward_path_invalid(self) -> None:
        assert not is_upgrade_path_valid(from_version="1.1.0", to_version="1.0.0")

    def test_same_version_invalid(self) -> None:
        assert not is_upgrade_path_valid(from_version="1.0.0", to_version="1.0.0")

    def test_major_upgrade_detected(self) -> None:
        assert is_major_upgrade(from_version="1.9.0", to_version="2.0.0")

    def test_minor_upgrade_is_not_major(self) -> None:
        assert not is_major_upgrade(from_version="1.0.0", to_version="1.1.0")


class TestRollbackEngine:
    def test_rollback_to_known_older_version(self) -> None:
        assert can_rollback_to(
            current_version="2.0.0", target_version="1.5.0", available_versions=["1.5.0", "2.0.0"]
        )

    def test_rollback_to_unknown_version_refused(self) -> None:
        assert not can_rollback_to(
            current_version="2.0.0", target_version="1.5.0", available_versions=["2.0.0"]
        )

    def test_rollback_to_newer_version_refused(self) -> None:
        assert not can_rollback_to(
            current_version="1.0.0", target_version="2.0.0", available_versions=["1.0.0", "2.0.0"]
        )


class TestVerificationEngine:
    def test_outcome_reuses_preflight_aggregation(self) -> None:
        assert (
            compute_verification_outcome([CheckResultStatus.PASSED, CheckResultStatus.FAILED])
            == CheckResultStatus.FAILED
        )

    def test_deployment_verified_true(self) -> None:
        assert is_deployment_verified(CheckResultStatus.PASSED)

    def test_deployment_verified_false(self) -> None:
        assert not is_deployment_verified(CheckResultStatus.FAILED)


class TestTlsEngine:
    def test_generated_certificate_is_pem(self) -> None:
        generated = generate_self_signed_certificate(common_name="aiios.local", valid_days=365)
        assert generated.certificate_pem.startswith("-----BEGIN CERTIFICATE-----")
        assert generated.private_key_pem.startswith("-----BEGIN PRIVATE KEY-----")

    def test_classify_valid(self) -> None:
        status = classify_certificate_status(
            not_after=NOW + timedelta(days=100), now=NOW, warning_days=30
        )
        assert status.value == "valid"

    def test_classify_expiring(self) -> None:
        status = classify_certificate_status(
            not_after=NOW + timedelta(days=10), now=NOW, warning_days=30
        )
        assert status.value == "expiring"

    def test_classify_expired(self) -> None:
        status = classify_certificate_status(
            not_after=NOW - timedelta(days=1), now=NOW, warning_days=30
        )
        assert status.value == "expired"


class TestSecretsEngine:
    def test_generated_credential_has_entropy(self) -> None:
        assert len(generate_credential(32)) > 20

    def test_generated_credentials_are_unique(self) -> None:
        assert generate_credential(32) != generate_credential(32)

    def test_masking_hides_raw_value(self) -> None:
        credential = generate_credential(32)
        assert mask_for_display(credential) != credential

    def test_rotation_due_past_max_age(self) -> None:
        assert is_rotation_due(generated_at=NOW - timedelta(days=100), now=NOW, max_age_days=90)

    def test_rotation_not_due_within_max_age(self) -> None:
        assert not is_rotation_due(generated_at=NOW - timedelta(days=10), now=NOW, max_age_days=90)


class TestAnalyticsEngine:
    def test_success_rate(self) -> None:
        assert success_rate(8, 10) == pytest.approx(0.8)

    def test_success_rate_empty(self) -> None:
        assert success_rate(0, 0) == 0.0

    def test_average_duration(self) -> None:
        assert average_duration_seconds([10.0, 20.0, 30.0]) == pytest.approx(20.0)

    def test_average_duration_empty(self) -> None:
        assert average_duration_seconds([]) == 0.0

    def test_rollback_frequency(self) -> None:
        assert rollback_frequency(1, 4) == pytest.approx(0.25)

    def test_rollback_frequency_empty(self) -> None:
        assert rollback_frequency(0, 0) == 0.0
