"""Tests for app.digital_twins.engine: digital twin sync classification."""

from __future__ import annotations

from app.digital_twins.engine import classify_twin_sync
from app.models.enums import SyncStatus as S


class TestClassifyTwinSync:
    def test_syncing_is_in_progress_regardless_of_hashes(self) -> None:
        assert classify_twin_sync("a", "a", is_syncing=True) == S.IN_PROGRESS
        assert classify_twin_sync(None, None, is_syncing=True) == S.IN_PROGRESS

    def test_missing_desired_hash_is_pending(self) -> None:
        assert classify_twin_sync(None, "live", is_syncing=False) == S.PENDING

    def test_missing_live_hash_is_pending(self) -> None:
        assert classify_twin_sync("desired", None, is_syncing=False) == S.PENDING

    def test_matching_hashes_is_completed(self) -> None:
        assert classify_twin_sync("hash-1", "hash-1", is_syncing=False) == S.COMPLETED

    def test_mismatched_hashes_is_conflict(self) -> None:
        assert classify_twin_sync("hash-1", "hash-2", is_syncing=False) == S.CONFLICT
