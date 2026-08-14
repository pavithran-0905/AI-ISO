"""Tests for app.governance.engine: tag, naming, and quota policy
evaluation."""

from __future__ import annotations

import pytest

from app.governance.engine import evaluate_naming_policy, evaluate_quota_policy, evaluate_tag_policy


class TestEvaluateTagPolicy:
    def test_all_required_present(self) -> None:
        result = evaluate_tag_policy(
            {"env": "prod", "owner": "team-a"}, required_keys=frozenset({"env"})
        )
        assert result.is_compliant

    def test_missing_key(self) -> None:
        result = evaluate_tag_policy({}, required_keys=frozenset({"env"}))
        assert not result.is_compliant
        assert "missing required tag: env" in result.violations

    def test_empty_value_counts_as_missing(self) -> None:
        result = evaluate_tag_policy({"env": "   "}, required_keys=frozenset({"env"}))
        assert not result.is_compliant


class TestEvaluateNamingPolicy:
    def test_matching_name(self) -> None:
        assert evaluate_naming_policy("prod-vm-01", pattern=r"prod-.*").is_compliant

    def test_non_matching_name(self) -> None:
        result = evaluate_naming_policy("dev-vm-01", pattern=r"prod-.*")
        assert not result.is_compliant
        assert result.violations


class TestEvaluateQuotaPolicy:
    def test_within_quota(self) -> None:
        assert evaluate_quota_policy(current_count=5, max_count=10).is_compliant

    def test_at_quota_is_compliant(self) -> None:
        assert evaluate_quota_policy(current_count=10, max_count=10).is_compliant

    def test_over_quota(self) -> None:
        result = evaluate_quota_policy(current_count=11, max_count=10)
        assert not result.is_compliant

    def test_negative_current_count_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            evaluate_quota_policy(current_count=-1, max_count=10)

    def test_non_positive_max_count_raises(self) -> None:
        with pytest.raises(ValueError, match="max_count"):
            evaluate_quota_policy(current_count=0, max_count=0)
