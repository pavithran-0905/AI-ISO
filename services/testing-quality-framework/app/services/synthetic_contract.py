"""Synthetic monitoring checks and contract test recording."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.contract.engine import classify_contract_compatibility
from app.models.enums import CheckResultStatus, ContractTestType, SyntheticCheckType
from app.models.synthetic_contract import ContractTest, SyntheticCheck
from app.repositories.synthetic_contract import ContractTestRepository, SyntheticCheckRepository


class SyntheticCheckService:
    def __init__(self, repo: SyntheticCheckRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        name: str,
        check_type: SyntheticCheckType,
        status: CheckResultStatus,
        latency_ms: float = 0.0,
        detail: str = "",
        now: datetime,
    ) -> SyntheticCheck:
        return await self._repo.create(
            SyntheticCheck(
                organization_id=organization_id,
                name=name,
                check_type=check_type,
                status=status,
                latency_ms=latency_ms,
                detail=detail,
                checked_at=now,
            )
        )


class ContractTestService:
    def __init__(self, repo: ContractTestRepository) -> None:
        self._repo = repo

    async def validate(
        self,
        organization_id: UUID,
        *,
        name: str,
        contract_type: ContractTestType,
        provider_version: str,
        consumer_version: str,
        detail: str = "",
    ) -> ContractTest:
        status = classify_contract_compatibility(
            provider_version=provider_version, consumer_version=consumer_version
        )
        return await self._repo.create(
            ContractTest(
                organization_id=organization_id,
                name=name,
                contract_type=contract_type,
                status=status,
                detail=detail,
            )
        )


__all__ = ["ContractTestService", "SyntheticCheckService"]
