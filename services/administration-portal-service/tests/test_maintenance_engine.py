"""Tests for app.maintenance.engine: maintenance window lifecycle
transitions, overlap detection, and schedule-due checks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.maintenance.engine import (
    ALLOWED_TRANSITIONS,
    TransitionRefusal,
    is_due_to_complete,
    is_due_to_start,
    validate_transition,
    windows_overlap,
)
from app.models.enums import MaintenanceStatus

NOW = datetime(2026, 6, 1, tzinfo=UTC)


class TestValidateTransition:
    def test_scheduled_to_approved_is_allowed(self) -> None:
        assert validate_transition(
            MaintenanceStatus.SCHEDULED, MaintenanceStatus.APPROVED
        ).is_allowed

    def test_approved_to_in_progress_is_allowed(self) -> None:
        assert validate_transition(
            MaintenanceStatus.APPROVED, MaintenanceStatus.IN_PROGRESS
        ).is_allowed

    def test_in_progress_to_completed_is_allowed(self) -> None:
        assert validate_transition(
            MaintenanceStatus.IN_PROGRESS, MaintenanceStatus.COMPLETED
        ).is_allowed

    def test_completed_is_terminal(self) -> None:
        result = validate_transition(MaintenanceStatus.COMPLETED, MaintenanceStatus.APPROVED)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_scheduled_to_completed_is_invalid(self) -> None:
        result = validate_transition(MaintenanceStatus.SCHEDULED, MaintenanceStatus.COMPLETED)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_every_state_has_a_table_entry(self) -> None:
        for status in MaintenanceStatus:
            assert status in ALLOWED_TRANSITIONS


class TestWindowsOverlap:
    def test_overlapping_windows(self) -> None:
        assert windows_overlap(
            NOW, NOW + timedelta(hours=2), NOW + timedelta(hours=1), NOW + timedelta(hours=3)
        )

    def test_non_overlapping_windows(self) -> None:
        assert not windows_overlap(
            NOW, NOW + timedelta(hours=1), NOW + timedelta(hours=2), NOW + timedelta(hours=3)
        )

    def test_touching_windows_overlap(self) -> None:
        assert windows_overlap(
            NOW, NOW + timedelta(hours=1), NOW + timedelta(hours=1), NOW + timedelta(hours=2)
        )

    def test_inverted_window_raises(self) -> None:
        with pytest.raises(ValueError, match="precede"):
            windows_overlap(NOW + timedelta(hours=1), NOW, NOW, NOW + timedelta(hours=1))


class TestIsDueToStart:
    def test_approved_past_start_is_due(self) -> None:
        assert is_due_to_start(
            MaintenanceStatus.APPROVED, starts_at=NOW - timedelta(minutes=1), now=NOW
        )

    def test_scheduled_is_never_due(self) -> None:
        assert not is_due_to_start(
            MaintenanceStatus.SCHEDULED, starts_at=NOW - timedelta(minutes=1), now=NOW
        )

    def test_approved_before_start_is_not_due(self) -> None:
        assert not is_due_to_start(
            MaintenanceStatus.APPROVED, starts_at=NOW + timedelta(minutes=1), now=NOW
        )


class TestIsDueToComplete:
    def test_in_progress_past_end_is_due(self) -> None:
        assert is_due_to_complete(
            MaintenanceStatus.IN_PROGRESS, ends_at=NOW - timedelta(minutes=1), now=NOW
        )

    def test_approved_is_never_due(self) -> None:
        assert not is_due_to_complete(
            MaintenanceStatus.APPROVED, ends_at=NOW - timedelta(minutes=1), now=NOW
        )
