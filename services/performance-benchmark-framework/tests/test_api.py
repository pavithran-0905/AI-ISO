"""API-level tests for all 11 docs/078 REST routes, exercised through
a real ASGI transport against real PostgreSQL."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from app.models.benchmark_definitions import BenchmarkSuite
from app.models.enums import BenchmarkType
from app.services.bundle import Repositories
from tests.conftest import HTTP_FORBIDDEN, HTTP_OK, HTTP_UNAUTHORIZED, AuthHeadersFn


class TestBenchmarksRoute:
    async def test_list_requires_administrator(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id, roles=["member"])
        response = await client.get("/benchmarks", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_list_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.get("/benchmarks")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_create_and_list_and_get(
        self,
        client: AsyncClient,
        auth_headers: AuthHeadersFn,
        organization_id: uuid.UUID,
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        create_response = await client.post(
            "/benchmarks", headers=headers, json={"name": "api-suite", "benchmark_type": "api"}
        )
        assert create_response.status_code == HTTP_OK
        suite_id = create_response.json()["data"]["id"]

        list_response = await client.get("/benchmarks", headers=headers)
        assert list_response.status_code == HTTP_OK
        assert list_response.json()["data"]["total"] == 1

        get_response = await client.get(f"/benchmarks/{suite_id}", headers=headers)
        assert get_response.status_code == HTTP_OK
        assert get_response.json()["data"]["name"] == "api-suite"


class TestBenchmarkRunRoute:
    async def test_start_run(
        self,
        client: AsyncClient,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
        organization_id: uuid.UUID,
    ) -> None:
        suite = await repos.benchmark_suites.create(
            BenchmarkSuite(
                organization_id=organization_id, name="run-suite", benchmark_type=BenchmarkType.API
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/benchmarks/run", headers=headers, json={"benchmark_suite_id": str(suite.id)}
        )
        assert response.status_code == HTTP_OK
        body = response.json()["data"]
        assert body["status"] == "running"
        assert body["benchmark_suite_id"] == str(suite.id)


class TestPerformanceRoute:
    async def test_list_performance(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/performance", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestPerformanceRegressionsRoute:
    async def test_list_regressions(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/performance/regressions", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestCapacityRoute:
    async def test_list_capacity(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/capacity", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestOptimizationRoute:
    async def test_list_optimization(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/optimization", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestSlosRoute:
    async def test_list_slos(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/slos", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestReportsRoute:
    async def test_list_reports(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/reports", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestStatisticsRoute:
    async def test_list_statistics(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/statistics", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestTenantIsolation:
    async def test_suites_scoped_to_caller_organization(
        self,
        client: AsyncClient,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
        organization_id: uuid.UUID,
    ) -> None:
        await repos.benchmark_suites.create(
            BenchmarkSuite(
                organization_id=organization_id, name="mine", benchmark_type=BenchmarkType.API
            )
        )
        other_org = uuid.uuid4()
        headers = auth_headers(organization_id=other_org)
        response = await client.get("/benchmarks", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0
