"""End-to-end API tests against the real FastAPI app (real Postgres/Redis)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from httpx import AsyncClient

from app.models.billing import BillingAccount
from app.models.customers import Customer
from app.models.enums import BillingModel, CustomerType, LicenseModel
from app.models.licenses import License
from app.models.subscriptions import Subscription, SubscriptionPlan
from tests.conftest import (
    HTTP_CONFLICT,
    HTTP_CREATED,
    HTTP_FORBIDDEN,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    AuthHeadersFn,
)

NOW = datetime(2026, 6, 1, tzinfo=UTC)


class TestHealthEndpoints:
    async def test_health(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] == "healthy"

    async def test_liveness(self, client: AsyncClient) -> None:
        response = await client.get("/liveness")
        assert response.status_code == HTTP_OK

    async def test_readiness(self, client: AsyncClient) -> None:
        response = await client.get("/readiness")
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] in ("ready", "not_ready")

    async def test_metrics(self, client: AsyncClient) -> None:
        response = await client.get("/metrics")
        assert response.status_code == HTTP_OK


class TestAuth:
    async def test_missing_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get("/licenses")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_non_admin_cannot_issue_license(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id, roles=["viewer"])
        response = await client.post(
            "/licenses",
            json={"customer_id": str(uuid4()), "license_model": "saas"},
            headers=headers,
        )
        assert response.status_code == HTTP_FORBIDDEN


async def _create_customer(repos, organization_id: UUID, **kwargs: object) -> Customer:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "name": "Acme",
        "customer_type": CustomerType.ORGANIZATION,
    }
    defaults.update(kwargs)
    return await repos.customers.create(Customer(**defaults))


async def _create_plan(repos, organization_id: UUID, **kwargs: object) -> SubscriptionPlan:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "name": "Pro",
        "billing_model": BillingModel.MONTHLY,
        "base_price": 100.0,
    }
    defaults.update(kwargs)
    return await repos.plans.create(SubscriptionPlan(**defaults))


class TestLicenseRoutes:
    async def test_list_licenses_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/licenses", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["licenses"] == []

    async def test_create_and_get_license(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        customer = await _create_customer(repos, organization_id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/licenses",
            json={"customer_id": str(customer.id), "license_model": "saas", "seat_limit": 5},
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        license_id = response.json()["data"]["id"]

        get_response = await client.get(f"/licenses/{license_id}", headers=headers)
        assert get_response.status_code == HTTP_OK
        assert get_response.json()["data"]["status"] == "issued"

    async def test_activate_license(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        customer = await _create_customer(repos, organization_id)
        license_row = await repos.licenses.create(
            License(
                organization_id=organization_id,
                customer_id=customer.id,
                license_model=LicenseModel.SAAS,
                issued_at=NOW,
                seat_limit=1,
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            f"/licenses/{license_row.id}/activate",
            json={"activation_ref": "device-1"},
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["activation_ref"] == "device-1"

    async def test_activate_license_past_seat_limit_is_conflict(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        customer = await _create_customer(repos, organization_id)
        license_row = await repos.licenses.create(
            License(
                organization_id=organization_id,
                customer_id=customer.id,
                license_model=LicenseModel.SAAS,
                issued_at=NOW,
                seat_limit=1,
            )
        )
        headers = auth_headers(organization_id=organization_id)
        await client.post(
            f"/licenses/{license_row.id}/activate",
            json={"activation_ref": "device-1"},
            headers=headers,
        )
        response = await client.post(
            f"/licenses/{license_row.id}/activate",
            json={"activation_ref": "device-2"},
            headers=headers,
        )
        assert response.status_code == HTTP_CONFLICT

    async def test_revoke_license(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        customer = await _create_customer(repos, organization_id)
        license_row = await repos.licenses.create(
            License(
                organization_id=organization_id,
                customer_id=customer.id,
                license_model=LicenseModel.SAAS,
                issued_at=NOW,
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(f"/licenses/{license_row.id}/revoke", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] == "revoked"

    async def test_revoke_already_revoked_license_is_conflict(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        customer = await _create_customer(repos, organization_id)
        license_row = await repos.licenses.create(
            License(
                organization_id=organization_id,
                customer_id=customer.id,
                license_model=LicenseModel.SAAS,
                issued_at=NOW,
            )
        )
        headers = auth_headers(organization_id=organization_id)
        await client.post(f"/licenses/{license_row.id}/revoke", headers=headers)
        response = await client.post(f"/licenses/{license_row.id}/revoke", headers=headers)
        assert response.status_code == HTTP_CONFLICT


class TestSubscriptionRoutes:
    async def test_list_subscriptions_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/subscriptions", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["subscriptions"] == []

    async def test_create_subscription(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        customer = await _create_customer(repos, organization_id)
        plan = await _create_plan(repos, organization_id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/subscriptions",
            json={
                "customer_id": str(customer.id),
                "plan_id": str(plan.id),
                "start_at": NOW.isoformat(),
                "current_period_end": (NOW + timedelta(days=30)).isoformat(),
            },
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["status"] == "trial"

    async def test_update_subscription_transitions(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        customer = await _create_customer(repos, organization_id)
        plan = await _create_plan(repos, organization_id)
        subscription = await repos.subscriptions.create(
            Subscription(
                organization_id=organization_id,
                customer_id=customer.id,
                plan_id=plan.id,
                start_at=NOW,
                current_period_start=NOW,
                current_period_end=NOW + timedelta(days=30),
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.put(
            f"/subscriptions/{subscription.id}", json={"target_status": "active"}, headers=headers
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] == "active"

    async def test_update_subscription_invalid_transition_is_conflict(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        customer = await _create_customer(repos, organization_id)
        plan = await _create_plan(repos, organization_id)
        subscription = await repos.subscriptions.create(
            Subscription(
                organization_id=organization_id,
                customer_id=customer.id,
                plan_id=plan.id,
                start_at=NOW,
                current_period_start=NOW,
                current_period_end=NOW + timedelta(days=30),
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.put(
            f"/subscriptions/{subscription.id}",
            json={"target_status": "suspended"},
            headers=headers,
        )
        assert response.status_code == HTTP_CONFLICT

    async def test_delete_subscription_cancels(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        customer = await _create_customer(repos, organization_id)
        plan = await _create_plan(repos, organization_id)
        subscription = await repos.subscriptions.create(
            Subscription(
                organization_id=organization_id,
                customer_id=customer.id,
                plan_id=plan.id,
                start_at=NOW,
                current_period_start=NOW,
                current_period_end=NOW + timedelta(days=30),
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.delete(f"/subscriptions/{subscription.id}", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] == "cancelled"


class TestInvoiceRoutes:
    async def test_list_invoices_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/billing/invoices", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["invoices"] == []

    async def test_create_invoice(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        customer = await _create_customer(repos, organization_id)
        account = await repos.billing_accounts.create(
            BillingAccount(organization_id=organization_id, customer_id=customer.id)
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/billing/invoices",
            json={
                "billing_account_id": str(account.id),
                "invoice_number": "INV-API-1",
                "items": [{"description": "Pro plan", "quantity": 1.0, "unit_price": 100.0}],
                "currency": "USD",
            },
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["total_amount"] == 100.0


class TestPaymentRoutes:
    async def test_list_payments_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/billing/payments", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["payments"] == []

    async def test_create_successful_payment(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        customer = await _create_customer(repos, organization_id)
        account = await repos.billing_accounts.create(
            BillingAccount(organization_id=organization_id, customer_id=customer.id)
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/billing/payments",
            json={"billing_account_id": str(account.id), "amount": 50.0, "succeeded": True},
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["status"] == "succeeded"

    async def test_create_failed_payment(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        customer = await _create_customer(repos, organization_id)
        account = await repos.billing_accounts.create(
            BillingAccount(organization_id=organization_id, customer_id=customer.id)
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/billing/payments",
            json={"billing_account_id": str(account.id), "amount": 50.0, "succeeded": False},
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["status"] == "failed"


class TestUsageQuotaStatisticsReportRoutes:
    async def test_get_usage_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        customer = await _create_customer(repos, organization_id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.get(
            "/billing/usage", params={"customer_id": str(customer.id)}, headers=headers
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["counters"] == []

    async def test_get_quotas_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/billing/quotas", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["quotas"] == []

    async def test_get_statistics_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/billing/statistics", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["windows"] == []

    async def test_get_reports_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/billing/reports", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["reports"] == []
