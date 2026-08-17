"""Operational readiness and disaster recovery check recording."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import (
    CheckResultStatus,
    DisasterRecoveryCheckType,
    OperationalReadinessCheckType,
)
from app.models.readiness import DisasterRecoveryCheck, OperationalReadiness
from app.repositories.readiness import (
    DisasterRecoveryCheckRepository,
    OperationalReadinessRepository,
)
from app.services.notifications import HardeningNotifier


class OperationalReadinessService:
    def __init__(
        self, repo: OperationalReadinessRepository, *, notifier: HardeningNotifier | None = None
    ) -> None:
        self._repo = repo
        self._notifier = notifier

    async def record(
        self,
        organization_id: UUID,
        *,
        check_type: OperationalReadinessCheckType,
        status: CheckResultStatus,
        detail: str = "",
        checked_at: datetime,
    ) -> OperationalReadiness:
        check = await self._repo.create(
            OperationalReadiness(
                organization_id=organization_id,
                check_type=check_type,
                status=status,
                detail=detail,
                checked_at=checked_at,
            )
        )
        if self._notifier is not None and CheckResultStatus(status) == CheckResultStatus.FAILED:
            await self._notifier.notify_operational_risk(check_type=str(check_type), detail=detail)
        return check


class DisasterRecoveryCheckService:
    def __init__(self, repo: DisasterRecoveryCheckRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        check_type: DisasterRecoveryCheckType,
        status: CheckResultStatus,
        detail: str = "",
        checked_at: datetime,
    ) -> DisasterRecoveryCheck:
        return await self._repo.create(
            DisasterRecoveryCheck(
                organization_id=organization_id,
                check_type=check_type,
                status=status,
                detail=detail,
                checked_at=checked_at,
            )
        )


__all__ = ["DisasterRecoveryCheckService", "OperationalReadinessService"]
