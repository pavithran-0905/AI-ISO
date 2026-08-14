"""Repositories for billing accounts, payment methods and
transactions, invoices, credits, discounts, promotions, and
marketplace subscriptions."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import (
    BillingAccount,
    Credit,
    Discount,
    Invoice,
    InvoiceItem,
    MarketplaceSubscription,
    PaymentMethod,
    PaymentTransaction,
    Promotion,
)
from app.models.enums import InvoiceStatus, PaymentStatus

MAX_PAGE_SIZE = 500


class BillingAccountRepository(BaseRepository[BillingAccount]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, BillingAccount, tenant_scope=tenant_scope)

    async def find_for_customer(self, customer_id: UUID) -> BillingAccount | None:
        stmt = self._base_select().where(BillingAccount.customer_id == customer_id)
        return (await self._session.execute(stmt)).scalars().first()

    async def require_in_org(
        self, organization_id: UUID, billing_account_id: UUID
    ) -> BillingAccount:
        stmt = self._base_select().where(
            BillingAccount.id == billing_account_id,
            BillingAccount.organization_id == organization_id,
        )
        found: BillingAccount | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(
                f"Billing account {billing_account_id!s} was not found in this organization."
            )
        return found


class PaymentMethodRepository(BaseRepository[PaymentMethod]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PaymentMethod, tenant_scope=tenant_scope)

    async def list_for_billing_account(self, billing_account_id: UUID) -> Sequence[PaymentMethod]:
        stmt = self._base_select().where(PaymentMethod.billing_account_id == billing_account_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def find_default(self, billing_account_id: UUID) -> PaymentMethod | None:
        stmt = self._base_select().where(
            PaymentMethod.billing_account_id == billing_account_id,
            PaymentMethod.is_default.is_(True),
        )
        return (await self._session.execute(stmt)).scalars().first()


class PaymentTransactionRepository(BaseRepository[PaymentTransaction]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PaymentTransaction, tenant_scope=tenant_scope)

    async def list_for_billing_account(
        self, billing_account_id: UUID
    ) -> Sequence[PaymentTransaction]:
        stmt = self._base_select().where(
            PaymentTransaction.billing_account_id == billing_account_id
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_recent(
        self, organization_id: UUID, *, status: PaymentStatus | None = None, limit: int = 100
    ) -> Sequence[PaymentTransaction]:
        stmt = self._base_select().where(PaymentTransaction.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(PaymentTransaction.status == status)
        stmt = stmt.order_by(PaymentTransaction.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: PaymentStatus
    ) -> Sequence[PaymentTransaction]:
        stmt = self._base_select().where(
            PaymentTransaction.organization_id == organization_id,
            PaymentTransaction.status == status,
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(PaymentTransaction.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()


class InvoiceRepository(BaseRepository[Invoice]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Invoice, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, invoice_id: UUID) -> Invoice:
        stmt = self._base_select().where(
            Invoice.id == invoice_id, Invoice.organization_id == organization_id
        )
        found: Invoice | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(f"Invoice {invoice_id!s} was not found in this organization.")
        return found

    async def list_recent(
        self, organization_id: UUID, *, status: InvoiceStatus | None = None, limit: int = 100
    ) -> Sequence[Invoice]:
        stmt = self._base_select().where(Invoice.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(Invoice.status == status)
        stmt = stmt.order_by(Invoice.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_status(
        self, organization_id: UUID, *, status: InvoiceStatus
    ) -> Sequence[Invoice]:
        stmt = self._base_select().where(
            Invoice.organization_id == organization_id, Invoice.status == status
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_organization_ids(self) -> Sequence[UUID]:
        stmt = select(Invoice.organization_id).distinct()
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_subscription(self, subscription_id: UUID) -> Sequence[Invoice]:
        stmt = self._base_select().where(Invoice.subscription_id == subscription_id)
        return (await self._session.execute(stmt)).scalars().all()


class InvoiceItemRepository(BaseRepository[InvoiceItem]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, InvoiceItem, tenant_scope=tenant_scope)

    async def list_for_invoice(self, invoice_id: UUID) -> Sequence[InvoiceItem]:
        stmt = self._base_select().where(InvoiceItem.invoice_id == invoice_id)
        return (await self._session.execute(stmt)).scalars().all()


class CreditRepository(BaseRepository[Credit]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Credit, tenant_scope=tenant_scope)

    async def list_for_billing_account(self, billing_account_id: UUID) -> Sequence[Credit]:
        stmt = self._base_select().where(Credit.billing_account_id == billing_account_id)
        return (await self._session.execute(stmt)).scalars().all()


class DiscountRepository(BaseRepository[Discount]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Discount, tenant_scope=tenant_scope)

    async def list_enabled(self, organization_id: UUID) -> Sequence[Discount]:
        stmt = self._base_select().where(
            Discount.organization_id == organization_id, Discount.is_enabled.is_(True)
        )
        return (await self._session.execute(stmt)).scalars().all()


class PromotionRepository(BaseRepository[Promotion]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Promotion, tenant_scope=tenant_scope)

    async def find_by_code(self, organization_id: UUID, *, code: str) -> Promotion | None:
        stmt = self._base_select().where(
            Promotion.organization_id == organization_id, Promotion.code == code
        )
        return (await self._session.execute(stmt)).scalars().first()


class MarketplaceSubscriptionRepository(BaseRepository[MarketplaceSubscription]):
    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MarketplaceSubscription, tenant_scope=tenant_scope)

    async def list_for_customer(self, customer_id: UUID) -> Sequence[MarketplaceSubscription]:
        stmt = self._base_select().where(MarketplaceSubscription.customer_id == customer_id)
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "BillingAccountRepository",
    "CreditRepository",
    "DiscountRepository",
    "InvoiceItemRepository",
    "InvoiceRepository",
    "MarketplaceSubscriptionRepository",
    "PaymentMethodRepository",
    "PaymentTransactionRepository",
    "PromotionRepository",
]
