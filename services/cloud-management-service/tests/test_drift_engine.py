"""Tests for app.drift.engine: drift detection and severity
classification."""

from __future__ import annotations

import pytest

from app.drift.engine import classify_drift_severity, has_drifted
from app.models.enums import DriftSeverity


class TestHasDrifted:
    def test_matching_hashes_no_drift(self) -> None:
        assert not has_drifted("hash-1", "hash-1")

    def test_mismatched_hashes_drifted(self) -> None:
        assert has_drifted("hash-1", "hash-2")

    def test_missing_desired_hash_no_drift(self) -> None:
        assert not has_drifted(None, "hash-1")

    def test_missing_live_hash_no_drift(self) -> None:
        assert not has_drifted("hash-1", None)


class TestClassifyDriftSeverity:
    def test_zero_fields_is_low(self) -> None:
        assert (
            classify_drift_severity(0, high_threshold=3, critical_threshold=5) == DriftSeverity.LOW
        )

    def test_below_high_is_medium(self) -> None:
        assert (
            classify_drift_severity(1, high_threshold=3, critical_threshold=5)
            == DriftSeverity.MEDIUM
        )

    def test_at_high_threshold(self) -> None:
        assert (
            classify_drift_severity(3, high_threshold=3, critical_threshold=5) == DriftSeverity.HIGH
        )

    def test_at_critical_threshold(self) -> None:
        assert (
            classify_drift_severity(5, high_threshold=3, critical_threshold=5)
            == DriftSeverity.CRITICAL
        )

    def test_negative_count_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            classify_drift_severity(-1, high_threshold=3, critical_threshold=5)
