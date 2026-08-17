"""Upgrade dry-run simulation.

Purely computed from caller-supplied inputs -- nothing here is
persisted, matching ``app.simulation.engine``'s own module docstring on
why docs/076's DATABASE TABLES section has no simulation-result table.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.models.enums import CheckResultStatus
from app.simulation.engine import assess_risk, estimate_duration_seconds


@dataclass(frozen=True, slots=True)
class SimulationOutcome:
    risk_level: str
    estimated_duration_seconds: float
    check_count: int


class SimulationService:
    def simulate(
        self,
        *,
        compatibility_results: Sequence[CheckResultStatus],
        dependency_results: Sequence[CheckResultStatus],
        target_count: int,
        seconds_per_target: float,
    ) -> SimulationOutcome:
        combined = list(compatibility_results) + list(dependency_results)
        return SimulationOutcome(
            risk_level=assess_risk(combined),
            estimated_duration_seconds=estimate_duration_seconds(
                target_count=target_count, seconds_per_target=seconds_per_target
            ),
            check_count=len(combined),
        )


__all__ = ["SimulationOutcome", "SimulationService"]
