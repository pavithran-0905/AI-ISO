"""API-level tests for all 11 docs/077 REST routes, exercised through
a real ASGI transport against real PostgreSQL.

See ``test_repositories.py``'s own module docstring for why every
model/enum starting with ``Test`` is imported under an alias here too.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from app.models.enums import CoverageType, QualityGateType, SecurityTestType
from app.models.enums import TestType as SuiteTypeEnum
from app.models.security_chaos import SecurityResult
from app.models.test_definitions import TestCase as CaseModel
from app.models.test_definitions import TestSuite as SuiteModel
from app.services.bundle import Repositories
from tests.conftest import (
    HTTP_FORBIDDEN,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    AuthHeadersFn,
)


class TestTestSuitesRoute:
    async def test_list_requires_administrator(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id, roles=["member"])
        response = await client.get("/qa/test-suites", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_list_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.get("/qa/test-suites")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_list_returns_suites(
        self,
        client: AsyncClient,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
        organization_id: uuid.UUID,
    ) -> None:
        await repos.test_suites.create(
            SuiteModel(
                organization_id=organization_id, name="api-suite", test_type=SuiteTypeEnum.UNIT
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/qa/test-suites", headers=headers)
        assert response.status_code == HTTP_OK
        body = response.json()["data"]
        assert body["total"] == 1
        assert body["suites"][0]["name"] == "api-suite"


class TestTestRunsRoute:
    async def test_start_run(
        self,
        client: AsyncClient,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
        organization_id: uuid.UUID,
    ) -> None:
        suite = await repos.test_suites.create(
            SuiteModel(
                organization_id=organization_id, name="run-suite", test_type=SuiteTypeEnum.UNIT
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/qa/test-runs", headers=headers, json={"test_suite_id": str(suite.id)}
        )
        assert response.status_code == HTTP_OK
        body = response.json()["data"]
        assert body["status"] == "running"
        assert body["test_suite_id"] == str(suite.id)


class TestResultsRoute:
    async def test_list_results(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/qa/results", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestCoverageRoute:
    async def test_list_coverage(
        self,
        client: AsyncClient,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
        organization_id: uuid.UUID,
    ) -> None:
        from app.models.coverage import CoverageReport

        await repos.coverage_reports.create(
            CoverageReport(
                organization_id=organization_id, coverage_type=CoverageType.UNIT, percentage=91.0
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/qa/coverage", headers=headers)
        assert response.status_code == HTTP_OK
        body = response.json()["data"]
        assert body["total"] == 1
        assert body["reports"][0]["percentage"] == 91.0


class TestPerformanceRoute:
    async def test_list_performance(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/qa/performance", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestSecurityRoute:
    async def test_list_security(
        self,
        client: AsyncClient,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
        organization_id: uuid.UUID,
    ) -> None:
        await repos.security_results.create(
            SecurityResult(
                organization_id=organization_id,
                security_type=SecurityTestType.OWASP_TOP_10,
                status="passed",
                findings_count=0,
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/qa/security", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1


class TestBenchmarksRoute:
    async def test_list_benchmarks(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/qa/benchmarks", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestQualityGatesRoute:
    async def test_create_and_list(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        create_response = await client.post(
            "/qa/quality-gates",
            headers=headers,
            json={
                "name": "coverage-gate",
                "gate_type": QualityGateType.MINIMUM_COVERAGE.value,
                "threshold": 90.0,
            },
        )
        assert create_response.status_code == HTTP_OK
        assert create_response.json()["data"]["name"] == "coverage-gate"

        list_response = await client.get("/qa/quality-gates", headers=headers)
        assert list_response.status_code == HTTP_OK
        assert list_response.json()["data"]["total"] == 1


class TestReportsRoute:
    async def test_list_reports(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/qa/reports", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestStatisticsRoute:
    async def test_list_statistics(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/qa/statistics", headers=headers)
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
        await repos.test_suites.create(
            SuiteModel(organization_id=organization_id, name="mine", test_type=SuiteTypeEnum.UNIT)
        )
        other_org = uuid.uuid4()
        headers = auth_headers(organization_id=other_org)
        response = await client.get("/qa/test-suites", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestCaseModelSanity:
    def test_case_model_importable(self) -> None:
        assert CaseModel is not None
