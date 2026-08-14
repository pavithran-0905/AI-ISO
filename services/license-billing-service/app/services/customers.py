"""Customer and customer-account registration.

Publishes ``CustomerCreated`` on registration.
"""

from __future__ import annotations

from uuid import UUID

from app.events.domain_events import CustomerCreatedEvent
from app.models.customers import Customer, CustomerAccount
from app.models.enums import CustomerAccountStatus, CustomerType
from app.repositories.customers import CustomerAccountRepository, CustomerRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "license-billing-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class CustomerService:
    def __init__(
        self, repo: CustomerRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def create_customer(
        self,
        organization_id: UUID,
        *,
        name: str,
        customer_type: CustomerType,
        parent_customer_id: UUID | None = None,
        billing_contact_email: str | None = None,
        technical_contact_email: str | None = None,
    ) -> Customer:
        customer = await self._repo.create(
            Customer(
                organization_id=organization_id,
                name=name,
                customer_type=customer_type,
                parent_customer_id=parent_customer_id,
                billing_contact_email=billing_contact_email,
                technical_contact_email=technical_contact_email,
            )
        )
        await self._publish(
            CustomerCreatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "customer_id": str(customer.id),
                    "name": name,
                    "customer_type": str(customer_type),
                },
            )
        )
        return customer


class CustomerAccountService:
    def __init__(self, repo: CustomerAccountRepository) -> None:
        self._repo = repo

    async def create_account(
        self, organization_id: UUID, *, customer_id: UUID, external_account_ref: str
    ) -> CustomerAccount:
        return await self._repo.create(
            CustomerAccount(
                organization_id=organization_id,
                customer_id=customer_id,
                external_account_ref=external_account_ref,
                account_status=CustomerAccountStatus.ACTIVE,
            )
        )

    async def suspend(self, account: CustomerAccount) -> CustomerAccount:
        account.account_status = CustomerAccountStatus.SUSPENDED
        return await self._repo.update(account)

    async def close(self, account: CustomerAccount) -> CustomerAccount:
        account.account_status = CustomerAccountStatus.CLOSED
        return await self._repo.update(account)


__all__ = ["CustomerAccountService", "CustomerService"]
