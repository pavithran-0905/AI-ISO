"""Tests for app.payments.engine: payment retry eligibility."""

from __future__ import annotations

import pytest

from app.models.enums import PaymentStatus
from app.payments.engine import should_retry_payment


class TestShouldRetryPayment:
    def test_failed_below_max_should_retry(self) -> None:
        decision = should_retry_payment(PaymentStatus.FAILED, attempt_count=1, max_attempts=3)
        assert decision.should_retry

    def test_failed_at_max_should_not_retry(self) -> None:
        decision = should_retry_payment(PaymentStatus.FAILED, attempt_count=3, max_attempts=3)
        assert not decision.should_retry

    def test_succeeded_is_never_retried(self) -> None:
        decision = should_retry_payment(PaymentStatus.SUCCEEDED, attempt_count=1, max_attempts=3)
        assert not decision.should_retry

    def test_pending_is_never_retried(self) -> None:
        decision = should_retry_payment(PaymentStatus.PENDING, attempt_count=1, max_attempts=3)
        assert not decision.should_retry

    def test_refunded_is_never_retried(self) -> None:
        decision = should_retry_payment(PaymentStatus.REFUNDED, attempt_count=1, max_attempts=3)
        assert not decision.should_retry

    def test_non_positive_max_attempts_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            should_retry_payment(PaymentStatus.FAILED, attempt_count=0, max_attempts=0)
