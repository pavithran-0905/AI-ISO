"""End-to-end API tests against the real FastAPI app (real Postgres/Redis)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from httpx import AsyncClient

from app.models.accounts import CloudAccount, CloudProvider
from app.models.enums import BudgetPeriod, CloudProviderType, CloudResourceType
from app.models.resources import CloudResource
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
        response = await client.get("/cloud/accounts")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_non_admin_cannot_register_account(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id, roles=["viewer"])
        response = await client.post(
            "/cloud/accounts",
            json={
                "provider_id": str(UUID(int=0)),
                "external_account_id": "123",
                "name": "a1",
                "credential_ref": "ref",
            },
            headers=headers,
        )
        assert response.status_code == HTTP_FORBIDDEN


async def _create_provider(repos, organization_id: UUID, **kwargs: object) -> CloudProvider:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "provider_type": CloudProviderType.AWS,
        "name": "aws-prod",
    }
    defaults.update(kwargs)
    return await repos.providers.create(CloudProvider(**defaults))


async def _create_account(
    repos, organization_id: UUID, provider_id: UUID, **kwargs: object
) -> CloudAccount:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "provider_id": provider_id,
        "external_account_id": "123456789",
        "name": "a1",
        "credential_ref": "ref",
    }
    defaults.update(kwargs)
    return await repos.accounts.create(CloudAccount(**defaults))


class TestProviderRoutes:
    async def test_list_providers_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/cloud/providers", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["providers"] == []


class TestAccountRoutes:
    async def test_list_accounts_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/cloud/accounts", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["accounts"] == []

    async def test_create_account(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        provider = await _create_provider(repos, organization_id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/cloud/accounts",
            json={
                "provider_id": str(provider.id),
                "external_account_id": "123456789",
                "name": "prod-account",
                "credential_ref": "ref",
            },
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["name"] == "prod-account"

    async def test_create_account_refused_on_empty_credential(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        provider = await _create_provider(repos, organization_id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/cloud/accounts",
            json={
                "provider_id": str(provider.id),
                "external_account_id": "123456789",
                "name": "prod-account",
                "credential_ref": "   ",
            },
            headers=headers,
        )
        assert response.status_code == HTTP_CONFLICT


class TestResourceRoutes:
    async def test_list_resources_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/cloud/resources", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["resources"] == []

    async def test_discover_and_update_and_get(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        provider = await _create_provider(repos, organization_id)
        account = await _create_account(repos, organization_id, provider.id)
        headers = auth_headers(organization_id=organization_id)
        discover_response = await client.post(
            "/cloud/resources/discover",
            json={
                "account_id": str(account.id),
                "resource_type": "virtual_machine",
                "external_id": "i-123",
                "name": "web-1",
            },
            headers=headers,
        )
        assert discover_response.status_code == HTTP_CREATED
        resource_id = discover_response.json()["data"]["id"]

        update_response = await client.put(
            f"/cloud/resources/{resource_id}", json={"name": "web-1-renamed"}, headers=headers
        )
        assert update_response.status_code == HTTP_OK
        assert update_response.json()["data"]["name"] == "web-1-renamed"

    async def test_provision_advances_lifecycle(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        provider = await _create_provider(repos, organization_id)
        account = await _create_account(repos, organization_id, provider.id)
        resource = await repos.resources.create(
            CloudResource(
                organization_id=organization_id,
                account_id=account.id,
                resource_type=CloudResourceType.VIRTUAL_MACHINE,
                external_id="i-123",
                name="web-1",
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/cloud/resources/provision",
            json={"resource_id": str(resource.id), "target_state": "provisioning"},
            headers=headers,
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["lifecycle_state"] == "provisioning"

    async def test_provision_invalid_transition_is_conflict(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        provider = await _create_provider(repos, organization_id)
        account = await _create_account(repos, organization_id, provider.id)
        resource = await repos.resources.create(
            CloudResource(
                organization_id=organization_id,
                account_id=account.id,
                resource_type=CloudResourceType.VIRTUAL_MACHINE,
                external_id="i-123",
                name="web-1",
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/cloud/resources/provision",
            json={"resource_id": str(resource.id), "target_state": "active"},
            headers=headers,
        )
        assert response.status_code == HTTP_CONFLICT

    async def test_delete_resource_invalid_transition_is_conflict(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        """A freshly-discovered resource cannot jump straight to
        deleting -- the route must surface that refusal as a clear 409,
        not an unhandled 500."""
        provider = await _create_provider(repos, organization_id)
        account = await _create_account(repos, organization_id, provider.id)
        resource = await repos.resources.create(
            CloudResource(
                organization_id=organization_id,
                account_id=account.id,
                resource_type=CloudResourceType.VIRTUAL_MACHINE,
                external_id="i-123",
                name="web-1",
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.delete(f"/cloud/resources/{resource.id}", headers=headers)
        assert response.status_code == HTTP_CONFLICT

    async def test_delete_resource_from_active_starts_deleting(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        from app.models.resources import CloudResource

        provider = await _create_provider(repos, organization_id)
        account = await _create_account(repos, organization_id, provider.id)
        resource = await repos.resources.create(
            CloudResource(
                organization_id=organization_id,
                account_id=account.id,
                resource_type=CloudResourceType.VIRTUAL_MACHINE,
                external_id="i-123",
                name="web-1",
                lifecycle_state="active",
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.delete(f"/cloud/resources/{resource.id}", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["lifecycle_state"] == "deleting"


class TestCostRoute:
    async def test_get_cost_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        provider = await _create_provider(repos, organization_id)
        account = await _create_account(repos, organization_id, provider.id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.get(
            "/cloud/cost", params={"account_id": str(account.id)}, headers=headers
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["items"] == []


class TestBudgetRoutes:
    async def test_list_budgets_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/cloud/budgets", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["budgets"] == []

    async def test_create_budget(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/cloud/budgets",
            json={
                "name": "Monthly",
                "amount": 1000.0,
                "period": BudgetPeriod.MONTHLY.value,
                "threshold_fraction": 0.8,
                "period_start": NOW.isoformat(),
                "period_end": (NOW + timedelta(days=30)).isoformat(),
            },
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["name"] == "Monthly"


class TestFleetWideRoutes:
    async def test_optimization_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/cloud/optimization", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["recommendations"] == []

    async def test_compliance_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/cloud/compliance", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["assessments"] == []

    async def test_statistics_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/cloud/statistics", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["windows"] == []

    async def test_reports_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/cloud/reports", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["reports"] == []
