"""Tests for app.jobs.engine: job lifecycle transitions and retry
backoff."""

from __future__ import annotations

import pytest

from app.jobs.engine import (
    ALLOWED_TRANSITIONS,
    TransitionRefusal,
    compute_backoff_seconds,
    should_retry_job,
    validate_transition,
)
from app.models.enums import JobStatus


class TestValidateTransition:
    def test_queued_to_running_is_allowed(self) -> None:
        assert validate_transition(JobStatus.QUEUED, JobStatus.RUNNING).is_allowed

    def test_running_to_succeeded_is_allowed(self) -> None:
        assert validate_transition(JobStatus.RUNNING, JobStatus.SUCCEEDED).is_allowed

    def test_failed_to_retrying_is_allowed(self) -> None:
        assert validate_transition(JobStatus.FAILED, JobStatus.RETRYING).is_allowed

    def test_retrying_to_running_is_allowed(self) -> None:
        assert validate_transition(JobStatus.RETRYING, JobStatus.RUNNING).is_allowed

    def test_succeeded_is_terminal(self) -> None:
        result = validate_transition(JobStatus.SUCCEEDED, JobStatus.RUNNING)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_queued_to_succeeded_is_invalid(self) -> None:
        result = validate_transition(JobStatus.QUEUED, JobStatus.SUCCEEDED)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_every_state_has_a_table_entry(self) -> None:
        for status in JobStatus:
            assert status in ALLOWED_TRANSITIONS


class TestShouldRetryJob:
    def test_failed_below_max_should_retry(self) -> None:
        assert should_retry_job(JobStatus.FAILED, attempt_count=1, max_attempts=3).should_retry

    def test_failed_at_max_should_not_retry(self) -> None:
        assert not should_retry_job(JobStatus.FAILED, attempt_count=3, max_attempts=3).should_retry

    def test_succeeded_is_never_retried(self) -> None:
        assert not should_retry_job(
            JobStatus.SUCCEEDED, attempt_count=1, max_attempts=3
        ).should_retry

    def test_non_positive_max_attempts_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            should_retry_job(JobStatus.FAILED, attempt_count=0, max_attempts=0)


class TestComputeBackoffSeconds:
    def test_zero_attempts_is_base(self) -> None:
        assert compute_backoff_seconds(0, base_seconds=60) == 60.0

    def test_doubles_each_attempt(self) -> None:
        assert compute_backoff_seconds(1, base_seconds=60) == 120.0
        assert compute_backoff_seconds(2, base_seconds=60) == 240.0

    def test_negative_attempt_count_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_backoff_seconds(-1, base_seconds=60)

    def test_non_positive_base_seconds_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            compute_backoff_seconds(0, base_seconds=0)
