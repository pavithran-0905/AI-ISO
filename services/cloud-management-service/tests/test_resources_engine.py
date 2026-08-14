"""Tests for app.resources.engine: cloud resource lifecycle
transitions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.enums import CloudResourceLifecycleState as S
from app.resources.engine import TransitionRefusal, is_stale, is_terminal, validate_transition


class TestValidateTransition:
    def test_discovered_to_provisioning_allowed(self) -> None:
        assert validate_transition(S.DISCOVERED, S.PROVISIONING).is_allowed

    def test_discovered_to_active_invalid(self) -> None:
        result = validate_transition(S.DISCOVERED, S.ACTIVE)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_full_provisioning_chain(self) -> None:
        assert validate_transition(S.PROVISIONING, S.ACTIVE).is_allowed
        assert validate_transition(S.IMPORTED, S.ACTIVE).is_allowed

    def test_active_can_reach_every_operational_state(self) -> None:
        for target in (S.UPDATING, S.SCALING, S.SUSPENDED, S.STOPPED, S.DELETING, S.FAILED):
            assert validate_transition(S.ACTIVE, target).is_allowed, target

    def test_updating_and_scaling_return_to_active(self) -> None:
        assert validate_transition(S.UPDATING, S.ACTIVE).is_allowed
        assert validate_transition(S.SCALING, S.ACTIVE).is_allowed

    def test_suspended_and_stopped_can_resume_or_delete(self) -> None:
        assert validate_transition(S.SUSPENDED, S.ACTIVE).is_allowed
        assert validate_transition(S.SUSPENDED, S.DELETING).is_allowed
        assert validate_transition(S.STOPPED, S.DELETING).is_allowed

    def test_deleting_leads_to_deleted(self) -> None:
        assert validate_transition(S.DELETING, S.DELETED).is_allowed

    def test_deleted_can_archive(self) -> None:
        assert validate_transition(S.DELETED, S.ARCHIVED).is_allowed

    def test_archived_is_terminal(self) -> None:
        result = validate_transition(S.ARCHIVED, S.ACTIVE)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_failed_can_retry_or_be_deleted(self) -> None:
        assert validate_transition(S.FAILED, S.PROVISIONING).is_allowed
        assert validate_transition(S.FAILED, S.DELETING).is_allowed

    def test_coerces_plain_string_inputs(self) -> None:
        result = validate_transition("discovered", "provisioning")  # type: ignore[arg-type]
        assert result.is_allowed


class TestIsTerminal:
    def test_archived_is_terminal(self) -> None:
        assert is_terminal(S.ARCHIVED)

    def test_active_is_not_terminal(self) -> None:
        assert not is_terminal(S.ACTIVE)


class TestIsStale:
    def test_never_synced_is_stale(self) -> None:
        assert is_stale(None, now=datetime.now(UTC), threshold_minutes=60)

    def test_recently_synced_is_not_stale(self) -> None:
        now = datetime.now(UTC)
        assert not is_stale(now - timedelta(minutes=5), now=now, threshold_minutes=60)

    def test_old_sync_is_stale(self) -> None:
        now = datetime.now(UTC)
        assert is_stale(now - timedelta(minutes=90), now=now, threshold_minutes=60)
