"""Tests for :mod:`app.versioning.semver`.

Pure module. The lexical-sort and validator-agreement cases below are
regression tests for real defects, not hypotheticals.
"""

from __future__ import annotations

import pytest

from app.models.enums import VersionBump
from app.versioning.semver import (
    INITIAL_VERSION,
    VersionDiff,
    bump,
    compare_bodies,
    infer_bump,
    is_downgrade,
    is_upgrade,
    is_valid,
    next_version,
    sort_versions,
)

# ---------------------------------------------------------------------------
# bump
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "component", "expected"),
    [
        ("1.2.3", VersionBump.MAJOR, "2.0.0"),
        ("1.2.3", VersionBump.MINOR, "1.3.0"),
        ("1.2.3", VersionBump.PATCH, "1.2.4"),
        ("0.0.0", VersionBump.PATCH, "0.0.1"),
        ("9.9.9", VersionBump.MAJOR, "10.0.0"),
    ],
)
def test_bump(current: str, component: VersionBump, expected: str) -> None:
    assert bump(current, component) == expected


def test_major_bump_zeroes_minor_and_patch() -> None:
    """Otherwise 2.0.0 and 2.1.0 would be permanently unreachable and
    ordering would stop being total."""
    assert bump("1.5.7", VersionBump.MAJOR) == "2.0.0"


def test_minor_bump_zeroes_patch() -> None:
    assert bump("1.5.7", VersionBump.MINOR) == "1.6.0"


@pytest.mark.parametrize("bad", ["1.2", "1.2.3.4", "x.y.z", "", "1.2.x", "-1.0.0", "1.-2.3"])
def test_bump_refuses_malformed_versions(bad: str) -> None:
    with pytest.raises(ValueError):
        bump(bad, VersionBump.PATCH)


# ---------------------------------------------------------------------------
# next_version
# ---------------------------------------------------------------------------


def test_initial_version_is_one_zero_zero() -> None:
    """A prompt's first published revision is a real artefact other
    services resolve by name -- there is no 0.x pre-release phase."""
    assert INITIAL_VERSION == "1.0.0"


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_next_version_of_nothing_is_the_initial_version(empty: str | None) -> None:
    assert next_version(empty) == "1.0.0"


def test_next_version_defaults_to_a_patch_bump() -> None:
    assert next_version("2.4.9") == "2.4.10"


def test_next_version_honours_an_explicit_component() -> None:
    assert next_version("2.4.9", VersionBump.MINOR) == "2.5.0"


def test_next_version_refuses_a_malformed_current() -> None:
    with pytest.raises(ValueError):
        next_version("not-a-version")


# ---------------------------------------------------------------------------
# is_valid -- must agree with bump
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("1.2.3", True),
        ("0.0.0", True),
        ("10.20.30", True),
        ("1.2", False),
        ("1.2.3.4", False),
        ("x.y.z", False),
        ("", False),
        ("-1.0.0", False),
    ],
)
def test_is_valid(version: str, expected: bool) -> None:
    assert is_valid(version) is expected


@pytest.mark.parametrize(
    "version", ["1.2.3", "0.0.0", "10.20.30", "1.2", "1.2.3.4", "x.y.z", "", "-1.0.0"]
)
def test_is_valid_agrees_with_bump(version: str) -> None:
    """Regression test for a real defect.

    ``shared_core``'s own ``parse_version`` accepts a two-part
    ``"1.2"`` that everything here rejects, so validating against it
    let ``is_valid`` return True and then ``bump`` raise on the very
    next line. A validator that disagrees with the thing it validates
    for is worse than none.
    """
    try:
        bump(version, VersionBump.PATCH)
        bumpable = True
    except ValueError:
        bumpable = False
    assert is_valid(version) is bumpable


# ---------------------------------------------------------------------------
# infer_bump
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("from_version", "to_version", "expected"),
    [
        ("1.2.3", "2.0.0", VersionBump.MAJOR),
        ("1.2.3", "1.3.0", VersionBump.MINOR),
        ("1.2.3", "1.2.4", VersionBump.PATCH),
        ("1.2.3", "1.2.3", None),
        ("2.0.0", "1.9.9", VersionBump.MAJOR),
    ],
)
def test_infer_bump(from_version: str, to_version: str, expected: VersionBump | None) -> None:
    assert infer_bump(from_version, to_version) == expected


