"""Tests for app.gitops.engine: sync classification."""

from __future__ import annotations

from app.gitops.engine import classify_sync
from app.models.enums import SyncStatus as S


class TestClassifySync:
    def test_syncing_regardless_of_hashes(self) -> None:
        assert classify_sync("a", "b", is_syncing=True) is S.SYNCING
        assert classify_sync("a", "a", is_syncing=True) is S.SYNCING

    def test_matching_hashes_in_sync(self) -> None:
        assert classify_sync("abc", "abc", is_syncing=False) is S.IN_SYNC

    def test_mismatched_hashes_out_of_sync(self) -> None:
        assert classify_sync("abc", "xyz", is_syncing=False) is S.OUT_OF_SYNC

    def test_missing_desired_hash_unknown(self) -> None:
        assert classify_sync(None, "xyz", is_syncing=False) is S.UNKNOWN

    def test_missing_live_hash_unknown(self) -> None:
        assert classify_sync("abc", None, is_syncing=False) is S.UNKNOWN

    def test_both_missing_unknown(self) -> None:
        assert classify_sync(None, None, is_syncing=False) is S.UNKNOWN
