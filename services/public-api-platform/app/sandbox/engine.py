"""Sandbox mock-response selection and session staleness."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.models.enums import MockType

_SIMULATED_ERROR_STATUS_CODE = 500


@dataclass(frozen=True, slots=True)
class MockOutcome:
    status_code: int
    body: dict[str, Any]
    latency_ms: float


def resolve_mock_response(
    *,
    mock_type: MockType,
    response_body: dict[str, Any],
    response_status_code: int,
    simulated_latency_ms: float,
    simulate_error: bool,
) -> MockOutcome:
    """Resolve one configured mock service definition into the outcome
    a sandbox call should return.

    ``DYNAMIC`` mocks are not template-rendered here -- the caller
    already resolved any dynamic substitution into *response_body*
    before calling this; this function's only remaining job is
    honoring the error-simulation override, which always wins
    regardless of mock type.
    """
    if simulate_error:
        return MockOutcome(
            status_code=_SIMULATED_ERROR_STATUS_CODE,
            body={"error": "simulated failure"},
            latency_ms=simulated_latency_ms,
        )
    return MockOutcome(
        status_code=response_status_code, body=response_body, latency_ms=simulated_latency_ms
    )


def is_sandbox_session_stale(*, last_reset_at: datetime, now: datetime, max_age_hours: int) -> bool:
    """Whether a sandbox session has outlived its own configured
    maximum age and should be reset."""
    return now - last_reset_at >= timedelta(hours=max_age_hours)


__all__ = ["MockOutcome", "is_sandbox_session_stale", "resolve_mock_response"]
