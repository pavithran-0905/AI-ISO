"""Billing account and payment method registration."""

from __future__ import annotations

from uuid import UUID

from app.models.billing import BillingAccount, PaymentMethod
from app.models.enums import PaymentMethodType
from app.repositories.billing import BillingAccountRepository, PaymentMethodRepository


class BillingAccountService:
    def __init__(self, repo: BillingAccountRepository) -> None:
        self._repo = repo

    async def create_account(
        self,
        organization_id: UUID,
        *,
        customer_id: UUID,
        currency: str = "USD",
        tax_id: str | None = None,
        billing_email: str | None = None,
    ) -> BillingAccount:
        return await self._repo.create(
            BillingAccount(
                organization_id=organization_id,
                customer_id=customer_id,
                currency=currency,
                tax_id=tax_id,
                billing_email=billing_email,
            )
        )


class PaymentMethodService:
    def __init__(self, repo: PaymentMethodRepository) -> None:
        self._repo = repo

    async def add_method(
        self,
        organization_id: UUID,
        *,
        billing_account_id: UUID,
        method_type: PaymentMethodType,
        reference: str | None,
        is_default: bool = False,
    ) -> PaymentMethod:
        if is_default:
            existing_default = await self._repo.find_default(billing_account_id)
            if existing_default is not None:
                existing_default.is_default = False
                await self._repo.update(existing_default)
        return await self._repo.create(
            PaymentMethod(
                organization_id=organization_id,
                billing_account_id=billing_account_id,
                method_type=method_type,
                reference=reference,
                is_default=is_default,
            )
        )


__all__ = ["BillingAccountService", "PaymentMethodService"]