def test_infer_bump_refuses_malformed_input() -> None:
    with pytest.raises(ValueError):
        infer_bump("1.2.3", "bad")


# ---------------------------------------------------------------------------
# sort_versions -- the lexical trap
# ---------------------------------------------------------------------------


def test_sort_is_numeric_not_lexical() -> None:
    """As strings, "10.0.0" sorts BEFORE "9.0.0", which would silently
    make a tenth major version look older than the ninth."""
    assert sort_versions(["9.0.0", "10.0.0", "1.0.0"]) == ["1.0.0", "9.0.0", "10.0.0"]


def test_sort_orders_every_component_numerically() -> None:
    assert sort_versions(["1.10.0", "1.9.0", "1.9.10", "1.9.2"]) == [
        "1.9.0",
        "1.9.2",
        "1.9.10",
        "1.10.0",
    ]


def test_sort_of_an_empty_list() -> None:
    assert sort_versions([]) == []


def test_sort_refuses_a_malformed_entry() -> None:
    with pytest.raises(ValueError):
        sort_versions(["1.0.0", "oops"])


def test_highest_version_is_the_last_after_sorting() -> None:
    """The property ``add_version`` depends on: bump from the HIGHEST,
    not the currently-live, revision."""
    assert sort_versions(["1.0.0", "1.1.0", "1.0.1"])[-1] == "1.1.0"


# ---------------------------------------------------------------------------
# is_upgrade / is_downgrade (reused from shared_core, re-exported)
# ---------------------------------------------------------------------------


def test_is_upgrade() -> None:
    assert is_upgrade("1.0.0", "1.1.0") is True
    assert is_upgrade("1.1.0", "1.0.0") is False


def test_is_downgrade() -> None:
    assert is_downgrade("1.1.0", "1.0.0") is True
    assert is_downgrade("1.0.0", "1.1.0") is False


# ---------------------------------------------------------------------------
# compare_bodies
# ---------------------------------------------------------------------------


def test_diff_reports_added_and_removed_lines() -> None:
    diff = compare_bodies("1.0.0", "1.1.0", "Do A.\nDo B.", "Do A.\nDo C.")
    assert diff.added_lines == ("Do C.",)
    assert diff.removed_lines == ("Do B.",)


def test_diff_of_identical_bodies() -> None:
    diff = compare_bodies("1.0.0", "1.0.1", "Same text", "Same text")
    assert diff.is_identical is True
    assert diff.added_lines == ()
    assert diff.removed_lines == ()


def test_diff_ignores_reordering() -> None:
    """Set-based on purpose: a prompt reviewer wants to know which
    instructions appeared and disappeared, not which line numbers moved
    when a paragraph was reordered.
    """
    diff = compare_bodies("1.0.0", "1.0.1", "Do A.\nDo B.", "Do B.\nDo A.")
    assert diff.is_identical is True


def test_diff_ignores_blank_lines_and_indentation() -> None:
    diff = compare_bodies("1.0.0", "1.0.1", "Do A.\n\n  Do B.  ", "Do A.\nDo B.")
    assert diff.is_identical is True


def test_diff_records_direction_and_bump() -> None:
    diff = compare_bodies("1.0.0", "1.1.0", "x", "y")
    assert isinstance(diff, VersionDiff)
    assert diff.is_forward is True
    assert diff.bump == VersionBump.MINOR


def test_diff_of_a_rollback_is_not_forward() -> None:
    diff = compare_bodies("1.1.0", "1.0.0", "y", "x")
    assert diff.is_forward is False


def test_diff_carries_the_token_delta_it_is_given() -> None:
    assert compare_bodies("1.0.0", "1.0.1", "a", "b", token_delta=-12).token_delta == -12


def test_diff_refuses_malformed_versions() -> None:
    with pytest.raises(ValueError):
        compare_bodies("1.0.0", "bad", "a", "b")
