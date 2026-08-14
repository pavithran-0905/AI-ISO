"""Tests for app.tenants.engine: tenant lifecycle transitions and
limit-vs-usage classification."""

from __future__ import annotations

import pytest

from app.models.enums import TenantStatus
from app.tenants.engine import (
    ALLOWED_TRANSITIONS,
    TenantLimitStatus,
    TransitionRefusal,
    classify_limit_status,
    validate_transition,
)


class TestValidateTransition:
    def test_provisioning_to_active_is_allowed(self) -> None:
        assert validate_transition(TenantStatus.PROVISIONING, TenantStatus.ACTIVE).is_allowed

    def test_active_to_suspended_is_allowed(self) -> None:
        assert validate_transition(TenantStatus.ACTIVE, TenantStatus.SUSPENDED).is_allowed

    def test_active_to_migrating_is_allowed(self) -> None:
        assert validate_transition(TenantStatus.ACTIVE, TenantStatus.MIGRATING).is_allowed

    def test_deleting_to_deleted_is_allowed(self) -> None:
        assert validate_transition(TenantStatus.DELETING, TenantStatus.DELETED).is_allowed

    def test_deleted_is_terminal(self) -> None:
        result = validate_transition(TenantStatus.DELETED, TenantStatus.ACTIVE)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.TERMINAL_STATE

    def test_provisioning_to_suspended_is_invalid(self) -> None:
        result = validate_transition(TenantStatus.PROVISIONING, TenantStatus.SUSPENDED)
        assert not result.is_allowed
        assert result.refusal == TransitionRefusal.INVALID_TRANSITION

    def test_every_state_has_a_table_entry(self) -> None:
        for status in TenantStatus:
            assert status in ALLOWED_TRANSITIONS


class TestClassifyLimitStatus:
    def test_low_usage_is_ok(self) -> None:
        assert classify_limit_status(5, 100, warning_fraction=0.8) == TenantLimitStatus.OK

    def test_high_usage_is_warning(self) -> None:
        assert classify_limit_status(85, 100, warning_fraction=0.8) == TenantLimitStatus.WARNING

    def test_at_limit_is_exceeded(self) -> None:
        assert classify_limit_status(100, 100, warning_fraction=0.8) == TenantLimitStatus.EXCEEDED

    def test_over_limit_is_exceeded(self) -> None:
        assert classify_limit_status(150, 100, warning_fraction=0.8) == TenantLimitStatus.EXCEEDED

    def test_negative_used_value_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            classify_limit_status(-1, 100, warning_fraction=0.8)

    def test_non_positive_limit_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            classify_limit_status(0, 0, warning_fraction=0.8)
