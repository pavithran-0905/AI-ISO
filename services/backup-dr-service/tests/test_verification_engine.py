"""Tests for app.verification.engine: checksum verification and sample selection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import VerificationStatus
from app.verification.engine import (
    VerifiableArchive,
    VerificationRefusal,
    compute_checksum,
    select_sample,
    verify_checksum,
)

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
MAX_AGE = NOW - timedelta(days=7)


class TestVerifyChecksum:
    def test_no_expected_checksum_is_skipped_not_passed(self) -> None:
        result = verify_checksum(expected=None, actual="abc123")
        assert result.status is VerificationStatus.SKIPPED
        assert result.refusal == VerificationRefusal.NO_EXPECTED_CHECKSUM

    def test_matching_checksum_passes(self) -> None:
        result = verify_checksum(expected="abc123", actual="abc123")
        assert result.status is VerificationStatus.PASSED
        assert result.refusal is None

    def test_case_insensitive_match(self) -> None:
        result = verify_checksum(expected="ABC123", actual="abc123")
        assert result.status is VerificationStatus.PASSED

    def test_mismatched_checksum_fails(self) -> None:
        result = verify_checksum(expected="abc123", actual="xyz789")
        assert result.status is VerificationStatus.FAILED
        assert "mismatch" in result.detail


class TestComputeChecksum:
    def test_sha256(self) -> None:
        result = compute_checksum(b"test data")
        assert len(result) == 64

    def test_unsupported_algorithm_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported checksum algorithm"):
            compute_checksum(b"data", algorithm="bogus")


def _archive(archive_id: str, last_verified_at: datetime | None) -> VerifiableArchive:
    return VerifiableArchive(archive_id=archive_id, last_verified_at=last_verified_at)


class TestSelectSample:
    def test_never_verified_always_included(self) -> None:
        archives = [_archive("never", None)]
        result = select_sample(archives, fraction=0.0, max_age=MAX_AGE)
        assert len(result) == 1
        assert result[0].archive_id == "never"

    def test_overdue_included_regardless_of_fraction(self) -> None:
        archives = [_archive("overdue", MAX_AGE - timedelta(days=1))]
        result = select_sample(archives, fraction=0.0, max_age=MAX_AGE)
        assert len(result) == 1

    def test_overdue_exactly_at_max_age_included(self) -> None:
        archives = [_archive("at-boundary", MAX_AGE)]
        result = select_sample(archives, fraction=0.0, max_age=MAX_AGE)
        assert len(result) == 1

    def test_routine_due_subject_to_fraction(self) -> None:
        archives = [
            _archive("routine-1", NOW - timedelta(days=1)),
            _archive("routine-2", NOW - timedelta(hours=12)),
        ]
        result = select_sample(archives, fraction=0.0, max_age=MAX_AGE)
        assert result == ()

    def test_full_fraction_includes_all_routine(self) -> None:
        archives = [
            _archive("routine-1", NOW - timedelta(days=1)),
            _archive("routine-2", NOW - timedelta(hours=12)),
        ]
        result = select_sample(archives, fraction=1.0, max_age=MAX_AGE)
        assert len(result) == 2

    def test_routine_sampled_oldest_verified_first(self) -> None:
        archives = [
            _archive("newer", NOW - timedelta(hours=1)),
            _archive("older", NOW - timedelta(hours=2)),
        ]
        result = select_sample(archives, fraction=0.5, max_age=MAX_AGE)
        assert len(result) == 1
        assert result[0].archive_id == "older"

    def test_no_duplicate_archives_in_result(self) -> None:
        archives = [_archive("a1", None)]
        result = select_sample(archives, fraction=1.0, max_age=MAX_AGE)
        assert len(result) == 1

    def test_invalid_fraction_below_zero_raises(self) -> None:
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            select_sample([], fraction=-0.1, max_age=MAX_AGE)

    def test_invalid_fraction_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            select_sample([], fraction=1.1, max_age=MAX_AGE)

    def test_empty_archives(self) -> None:
        assert select_sample([], fraction=0.5, max_age=MAX_AGE) == ()
