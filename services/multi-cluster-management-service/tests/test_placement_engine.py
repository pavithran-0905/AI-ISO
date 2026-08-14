"""Tests for app.placement.engine: affinity evaluation and candidate selection."""

from __future__ import annotations

from uuid import uuid4

from app.placement.engine import PlacementCandidate, evaluate_affinity, select_placement_candidates


class TestEvaluateAffinity:
    def test_no_rules_always_eligible(self) -> None:
        result = evaluate_affinity({}, required_labels={}, forbidden_labels={})
        assert result.is_eligible

    def test_required_label_present_matches(self) -> None:
        result = evaluate_affinity(
            {"env": "prod"}, required_labels={"env": "prod"}, forbidden_labels={}
        )
        assert result.is_eligible

    def test_required_label_missing_ineligible(self) -> None:
        result = evaluate_affinity({}, required_labels={"env": "prod"}, forbidden_labels={})
        assert not result.is_eligible
        assert result.unmet_requirements == ("env",)

    def test_required_label_wrong_value_ineligible(self) -> None:
        result = evaluate_affinity(
            {"env": "staging"}, required_labels={"env": "prod"}, forbidden_labels={}
        )
        assert not result.is_eligible
        assert result.unmet_requirements == ("env",)

    def test_forbidden_label_with_matching_value_ineligible(self) -> None:
        result = evaluate_affinity(
            {"risky": "true"}, required_labels={}, forbidden_labels={"risky": "true"}
        )
        assert not result.is_eligible
        assert result.violated_exclusions == ("risky",)

    def test_forbidden_label_different_value_still_eligible(self) -> None:
        """A forbidden key present with a *different* value does not
        violate the exclusion -- the rule names a specific value to
        avoid, not the key's mere existence."""
        result = evaluate_affinity(
            {"risky": "false"}, required_labels={}, forbidden_labels={"risky": "true"}
        )
        assert result.is_eligible

    def test_forbidden_label_absent_eligible(self) -> None:
        result = evaluate_affinity({}, required_labels={}, forbidden_labels={"risky": "true"})
        assert result.is_eligible


class TestSelectPlacementCandidates:
    def test_selects_only_eligible_clusters(self) -> None:
        c1 = PlacementCandidate(uuid4(), {"env": "prod"})
        c2 = PlacementCandidate(uuid4(), {"env": "staging"})
        c3 = PlacementCandidate(uuid4(), {"env": "prod", "risky": "true"})
        result = select_placement_candidates(
            [c1, c2, c3], required_labels={"env": "prod"}, forbidden_labels={"risky": "true"}
        )
        assert result == (c1.cluster_id,)

    def test_no_candidates_returns_empty(self) -> None:
        result = select_placement_candidates([], required_labels={}, forbidden_labels={})
        assert result == ()

    def test_preserves_input_order(self) -> None:
        c1 = PlacementCandidate(uuid4(), {"env": "prod"})
        c2 = PlacementCandidate(uuid4(), {"env": "prod"})
        result = select_placement_candidates(
            [c1, c2], required_labels={"env": "prod"}, forbidden_labels={}
        )
        assert result == (c1.cluster_id, c2.cluster_id)
