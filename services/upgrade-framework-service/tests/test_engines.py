"""Unit tests for every pure engine module -- the same checks the
hand-verification script already ran, formalized as pytest so they
gate CI, plus edge cases the script didn't cover."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.analytics.engine import (
    average_duration_seconds,
    channel_adoption,
    rollback_rate,
    success_rate,
)
from app.compatibility.engine import classify_compatibility, parse_semantic_version
from app.dependencies.engine import classify_dependency_check
from app.fleet.engine import plan_waves
from app.health.engine import compute_health_score, is_healthy_enough
from app.migrations.engine import plan_rollback_order
from app.models.enums import CheckResultStatus, MigrationType, UpgradeJobStatus
from app.rollback.engine import can_rollback_to
from app.simulation.engine import assess_risk, estimate_duration_seconds
from app.upgrade.engine import TransitionRefusal, is_job_stuck, validate_transition
from app.verification.engine import aggregate_check_results, is_health_gate_passed

NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)


class TestUpgradeEngine:
    def test_pending_to_running(self) -> None:
        assert validate_transition(UpgradeJobStatus.PENDING, UpgradeJobStatus.RUNNING).is_allowed

    def test_failed_is_terminal(self) -> None:
        result = validate_transition(UpgradeJobStatus.FAILED, UpgradeJobStatus.RUNNING)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_pending_to_succeeded_invalid(self) -> None:
        result = validate_transition(UpgradeJobStatus.PENDING, UpgradeJobStatus.SUCCEEDED)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_job_stuck_past_max_age(self) -> None:
        assert is_job_stuck(
            UpgradeJobStatus.RUNNING, started_at=NOW - timedelta(hours=5), now=NOW, max_age_hours=4
        )

    def test_job_not_stuck_within_max_age(self) -> None:
        assert not is_job_stuck(
            UpgradeJobStatus.RUNNING, started_at=NOW - timedelta(hours=1), now=NOW, max_age_hours=4
        )

    def test_job_not_stuck_when_pending(self) -> None:
        assert not is_job_stuck(UpgradeJobStatus.PENDING, started_at=None, now=NOW, max_age_hours=4)


class TestCompatibilityEngine:
    def test_parse_tolerates_v_prefix_and_suffix(self) -> None:
        assert parse_semantic_version("v1.2.3-beta").major == 1

    def test_parse_rejects_malformed(self) -> None:
        with pytest.raises(ValueError, match="not a valid"):
            parse_semantic_version("not-a-version")

    def test_classify_forward_move_passed(self) -> None:
        assert (
            classify_compatibility(from_version="1.0.0", to_version="1.1.0")
            == CheckResultStatus.PASSED
        )

    def test_classify_major_boundary_warning(self) -> None:
        assert (
            classify_compatibility(from_version="1.9.0", to_version="2.0.0")
            == CheckResultStatus.WARNING
        )

    def test_classify_downgrade_failed(self) -> None:
        assert (
            classify_compatibility(from_version="2.0.0", to_version="1.0.0")
            == CheckResultStatus.FAILED
        )

    def test_classify_no_op_failed(self) -> None:
        assert (
            classify_compatibility(from_version="1.0.0", to_version="1.0.0")
            == CheckResultStatus.FAILED
        )


class TestDependenciesEngine:
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

    def test_classify_newer_major_warning(self) -> None:
        assert (
            classify_dependency_check(required_version="1.0.0", found_version="2.0.0")
            == CheckResultStatus.WARNING
        )

    def test_classify_exact_match(self) -> None:
        assert (
            classify_dependency_check(required_version="1.2.3", found_version="1.2.3")
            == CheckResultStatus.PASSED
        )


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


class TestSimulationEngine:
    def test_risk_high_on_any_failed(self) -> None:
        assert assess_risk([CheckResultStatus.PASSED, CheckResultStatus.FAILED]) == "high"

    def test_risk_medium_on_warning_only(self) -> None:
        assert assess_risk([CheckResultStatus.PASSED, CheckResultStatus.WARNING]) == "medium"

    def test_risk_low_on_all_passed(self) -> None:
        assert assess_risk([CheckResultStatus.PASSED]) == "low"

    def test_risk_low_on_empty(self) -> None:
        assert assess_risk([]) == "low"

    def test_duration_estimate(self) -> None:
        assert estimate_duration_seconds(target_count=10, seconds_per_target=5.0) == 50.0

    def test_duration_estimate_zero_targets(self) -> None:
        assert estimate_duration_seconds(target_count=0, seconds_per_target=5.0) == 0.0


class TestHealthEngine:
    def test_score_all_passed(self) -> None:
        assert compute_health_score(passed=10, warning=0, failed=0) == 1.0

    def test_score_all_failed(self) -> None:
        assert compute_health_score(passed=0, warning=0, failed=10) == 0.0

    def test_score_mixed(self) -> None:
        assert compute_health_score(passed=5, warning=2, failed=3) == pytest.approx(0.6)

    def test_score_vacuous(self) -> None:
        assert compute_health_score(passed=0, warning=0, failed=0) == 1.0

    def test_healthy_enough_true(self) -> None:
        assert is_healthy_enough(0.9, threshold=0.8)

    def test_healthy_enough_false(self) -> None:
        assert not is_healthy_enough(0.7, threshold=0.8)


class TestVerificationEngine:
    def test_aggregate_failed_outranks_warning(self) -> None:
        assert (
            aggregate_check_results([CheckResultStatus.WARNING, CheckResultStatus.FAILED])
            == CheckResultStatus.FAILED
        )

    def test_aggregate_empty_is_passed(self) -> None:
        assert aggregate_check_results([]) == CheckResultStatus.PASSED

    def test_health_gate_passed_true_for_warning(self) -> None:
        assert is_health_gate_passed(CheckResultStatus.WARNING)

    def test_health_gate_passed_false_for_failed(self) -> None:
        assert not is_health_gate_passed(CheckResultStatus.FAILED)


class TestMigrationsEngine:
    def test_rollback_order_is_reversed(self) -> None:
        order = plan_rollback_order(
            [MigrationType.DATABASE_SCHEMA, MigrationType.CONFIGURATION, MigrationType.PLUGIN]
        )
        assert order == [
            MigrationType.PLUGIN,
            MigrationType.CONFIGURATION,
            MigrationType.DATABASE_SCHEMA,
        ]

    def test_rollback_order_dedups_keeping_last_application_first(self) -> None:
        order = plan_rollback_order(
            [MigrationType.CONFIGURATION, MigrationType.PLUGIN, MigrationType.CONFIGURATION]
        )
        assert order == [MigrationType.CONFIGURATION, MigrationType.PLUGIN]

    def test_empty_applied_list(self) -> None:
        assert plan_rollback_order([]) == []


class TestFleetEngine:
    def test_waves_chunked_correctly(self) -> None:
        waves = plan_waves(["a", "b", "c", "d", "e"], wave_size=2)
        assert waves == [["a", "b"], ["c", "d"], ["e"]]

    def test_wave_size_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            plan_waves(["a"], wave_size=0)

    def test_empty_targets(self) -> None:
        assert plan_waves([], wave_size=3) == []


class TestAnalyticsEngine:
    def test_success_rate(self) -> None:
        assert success_rate(8, 10) == pytest.approx(0.8)

    def test_success_rate_empty(self) -> None:
        assert success_rate(0, 0) == 0.0

    def test_average_duration(self) -> None:
        assert average_duration_seconds([10.0, 20.0, 30.0]) == pytest.approx(20.0)

    def test_rollback_rate(self) -> None:
        assert rollback_rate(1, 4) == pytest.approx(0.25)

    def test_rollback_rate_empty(self) -> None:
        assert rollback_rate(0, 0) == 0.0

    def test_channel_adoption_normalized(self) -> None:
        assert channel_adoption({"stable": 80, "beta": 20}) == {
            "stable": pytest.approx(0.8),
            "beta": pytest.approx(0.2),
        }

    def test_channel_adoption_empty_activity(self) -> None:
        assert channel_adoption({"stable": 0}) == {"stable": 0.0}
