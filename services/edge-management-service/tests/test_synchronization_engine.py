"""Tests for app.synchronization.engine: sync conflict resolution and
retry decisions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import ConflictResolutionStrategy as R
from app.models.enums import SyncStatus as S
from app.synchronization.engine import (
    ConflictWinner,
    is_sync_overdue,
    resolve_conflict,
    should_retry_sync,
)


class TestResolveConflict:
    def test_server_wins(self) -> None:
        now = datetime.now(UTC)
        winner = resolve_conflict(R.SERVER_WINS, server_updated_at=now, device_updated_at=now)
        assert winner == ConflictWinner.SERVER

    def test_device_wins(self) -> None:
        now = datetime.now(UTC)
        winner = resolve_conflict(R.DEVICE_WINS, server_updated_at=now, device_updated_at=now)
        assert winner == ConflictWinner.DEVICE

    def test_last_write_wins_picks_device_when_more_recent(self) -> None:
        now = datetime.now(UTC)
        winner = resolve_conflict(
            R.LAST_WRITE_WINS, server_updated_at=now - timedelta(minutes=5), device_updated_at=now
        )
        assert winner == ConflictWinner.DEVICE

    def test_last_write_wins_picks_server_when_more_recent(self) -> None:
        now = datetime.now(UTC)
        winner = resolve_conflict(
            R.LAST_WRITE_WINS, server_updated_at=now, device_updated_at=now - timedelta(minutes=5)
        )
        assert winner == ConflictWinner.SERVER

    def test_manual_never_resolves(self) -> None:
        now = datetime.now(UTC)
        winner = resolve_conflict(R.MANUAL, server_updated_at=now, device_updated_at=now)
        assert winner == ConflictWinner.UNRESOLVED

    def test_string_strategy_value_is_compared_safely(self) -> None:
        now = datetime.now(UTC)
        winner = resolve_conflict("server_wins", server_updated_at=now, device_updated_at=now)  # type: ignore[arg-type]
        assert winner == ConflictWinner.SERVER


class TestIsSyncOverdue:
    def test_never_synced_is_overdue(self) -> None:
        assert is_sync_overdue(None, now=datetime.now(UTC), threshold_minutes=60)

    def test_recently_synced_is_not_overdue(self) -> None:
        now = datetime.now(UTC)
        assert not is_sync_overdue(now - timedelta(minutes=10), now=now, threshold_minutes=60)

    def test_old_sync_is_overdue(self) -> None:
        now = datetime.now(UTC)
        assert is_sync_overdue(now - timedelta(minutes=90), now=now, threshold_minutes=60)


class TestShouldRetrySync:
    def test_failed_under_max_attempts_should_retry(self) -> None:
        decision = should_retry_sync(S.FAILED, attempt_count=1, max_attempts=5)
        assert decision.should_retry

    def test_failed_at_max_attempts_should_not_retry(self) -> None:
        decision = should_retry_sync(S.FAILED, attempt_count=5, max_attempts=5)
        assert not decision.should_retry

    def test_conflict_is_not_retryable(self) -> None:
        decision = should_retry_sync(S.CONFLICT, attempt_count=0, max_attempts=5)
        assert not decision.should_retry

    def test_completed_is_not_retryable(self) -> None:
        decision = should_retry_sync(S.COMPLETED, attempt_count=0, max_attempts=5)
        assert not decision.should_retry

    def test_non_positive_max_attempts_raises(self) -> None:
        with pytest.raises(ValueError, match="max_attempts"):
            should_retry_sync(S.FAILED, attempt_count=0, max_attempts=0)
