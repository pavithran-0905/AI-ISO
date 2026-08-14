"""Repositories for the customer and customer-account tables."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customers import Customer, CustomerAccount

MAX_PAGE_SIZE = 500


class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Customer, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, customer_id: UUID) -> Customer:
        stmt = self._base_select().where(
            Customer.id == customer_id, Customer.organization_id == organization_id
        )
        found: Customer | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"Customer {customer_id!s} was not found in this organization.")
        return found

    async def list_recent(self, organization_id: UUID, *, limit: int = 100) -> Sequence[Customer]:
        stmt = (
            self._base_select()
            .where(Customer.organization_id == organization_id)
            .order_by(Customer.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_children(self, parent_customer_id: UUID) -> Sequence[Customer]:
        stmt = self._base_select().where(Customer.parent_customer_id == parent_customer_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(Customer.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class CustomerAccountRepository(BaseRepository[CustomerAccount]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, CustomerAccount, tenant_scope=tenant_scope)

    async def list_for_customer(self, customer_id: UUID) -> Sequence[CustomerAccount]:
        stmt = self._base_select().where(CustomerAccount.customer_id == customer_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def find_by_external_ref(
        self, organization_id: UUID, *, external_account_ref: str
    ) -> CustomerAccount | None:
        stmt = self._base_select().where(
            CustomerAccount.organization_id == organization_id,
            CustomerAccount.external_account_ref == external_account_ref,
        )
        return (await self._session.execute(stmt)).scalars().first()


__all__ = ["MAX_PAGE_SIZE", "CustomerAccountRepository", "CustomerRepository"]
