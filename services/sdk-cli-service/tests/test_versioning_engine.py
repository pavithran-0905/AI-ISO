"""Tests for app.versioning.engine: semantic version parsing,
comparison, compatibility, and breaking-change detection."""

from __future__ import annotations

import pytest

from app.versioning.engine import (
    SemanticVersion,
    is_api_compatible,
    is_breaking_change,
    is_update_available,
    parse_version,
)


class TestParseVersion:
    def test_parses_valid_version(self) -> None:
        assert parse_version("1.2.3") == SemanticVersion(1, 2, 3)

    def test_string_comparison_would_be_wrong(self) -> None:
        # "9.0.0" < "10.0.0" as strings is False; as versions it's True.
        assert parse_version("9.0.0") < parse_version("10.0.0")

    def test_wrong_part_count_raises(self) -> None:
        with pytest.raises(ValueError, match="MAJOR\\.MINOR\\.PATCH"):
            parse_version("1.2")

    def test_non_numeric_part_raises(self) -> None:
        with pytest.raises(ValueError, match="MAJOR\\.MINOR\\.PATCH"):
            parse_version("1.2.a")

    def test_negative_part_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            parse_version("-1.2.3")


class TestIsBreakingChange:
    def test_major_bump_is_breaking(self) -> None:
        assert is_breaking_change("1.5.0", "2.0.0")

    def test_minor_bump_is_not_breaking(self) -> None:
        assert not is_breaking_change("1.5.0", "1.6.0")

    def test_patch_bump_is_not_breaking(self) -> None:
        assert not is_breaking_change("1.5.0", "1.5.1")

    def test_downgrade_is_not_breaking(self) -> None:
        assert not is_breaking_change("2.0.0", "1.0.0")


class TestIsUpdateAvailable:
    def test_newer_version_is_available(self) -> None:
        assert is_update_available("1.0.0", "1.1.0")

    def test_older_version_is_not_available(self) -> None:
        assert not is_update_available("1.1.0", "1.0.0")

    def test_same_version_is_not_available(self) -> None:
        assert not is_update_available("1.0.0", "1.0.0")


class TestIsApiCompatible:
    def test_at_or_above_minimum_is_compatible(self) -> None:
        assert is_api_compatible("2.0.0", minimum_api_version="1.5.0")
        assert is_api_compatible("1.5.0", minimum_api_version="1.5.0")

    def test_below_minimum_is_not_compatible(self) -> None:
        assert not is_api_compatible("1.0.0", minimum_api_version="1.5.0")
