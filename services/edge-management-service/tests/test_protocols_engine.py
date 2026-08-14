"""Tests for app.protocols.engine: industrial protocol connectivity
classification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.enums import ProtocolHealthStatus as S
from app.protocols.engine import classify_connectivity


class TestClassifyConnectivity:
    def test_never_checked_is_unknown(self) -> None:
        status = classify_connectivity(
            None, had_error=False, now=datetime.now(UTC), stale_after_minutes=30
        )
        assert status == S.UNKNOWN

    def test_recent_error_free_check_is_connected(self) -> None:
        now = datetime.now(UTC)
        status = classify_connectivity(
            now - timedelta(minutes=5), had_error=False, now=now, stale_after_minutes=30
        )
        assert status == S.CONNECTED

    def test_error_is_always_error_regardless_of_recency(self) -> None:
        now = datetime.now(UTC)
        status = classify_connectivity(now, had_error=True, now=now, stale_after_minutes=30)
        assert status == S.ERROR

    def test_stale_check_is_unknown(self) -> None:
        now = datetime.now(UTC)
        status = classify_connectivity(
            now - timedelta(minutes=60), had_error=False, now=now, stale_after_minutes=30
        )
        assert status == S.UNKNOWN

    def test_error_beats_staleness(self) -> None:
        now = datetime.now(UTC)
        status = classify_connectivity(
            now - timedelta(minutes=60), had_error=True, now=now, stale_after_minutes=30
        )
        assert status == S.ERROR
