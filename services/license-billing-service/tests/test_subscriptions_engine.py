"""Tests for app.subscriptions.engine: subscription lifecycle
transitions, grace period, and renewal-due detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import SubscriptionStatus
from app.subscriptions.engine import (
    ALLOWED_TRANSITIONS,
    TransitionRefusal,
    is_renewal_due,
    is_within_grace_period,
    validate_transition,
)


class TestValidateTransition:
    def test_trial_to_active_is_allowed(self) -> None:
        assert validate_transition(SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE).is_allowed

    def test_active_to_pending_renewal_is_allowed(self) -> None:
        assert validate_transition(
            SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING_RENEWAL
        ).is_allowed

    def test_expired_to_active_reactivates(self) -> None:
        assert validate_transition(SubscriptionStatus.EXPIRED, SubscriptionStatus.ACTIVE).is_allowed

    def test_cancelled_is_terminal(self) -> None:
        result = validate_transition(SubscriptionStatus.CANCELLED, SubscriptionStatus.ACTIVE)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_trial_to_suspended_is_invalid(self) -> None:
        result = validate_transition(SubscriptionStatus.TRIAL, SubscriptionStatus.SUSPENDED)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_every_state_has_a_table_entry(self) -> None:
        for status in SubscriptionStatus:
            assert status in ALLOWED_TRANSITIONS


class TestIsWithinGracePeriod:
    def test_before_period_end_is_not_yet_in_grace(self) -> None:
        end = datetime.now(UTC) + timedelta(days=1)
        assert not is_within_grace_period(end, now=datetime.now(UTC), grace_period_days=7)

    def test_just_past_period_end_is_in_grace(self) -> None:
        now = datetime.now(UTC)
        end = now - timedelta(days=1)
        assert is_within_grace_period(end, now=now, grace_period_days=7)

    def test_past_grace_window_is_not_in_grace(self) -> None:
        now = datetime.now(UTC)
        end = now - timedelta(days=10)
        assert not is_within_grace_period(end, now=now, grace_period_days=7)

    def test_negative_grace_period_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            is_within_grace_period(datetime.now(UTC), now=datetime.now(UTC), grace_period_days=-1)


class TestIsRenewalDue:
    def test_outside_reminder_window_is_not_due(self) -> None:
        end = datetime.now(UTC) + timedelta(days=30)
        assert not is_renewal_due(end, now=datetime.now(UTC), reminder_days_before=14)

    def test_inside_reminder_window_is_due(self) -> None:
        end = datetime.now(UTC) + timedelta(days=5)
        assert is_renewal_due(end, now=datetime.now(UTC), reminder_days_before=14)

    def test_past_period_end_is_due(self) -> None:
        end = datetime.now(UTC) - timedelta(days=1)
        assert is_renewal_due(end, now=datetime.now(UTC), reminder_days_before=14)

    def test_non_positive_reminder_days_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            is_renewal_due(datetime.now(UTC), now=datetime.now(UTC), reminder_days_before=0)
