"""Tests for app.devices.engine: device lifecycle state transitions and
staleness detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.devices.engine import TransitionRefusal, is_stale, is_terminal, validate_transition
from app.models.enums import DeviceLifecycleState as S


class TestValidateTransition:
    def test_discovered_to_registered_allowed(self) -> None:
        result = validate_transition(S.DISCOVERED, S.REGISTERED)
        assert result.is_allowed

    def test_discovered_to_active_invalid(self) -> None:
        result = validate_transition(S.DISCOVERED, S.ACTIVE)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_full_provisioning_chain(self) -> None:
        chain = [
            (S.DISCOVERED, S.REGISTERED),
            (S.REGISTERED, S.PROVISIONING),
            (S.PROVISIONING, S.PROVISIONED),
            (S.PROVISIONED, S.CONFIGURING),
            (S.CONFIGURING, S.ACTIVE),
        ]
        for current, target in chain:
            result = validate_transition(current, target)
            assert result.is_allowed, f"{current} -> {target} should be allowed"

    def test_active_can_reach_every_operational_state(self) -> None:
        for target in (S.MAINTENANCE, S.SUSPENDED, S.REPLACING, S.RETIRING, S.FAILED):
            result = validate_transition(S.ACTIVE, target)
            assert result.is_allowed, f"ACTIVE -> {target} should be allowed"

    def test_maintenance_returns_to_active(self) -> None:
        assert validate_transition(S.MAINTENANCE, S.ACTIVE).is_allowed

    def test_suspended_can_resume_or_retire(self) -> None:
        assert validate_transition(S.SUSPENDED, S.ACTIVE).is_allowed
        assert validate_transition(S.SUSPENDED, S.RETIRING).is_allowed

    def test_retiring_can_secure_wipe_or_retire_directly(self) -> None:
        assert validate_transition(S.RETIRING, S.SECURE_WIPING).is_allowed
        assert validate_transition(S.RETIRING, S.RETIRED).is_allowed

    def test_secure_wiping_leads_to_retired(self) -> None:
        assert validate_transition(S.SECURE_WIPING, S.RETIRED).is_allowed

    def test_retired_is_terminal(self) -> None:
        result = validate_transition(S.RETIRED, S.ACTIVE)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_failed_can_retry_or_retire(self) -> None:
        assert validate_transition(S.FAILED, S.REGISTERED).is_allowed
        assert validate_transition(S.FAILED, S.RETIRING).is_allowed

    def test_failed_cannot_jump_to_active(self) -> None:
        result = validate_transition(S.FAILED, S.ACTIVE)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_every_non_terminal_state_can_reach_failed(self) -> None:
        for state in (
            S.DISCOVERED,
            S.REGISTERED,
            S.PROVISIONING,
            S.PROVISIONED,
            S.CONFIGURING,
            S.ACTIVE,
            S.MAINTENANCE,
            S.SUSPENDED,
            S.REPLACING,
            S.RETIRING,
            S.SECURE_WIPING,
        ):
            result = validate_transition(state, S.FAILED)
            assert result.is_allowed, f"{state} -> FAILED should be allowed"

    def test_coerces_plain_string_inputs(self) -> None:
        """A value freshly loaded from Postgres comes back as a plain
        ``str``, not the enum instance -- the function must coerce it."""
        result = validate_transition("discovered", "registered")  # type: ignore[arg-type]
        assert result.is_allowed


class TestIsTerminal:
    def test_retired_is_terminal(self) -> None:
        assert is_terminal(S.RETIRED)

    def test_active_is_not_terminal(self) -> None:
        assert not is_terminal(S.ACTIVE)

    def test_failed_is_not_terminal(self) -> None:
        assert not is_terminal(S.FAILED)


class TestIsStale:
    def test_never_seen_is_stale(self) -> None:
        assert is_stale(None, now=datetime.now(UTC), threshold_minutes=15)

    def test_recently_seen_is_not_stale(self) -> None:
        now = datetime.now(UTC)
        assert not is_stale(now - timedelta(minutes=5), now=now, threshold_minutes=15)

    def test_old_last_seen_is_stale(self) -> None:
        now = datetime.now(UTC)
        assert is_stale(now - timedelta(minutes=30), now=now, threshold_minutes=15)

    def test_exact_threshold_boundary_is_not_stale(self) -> None:
        now = datetime.now(UTC)
        assert not is_stale(now - timedelta(minutes=15), now=now, threshold_minutes=15)
