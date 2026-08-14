"""Enterprise contract creation and approval workflow."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.contracts import Contract
from app.models.enums import ApprovalStatus, AuditAction, ContractStatus
from app.repositories.contracts import ContractRepository
from app.services.audit import AuditService


class ContractService:
    def __init__(self, repo: ContractRepository, *, audit: AuditService | None = None) -> None:
        self._repo = repo
        self._audit = audit

    async def create_contract(
        self,
        organization_id: UUID,
        *,
        customer_id: UUID,
        name: str,
        terms: dict[str, object],
        actor_id: str | None,
        now: datetime,
    ) -> Contract:
        contract = await self._repo.create(
            Contract(
                organization_id=organization_id, customer_id=customer_id, name=name, terms=terms
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.CONTRACT_CHANGED,
                entity_type="contract",
                entity_id=contract.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Created contract {name!r} for customer {customer_id!s}.",
            )
        return contract

    async def approve(self, contract: Contract, *, now: datetime) -> Contract:
        contract.approval_status = ApprovalStatus.APPROVED
        contract.status = ContractStatus.ACTIVE
        contract.start_at = now
        return await self._repo.update(contract)

    async def reject(self, contract: Contract) -> Contract:
        contract.approval_status = ApprovalStatus.REJECTED
        return await self._repo.update(contract)

    async def terminate(self, contract: Contract) -> Contract:
        contract.status = ContractStatus.TERMINATED
        return await self._repo.update(contract)


__all__ = ["ContractService"]
