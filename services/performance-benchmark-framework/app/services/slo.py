"""SLO/SLI compliance evaluation.

Records a compliance result only -- publishing ``SLOViolated`` and
notifying Slo Violation is the SLO compliance sweep worker's own job,
edge-triggered off the latest recorded result, so a caller that
evaluates the same SLO on every request does not re-notify on every
tick for as long as it stays non-compliant.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import SliType
from app.models.slo import SloResult
from app.repositories.slo import SloResultRepository
from app.slo.engine import is_slo_compliant


class SloService:
    def __init__(self, repo: SloResultRepository) -> None:
        self._repo = repo

    async def evaluate(
        self,
        organization_id: UUID,
        *,
        slo_name: str,
        sli_type: SliType,
        target_value: float,
        actual_value: float,
        evaluated_at: datetime,
        higher_is_better: bool | None = None,
    ) -> SloResult:
        compliant = is_slo_compliant(
            actual_value=actual_value,
            target_value=target_value,
            sli_type=sli_type,
            higher_is_better=higher_is_better,
        )
        return await self._repo.create(
            SloResult(
                organization_id=organization_id,
                slo_name=slo_name,
                sli_type=sli_type,
                target_value=target_value,
                actual_value=actual_value,
                is_compliant=compliant,
                evaluated_at=evaluated_at,
            )
        )


__all__ = ["SloService"]
