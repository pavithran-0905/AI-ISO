"""Integration tests for the 15 REST endpoints, against the real app
through its actual lifespan (real PostgreSQL, Redis; RabbitMQ event
publishing goes through the real broker too, since these tests exercise
``app.state.publish_event`` end-to-end)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient

from app.models.applications import DeveloperApplication
from app.models.enums import ApiProductStatus, ApiProductType, QuotaResetPolicy, QuotaType
from app.models.products import ApiPlan, ApiProduct
from app.services.bundle import Repositories
from app.services.documents import GraphQlSchemaService, OpenApiDocumentService
from app.services.quotas import QuotaService
from app.services.usage import UsageService
from app.services.versioning import ApiVersionService
from tests.conftest import (
    HTTP_CREATED,
    HTTP_FORBIDDEN,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    AuthHeadersFn,
)


def _now() -> datetime:
    return datetime.now(UTC)


class TestDeveloperRegisterAndProfile:
    async def test_register_developer(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("dev-a@example.com", organization_id=organization_id)
        response = await client.post(
            "/developers/register",
            headers=headers,
            json={"email": "dev-a@example.com", "display_name": "Dev A"},
        )
        assert response.status_code == HTTP_CREATED, response.text
        data = response.json()["data"]
        assert data["email"] == "dev-a@example.com"
        assert data["status"] == "pending_verification"

    async def test_profile_requires_registration(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("ghost@example.com", organization_id=organization_id)
        response = await client.get("/developers/profile", headers=headers)
        assert response.status_code == HTTP_NOT_FOUND

    async def test_profile_after_registration(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("dev-b@example.com", organization_id=organization_id)
        await client.post(
            "/developers/register", headers=headers, json={"email": "dev-b@example.com"}
        )
        response = await client.get("/developers/profile", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["email"] == "dev-b@example.com"

    async def test_register_requires_token(self, client: AsyncClient) -> None:
        response = await client.post("/developers/register", json={"email": "x@example.com"})
        assert response.status_code == HTTP_UNAUTHORIZED


class TestApplicationsAndCredentials:
    async def _register_developer(
        self,
        client: AsyncClient,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
        email: str,
    ) -> dict[str, str]:
        headers = auth_headers(email, organization_id=organization_id)
        await client.post("/developers/register", headers=headers, json={"email": email})
        return headers

    async def test_create_and_list_applications(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = await self._register_developer(
            client, organization_id, auth_headers, "dev-c@example.com"
        )
        response = await client.post(
            "/applications",
            headers=headers,
            json={"name": "My App", "redirect_uris": ["https://a.example/cb"]},
        )
        assert response.status_code == HTTP_CREATED
        list_response = await client.get("/applications", headers=headers)
        assert list_response.status_code == HTTP_OK
        assert list_response.json()["data"]["total"] == 1

    async def test_create_oauth_client(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = await self._register_developer(
            client, organization_id, auth_headers, "dev-d@example.com"
        )
        app_response = await client.post("/applications", headers=headers, json={"name": "App"})
        application_id = app_response.json()["data"]["id"]
        response = await client.post(
            "/oauth/clients",
            headers=headers,
            json={"application_id": application_id, "grant_types": ["client_credentials"]},
        )
        assert response.status_code == HTTP_CREATED
        data = response.json()["data"]
        assert len(data["client_secret"]) >= 32

    async def test_create_oauth_client_for_unowned_application_is_404(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = await self._register_developer(
            client, organization_id, auth_headers, "dev-e@example.com"
        )
        response = await client.post(
            "/oauth/clients",
            headers=headers,
            json={"application_id": str(uuid.uuid4()), "grant_types": ["client_credentials"]},
        )
        assert response.status_code == HTTP_NOT_FOUND

    async def test_create_api_key(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = await self._register_developer(
            client, organization_id, auth_headers, "dev-f@example.com"
        )
        app_response = await client.post("/applications", headers=headers, json={"name": "App"})
        application_id = app_response.json()["data"]["id"]
        response = await client.post(
            "/api-keys", headers=headers, json={"application_id": application_id}
        )
        assert response.status_code == HTTP_CREATED
        assert len(response.json()["data"]["api_key"]) >= 32


class TestProductsPlansSubscriptions:
    async def test_list_products_only_approved(
        self,
        client: AsyncClient,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
    ) -> None:
        await repos.api_products.create(
            ApiProduct(
                organization_id=organization_id,
                name="Approved API",
                product_type=ApiProductType.PUBLIC,
                status=ApiProductStatus.APPROVED,
            )
        )
        await repos.api_products.create(
            ApiProduct(
                organization_id=organization_id,
                name="Draft API",
                product_type=ApiProductType.PUBLIC,
                status=ApiProductStatus.DRAFT,
            )
        )
        headers = auth_headers("dev-g@example.com", organization_id=organization_id)
        response = await client.get("/products", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1

    async def test_list_plans_and_subscribe(
        self,
        client: AsyncClient,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
    ) -> None:
        product = await repos.api_products.create(
            ApiProduct(
                organization_id=organization_id, name="P", product_type=ApiProductType.PUBLIC
            )
        )
        plan = await repos.api_plans.create(
            ApiPlan(organization_id=organization_id, api_product_id=product.id, name="Free")
        )
        headers = auth_headers("dev-h@example.com", organization_id=organization_id)
        await client.post(
            "/developers/register", headers=headers, json={"email": "dev-h@example.com"}
        )

        plans_response = await client.get(
            "/plans", headers=headers, params={"api_product_id": str(product.id)}
        )
        assert plans_response.status_code == HTTP_OK
        assert plans_response.json()["data"]["total"] == 1

        sub_response = await client.post(
            "/subscriptions", headers=headers, json={"api_plan_id": str(plan.id)}
        )
        assert sub_response.status_code == HTTP_CREATED
        assert sub_response.json()["data"]["status"] == "active"


class TestUsageAndQuotas:
    async def test_get_usage(
        self,
        client: AsyncClient,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
    ) -> None:
        headers = auth_headers("dev-i@example.com", organization_id=organization_id)
        await client.post(
            "/developers/register", headers=headers, json={"email": "dev-i@example.com"}
        )
        developer = await repos.developer_accounts.find_by_email(
            organization_id, email="dev-i@example.com"
        )
        assert developer is not None
        application = await repos.applications.create(
            DeveloperApplication(
                organization_id=organization_id, developer_account_id=developer.id, name="App"
            )
        )
        product = await repos.api_products.create(
            ApiProduct(
                organization_id=organization_id, name="P", product_type=ApiProductType.PUBLIC
            )
        )
        usage_service = UsageService(repos.api_usage)
        await usage_service.record(
            organization_id,
            developer_account_id=developer.id,
            application_id=application.id,
            api_product_id=product.id,
            endpoint="/x",
            status_code=200,
            latency_ms=10.0,
            occurred_at=_now(),
        )
        response = await client.get("/usage", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1

    async def test_get_quotas(
        self,
        client: AsyncClient,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
    ) -> None:
        headers = auth_headers("dev-j@example.com", organization_id=organization_id)
        await client.post(
            "/developers/register", headers=headers, json={"email": "dev-j@example.com"}
        )
        developer = await repos.developer_accounts.find_by_email(
            organization_id, email="dev-j@example.com"
        )
        assert developer is not None
        quota_service = QuotaService(repos.api_quotas)
        await quota_service.provision(
            organization_id,
            developer_account_id=developer.id,
            quota_type=QuotaType.API_CALLS,
            limit_value=1000,
            reset_policy=QuotaResetPolicy.MONTHLY,
            now=_now(),
        )
        response = await client.get("/quotas", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1


class TestDocumentation:
    async def test_openapi_document_missing_is_404(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("dev-k@example.com", organization_id=organization_id)
        response = await client.get(
            "/openapi", headers=headers, params={"api_product_id": str(uuid.uuid4())}
        )
        assert response.status_code == HTTP_NOT_FOUND

    async def test_openapi_document_published(
        self,
        client: AsyncClient,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
    ) -> None:
        product = await repos.api_products.create(
            ApiProduct(
                organization_id=organization_id, name="P", product_type=ApiProductType.PUBLIC
            )
        )
        version_service = ApiVersionService(repos.api_versions)
        version = await version_service.create_draft(
            organization_id, api_product_id=product.id, version="1.0.0"
        )
        doc_service = OpenApiDocumentService(repos.openapi_documents)
        await doc_service.publish(
            organization_id,
            api_product_id=product.id,
            api_version_id=version.id,
            document={"openapi": "3.1.0"},
            now=_now(),
        )
        headers = auth_headers("dev-l@example.com", organization_id=organization_id)
        response = await client.get(
            "/openapi", headers=headers, params={"api_product_id": str(product.id)}
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["document"] == {"openapi": "3.1.0"}

    async def test_graphql_schema_published(
        self,
        client: AsyncClient,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
    ) -> None:
        product = await repos.api_products.create(
            ApiProduct(
                organization_id=organization_id, name="P", product_type=ApiProductType.PUBLIC
            )
        )
        version_service = ApiVersionService(repos.api_versions)
        version = await version_service.create_draft(
            organization_id, api_product_id=product.id, version="1.0.0"
        )
        schema_service = GraphQlSchemaService(repos.graphql_schemas)
        await schema_service.publish(
            organization_id,
            api_product_id=product.id,
            api_version_id=version.id,
            schema_sdl="type Query { hello: String }",
            now=_now(),
        )
        headers = auth_headers("dev-m@example.com", organization_id=organization_id)
        response = await client.get(
            "/graphql/schema", headers=headers, params={"api_product_id": str(product.id)}
        )
        assert response.status_code == HTTP_OK
        assert "hello" in response.json()["data"]["schema_sdl"]


class TestStatisticsAndReports:
    async def test_statistics_requires_admin(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(
            "dev-n@example.com", organization_id=organization_id, roles=["member"]
        )
        response = await client.get("/statistics", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_statistics_success_for_admin(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(
            "dev-o@example.com", organization_id=organization_id, roles=["admin"]
        )
        response = await client.get("/statistics", headers=headers)
        assert response.status_code == HTTP_OK

    async def test_reports_requires_admin(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(
            "dev-p@example.com", organization_id=organization_id, roles=["member"]
        )
        response = await client.get("/reports", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_reports_success_for_admin(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(
            "dev-q@example.com", organization_id=organization_id, roles=["admin"]
        )
        response = await client.get("/reports", headers=headers)
        assert response.status_code == HTTP_OK
