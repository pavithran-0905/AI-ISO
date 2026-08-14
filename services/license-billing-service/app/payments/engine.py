"""Payment retry eligibility.

**Only a `FAILED` transaction is retryable, and only up to the
configured attempt ceiling.** A `SUCCEEDED` or `REFUNDED` transaction
retried again would double-charge; a `PENDING` one retried again would
race the attempt already in flight.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import PaymentStatus


@dataclass(frozen=True, slots=True)
class RetryDecision:
    should_retry: bool
    detail: str


def should_retry_payment(
    status: PaymentStatus, *, attempt_count: int, max_attempts: int
) -> RetryDecision:
    """Whether a payment transaction should be retried.

    Raises:
        ValueError: On a non-positive *max_attempts*.
    """
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be at least 1; got {max_attempts}.")
    if PaymentStatus(status) != PaymentStatus.FAILED:
        return RetryDecision(
            should_retry=False, detail=f"Status {status} is not retryable by this decision."
        )
    if attempt_count >= max_attempts:
        return RetryDecision(
            should_retry=False,
            detail=f"Already attempted {attempt_count} time(s), at the maximum of {max_attempts}.",
        )
    return RetryDecision(
        should_retry=True, detail=f"Attempt {attempt_count + 1} of {max_attempts}."
    )


__all__ = ["RetryDecision", "should_retry_payment"]
