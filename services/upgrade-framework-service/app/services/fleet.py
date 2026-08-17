"""Fleet-wide upgrade target planning and per-target results."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.fleet.engine import plan_waves
from app.models.enums import UpgradeTargetStatus, UpgradeTargetType
from app.models.upgrade import UpgradeResult, UpgradeTarget
from app.repositories.upgrade import UpgradeResultRepository, UpgradeTargetRepository


class FleetUpgradeService:
    def __init__(self, repo: UpgradeTargetRepository) -> None:
        self._repo = repo

    async def plan_targets(
        self,
        organization_id: UUID,
        *,
        upgrade_job_id: UUID,
        target_refs: Sequence[str],
        target_type: UpgradeTargetType,
        wave_size: int,
    ) -> list[UpgradeTarget]:
        """Register every target for a fleet upgrade job, grouped into
        wave-ordered rows via ``app.fleet.engine.plan_waves``."""
        waves = plan_waves(target_refs, wave_size=wave_size)
        targets: list[UpgradeTarget] = []
        for wave_number, wave in enumerate(waves):
            for target_ref in wave:
                targets.append(
                    await self._repo.create(
                        UpgradeTarget(
                            organization_id=organization_id,
                            upgrade_job_id=upgrade_job_id,
                            target_ref=target_ref,
                            target_type=target_type,
                            wave_number=wave_number,
                        )
                    )
                )
        return targets

    async def mark_status(
        self, target: UpgradeTarget, *, status: UpgradeTargetStatus
    ) -> UpgradeTarget:
        target.status = status
        return await self._repo.update(target)


class UpgradeResultService:
    def __init__(self, repo: UpgradeResultRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        upgrade_target_id: UUID,
        status: UpgradeTargetStatus,
        detail: str = "",
        now: datetime,
    ) -> UpgradeResult:
        return await self._repo.create(
            UpgradeResult(
                organization_id=organization_id,
                upgrade_target_id=upgrade_target_id,
                status=status,
                detail=detail,
                completed_at=now,
            )
        )


__all__ = ["FleetUpgradeService", "UpgradeResultService"]
