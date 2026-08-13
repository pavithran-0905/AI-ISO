"""Tests for app.snapshots.engine: expiration, quota enforcement, validation backlog."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.snapshots.engine import (
    SnapshotRecord,
    enforce_quota,
    expired_snapshots,
    is_expired,
    validation_backlog,
)

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def _snapshot(
    snapshot_id: str,
    created_at: datetime,
    *,
    expires_at: datetime | None = None,
    is_validated: bool = True,
) -> SnapshotRecord:
    return SnapshotRecord(
        snapshot_id=snapshot_id,
        target_id="target-1",
        created_at_source=created_at,
        expires_at=expires_at,
        is_validated=is_validated,
    )


class TestIsExpired:
    def test_no_expiry_never_expires(self) -> None:
        snapshot = _snapshot("s1", NOW - timedelta(days=100), expires_at=None)
        assert not is_expired(snapshot, now=NOW)

    def test_expiry_in_future_not_expired(self) -> None:
        snapshot = _snapshot("s1", NOW, expires_at=NOW + timedelta(hours=1))
        assert not is_expired(snapshot, now=NOW)

    def test_expiry_exactly_now_is_expired(self) -> None:
        snapshot = _snapshot("s1", NOW - timedelta(hours=1), expires_at=NOW)
        assert is_expired(snapshot, now=NOW)

    def test_expiry_in_past_is_expired(self) -> None:
        snapshot = _snapshot("s1", NOW - timedelta(days=1), expires_at=NOW - timedelta(hours=1))
        assert is_expired(snapshot, now=NOW)


class TestExpiredSnapshots:
    def test_filters_only_expired(self) -> None:
        snapshots = [
            _snapshot("expired", NOW - timedelta(days=1), expires_at=NOW - timedelta(hours=1)),
            _snapshot("fresh", NOW, expires_at=NOW + timedelta(hours=1)),
            _snapshot("forever", NOW, expires_at=None),
        ]
        result = expired_snapshots(snapshots, now=NOW)
        assert len(result) == 1
        assert result[0].snapshot_id == "expired"

    def test_empty_input(self) -> None:
        assert expired_snapshots([], now=NOW) == ()


class TestEnforceQuota:
    def test_under_quota_keeps_all(self) -> None:
        snapshots = [_snapshot("s1", NOW), _snapshot("s2", NOW - timedelta(hours=1))]
        result = enforce_quota(snapshots, max_per_target=5)
        assert len(result.kept) == 2
        assert len(result.evicted) == 0

    def test_over_quota_evicts_oldest_first(self) -> None:
        snapshots = [
            _snapshot("newest", NOW),
            _snapshot("middle", NOW - timedelta(hours=1)),
            _snapshot("oldest", NOW - timedelta(hours=2)),
        ]
        result = enforce_quota(snapshots, max_per_target=2)
        kept_ids = {s.snapshot_id for s in result.kept}
        evicted_ids = {s.snapshot_id for s in result.evicted}
        assert kept_ids == {"newest", "middle"}
        assert evicted_ids == {"oldest"}

    def test_exact_quota_evicts_nothing(self) -> None:
        snapshots = [_snapshot("s1", NOW), _snapshot("s2", NOW - timedelta(hours=1))]
        result = enforce_quota(snapshots, max_per_target=2)
        assert len(result.evicted) == 0

    def test_zero_quota_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            enforce_quota([], max_per_target=0)

    def test_negative_quota_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            enforce_quota([], max_per_target=-1)


class TestValidationBacklog:
    def test_excludes_validated(self) -> None:
        snapshots = [_snapshot("validated", NOW, is_validated=True)]
        assert validation_backlog(snapshots, now=NOW) == ()

    def test_excludes_expired(self) -> None:
        snapshots = [
            _snapshot(
                "expired",
                NOW - timedelta(days=1),
                expires_at=NOW - timedelta(hours=1),
                is_validated=False,
            )
        ]
        assert validation_backlog(snapshots, now=NOW) == ()

    def test_includes_unvalidated_unexpired_newest_first(self) -> None:
        snapshots = [
            _snapshot("older", NOW - timedelta(hours=2), is_validated=False),
            _snapshot("newer", NOW - timedelta(hours=1), is_validated=False),
        ]
        result = validation_backlog(snapshots, now=NOW)
        assert [s.snapshot_id for s in result] == ["newer", "older"]
