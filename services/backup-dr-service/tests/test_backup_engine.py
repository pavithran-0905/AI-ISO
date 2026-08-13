"""Tests for app.backup.engine: chain validation, checksums, dedup, scheduling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.backup.engine import (
    ChainBreakReason,
    ChainLink,
    DedupeOutcome,
    compute_checksum,
    compute_next_run,
    detect_duplicate,
    validate_chain,
)
from app.models.enums import BackupJobStatus, BackupType

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def _link(
    job_id: str,
    *,
    backup_type: BackupType = BackupType.INCREMENTAL,
    parent_job_id: str | None = None,
    status: BackupJobStatus = BackupJobStatus.COMPLETED,
) -> ChainLink:
    return ChainLink(
        job_id=job_id,
        backup_type=backup_type,
        parent_job_id=parent_job_id,
        status=status,
        completed_at=NOW,
    )


class TestValidateChain:
    def test_full_backup_is_its_own_chain(self) -> None:
        jobs = [_link("full-1", backup_type=BackupType.FULL, parent_job_id=None)]
        result = validate_chain("full-1", jobs)
        assert result.is_intact
        assert result.chain == ("full-1",)
        assert result.break_reason is None

    def test_snapshot_is_its_own_chain(self) -> None:
        jobs = [_link("snap-1", backup_type=BackupType.SNAPSHOT, parent_job_id=None)]
        result = validate_chain("snap-1", jobs)
        assert result.is_intact
        assert result.chain == ("snap-1",)

    def test_continuous_is_its_own_chain(self) -> None:
        jobs = [_link("cont-1", backup_type=BackupType.CONTINUOUS, parent_job_id=None)]
        result = validate_chain("cont-1", jobs)
        assert result.is_intact

    def test_incremental_chain_to_full_intact(self) -> None:
        jobs = [
            _link("full-1", backup_type=BackupType.FULL, parent_job_id=None),
            _link("inc-1", parent_job_id="full-1"),
            _link("inc-2", parent_job_id="inc-1"),
        ]
        result = validate_chain("inc-2", jobs)
        assert result.is_intact
        assert result.chain == ("full-1", "inc-1", "inc-2")

    def test_missing_target_job(self) -> None:
        result = validate_chain("does-not-exist", [])
        assert not result.is_intact
        assert result.break_reason == ChainBreakReason.MISSING_PARENT
        assert result.broken_at_job_id == "does-not-exist"

    def test_missing_parent(self) -> None:
        jobs = [_link("inc-1", parent_job_id="ghost-parent")]
        result = validate_chain("inc-1", jobs)
        assert not result.is_intact
        assert result.break_reason == ChainBreakReason.MISSING_PARENT
        assert result.broken_at_job_id == "ghost-parent"

    def test_root_not_full(self) -> None:
        jobs = [_link("inc-1", parent_job_id=None)]
        result = validate_chain("inc-1", jobs)
        assert not result.is_intact
        assert result.break_reason == ChainBreakReason.ROOT_NOT_FULL
        assert result.broken_at_job_id == "inc-1"

    def test_parent_not_complete(self) -> None:
        jobs = [
            _link("full-1", backup_type=BackupType.FULL, status=BackupJobStatus.FAILED),
            _link("inc-1", parent_job_id="full-1"),
        ]
        result = validate_chain("inc-1", jobs)
        assert not result.is_intact
        assert result.break_reason == ChainBreakReason.PARENT_NOT_COMPLETE
        assert result.broken_at_job_id == "full-1"

    def test_target_itself_not_complete(self) -> None:
        jobs = [_link("inc-1", status=BackupJobStatus.RUNNING, parent_job_id="full-1")]
        result = validate_chain("inc-1", jobs)
        assert not result.is_intact
        assert result.break_reason == ChainBreakReason.PARENT_NOT_COMPLETE
        assert result.broken_at_job_id == "inc-1"

    def test_verified_status_counts_as_complete(self) -> None:
        jobs = [
            _link(
                "full-1",
                backup_type=BackupType.FULL,
                status=BackupJobStatus.VERIFIED,
            ),
        ]
        result = validate_chain("full-1", jobs)
        assert result.is_intact

    def test_cycle_detected(self) -> None:
        jobs = [
            _link("a", parent_job_id="b"),
            _link("b", parent_job_id="a"),
        ]
        result = validate_chain("a", jobs)
        assert not result.is_intact
        assert result.break_reason == ChainBreakReason.CYCLE_DETECTED

    def test_differential_chain_intact(self) -> None:
        jobs = [
            _link("full-1", backup_type=BackupType.FULL, parent_job_id=None),
            _link("diff-1", backup_type=BackupType.DIFFERENTIAL, parent_job_id="full-1"),
        ]
        result = validate_chain("diff-1", jobs)
        assert result.is_intact
        assert result.chain == ("full-1", "diff-1")


class TestComputeChecksum:
    def test_sha256_default(self) -> None:
        result = compute_checksum(b"hello world")
        assert result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

    def test_sha512(self) -> None:
        result = compute_checksum(b"data", algorithm="sha512")
        assert len(result) == 128

    def test_deterministic(self) -> None:
        assert compute_checksum(b"same data") == compute_checksum(b"same data")

    def test_different_data_different_checksum(self) -> None:
        assert compute_checksum(b"a") != compute_checksum(b"b")

    def test_unsupported_algorithm_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported checksum algorithm"):
            compute_checksum(b"data", algorithm="not-a-real-algorithm")


class TestDetectDuplicate:
    def test_no_existing_is_not_duplicate(self) -> None:
        result = detect_duplicate("abc123", 1024, [])
        assert result == DedupeOutcome(is_duplicate=False, duplicate_of_job_id=None)

    def test_matching_checksum_and_size_is_duplicate(self) -> None:
        existing = [("job-1", "abc123", 1024)]
        result = detect_duplicate("abc123", 1024, existing)
        assert result.is_duplicate
        assert result.duplicate_of_job_id == "job-1"

    def test_matching_checksum_different_size_is_not_duplicate(self) -> None:
        existing = [("job-1", "abc123", 1024)]
        result = detect_duplicate("abc123", 2048, existing)
        assert not result.is_duplicate

    def test_different_checksum_matching_size_is_not_duplicate(self) -> None:
        existing = [("job-1", "abc123", 1024)]
        result = detect_duplicate("xyz789", 1024, existing)
        assert not result.is_duplicate

    def test_first_match_wins_among_multiple(self) -> None:
        existing = [("job-1", "abc123", 1024), ("job-2", "abc123", 1024)]
        result = detect_duplicate("abc123", 1024, existing)
        assert result.duplicate_of_job_id == "job-1"


class TestComputeNextRun:
    def test_no_prior_run_fires_immediately(self) -> None:
        result = compute_next_run("daily", last_run_at=None, now=NOW)
        assert result == NOW

    def test_hourly_interval_catches_up_when_next_run_still_in_past(self) -> None:
        last_run = NOW - timedelta(hours=2)
        result = compute_next_run("hourly", last_run_at=last_run, now=NOW)
        assert result == NOW + timedelta(hours=1)

    def test_hourly_interval_keeps_future_next_run(self) -> None:
        last_run = NOW - timedelta(minutes=30)
        result = compute_next_run("hourly", last_run_at=last_run, now=NOW)
        assert result == last_run + timedelta(hours=1)

    def test_daily_interval(self) -> None:
        last_run = NOW - timedelta(hours=1)
        result = compute_next_run("daily", last_run_at=last_run, now=NOW)
        assert result == last_run + timedelta(days=1)

    def test_weekly_interval(self) -> None:
        last_run = NOW - timedelta(days=1)
        result = compute_next_run("weekly", last_run_at=last_run, now=NOW)
        assert result == last_run + timedelta(days=7)

    def test_monthly_interval(self) -> None:
        last_run = NOW - timedelta(days=1)
        result = compute_next_run("monthly", last_run_at=last_run, now=NOW)
        assert result == last_run + timedelta(days=30)

    def test_backlogged_schedule_catches_up_to_now_plus_interval(self) -> None:
        last_run = NOW - timedelta(days=10)
        result = compute_next_run("daily", last_run_at=last_run, now=NOW)
        assert result == NOW + timedelta(days=1)

    def test_custom_cron_raises(self) -> None:
        with pytest.raises(ValueError, match="does not evaluate cron"):
            compute_next_run("custom_cron", last_run_at=None, now=NOW)

    def test_unknown_frequency_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown schedule frequency"):
            compute_next_run("fortnightly", last_run_at=None, now=NOW)
