"""Tests for app.dr_plans.engine: recovery sequencing and compliance classification."""

from __future__ import annotations

from app.dr_plans.engine import SequencingRefusal, classify_compliance, sequence_recovery_groups
from app.models.enums import ComplianceStatus


class TestSequenceRecoveryGroups:
    def test_no_dependencies_alphabetical_order(self) -> None:
        result = sequence_recovery_groups(["c", "a", "b"], {})
        assert result.is_sequenced
        assert result.order == ("a", "b", "c")

    def test_simple_dependency_chain(self) -> None:
        result = sequence_recovery_groups(["api", "database"], {"api": ["database"]})
        assert result.is_sequenced
        assert result.order == ("database", "api")

    def test_diamond_dependency(self) -> None:
        groups = ["app", "cache", "database", "network"]
        deps = {
            "database": ["network"],
            "cache": ["network"],
            "app": ["database", "cache"],
        }
        result = sequence_recovery_groups(groups, deps)
        assert result.is_sequenced
        assert result.order.index("network") < result.order.index("database")
        assert result.order.index("network") < result.order.index("cache")
        assert result.order.index("database") < result.order.index("app")
        assert result.order.index("cache") < result.order.index("app")

    def test_cycle_detected(self) -> None:
        result = sequence_recovery_groups(["a", "b"], {"a": ["b"], "b": ["a"]})
        assert not result.is_sequenced
        assert result.refused == SequencingRefusal.CYCLE_DETECTED

    def test_self_dependency_is_cycle(self) -> None:
        result = sequence_recovery_groups(["a"], {"a": ["a"]})
        assert not result.is_sequenced
        assert result.refused == SequencingRefusal.CYCLE_DETECTED

    def test_unknown_dependency_key(self) -> None:
        result = sequence_recovery_groups(["a"], {"ghost": ["a"]})
        assert not result.is_sequenced
        assert result.refused == SequencingRefusal.UNKNOWN_DEPENDENCY

    def test_unknown_dependency_value(self) -> None:
        result = sequence_recovery_groups(["a"], {"a": ["ghost"]})
        assert not result.is_sequenced
        assert result.refused == SequencingRefusal.UNKNOWN_DEPENDENCY

    def test_declared_list_order_not_used(self) -> None:
        """The whole point of the engine: dependency wins over declaration order."""
        result = sequence_recovery_groups(["api", "database"], {"api": ["database"]})
        assert result.order == ("database", "api")

    def test_deterministic_across_dependency_dict_ordering(self) -> None:
        deps_a = {"x": ["y"], "z": []}
        deps_b = {"z": [], "x": ["y"]}
        result_a = sequence_recovery_groups(["x", "y", "z"], deps_a)
        result_b = sequence_recovery_groups(["x", "y", "z"], deps_b)
        assert result_a.order == result_b.order

    def test_empty_groups(self) -> None:
        result = sequence_recovery_groups([], {})
        assert result.is_sequenced
        assert result.order == ()


class TestClassifyCompliance:
    def test_never_measured(self) -> None:
        assert classify_compliance(target_minutes=60, achieved_minutes=None) is (
            ComplianceStatus.NOT_MEASURED
        )

    def test_within_target_is_met(self) -> None:
        assert classify_compliance(target_minutes=60, achieved_minutes=30.0) is (
            ComplianceStatus.MET
        )

    def test_exactly_at_target_is_met(self) -> None:
        assert classify_compliance(target_minutes=60, achieved_minutes=60.0) is (
            ComplianceStatus.MET
        )

    def test_over_target_is_violated(self) -> None:
        assert classify_compliance(target_minutes=60, achieved_minutes=90.0) is (
            ComplianceStatus.VIOLATED
        )

    def test_never_defaults_to_met_when_unmeasured(self) -> None:
        result = classify_compliance(target_minutes=0, achieved_minutes=None)
        assert result is not ComplianceStatus.MET
        assert result is ComplianceStatus.NOT_MEASURED
