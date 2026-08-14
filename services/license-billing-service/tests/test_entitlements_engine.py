"""Tests for app.entitlements.engine: feature limit checking."""

from __future__ import annotations

import pytest

from app.entitlements.engine import is_feature_entitled, is_within_limit


class TestIsWithinLimit:
    def test_none_limit_is_unlimited(self) -> None:
        assert is_within_limit(1_000_000, limit_value=None)

    def test_below_limit(self) -> None:
        assert is_within_limit(4, limit_value=5)

    def test_at_limit_is_not_within(self) -> None:
        assert not is_within_limit(5, limit_value=5)

    def test_negative_usage_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            is_within_limit(-1, limit_value=5)


class TestIsFeatureEntitled:
    def test_disabled_feature_is_never_entitled(self) -> None:
        assert not is_feature_entitled(is_enabled=False, limit_value=None, current_usage=0)

    def test_enabled_unlimited_is_entitled(self) -> None:
        assert is_feature_entitled(is_enabled=True, limit_value=None, current_usage=1_000_000)

    def test_enabled_within_limit_is_entitled(self) -> None:
        assert is_feature_entitled(is_enabled=True, limit_value=10, current_usage=5)

    def test_enabled_at_limit_is_not_entitled(self) -> None:
        assert not is_feature_entitled(is_enabled=True, limit_value=10, current_usage=10)
