"""API-level tests for all 11 docs/079 REST routes, exercised through
a real ASGI transport against real PostgreSQL."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from app.models.enums import CisBenchmark, HardeningTargetType
from app.models.hardening_definitions import HardeningProfile
from app.services.bundle import Repositories
from tests.conftest import HTTP_FORBIDDEN, HTTP_OK, HTTP_UNAUTHORIZED, AuthHeadersFn


class TestHardeningRoute:
    async def test_list_requires_administrator(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id, roles=["member"])
        response = await client.get("/hardening", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_list_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.get("/hardening")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_list_returns_profiles(
        self,
        client: AsyncClient,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
        organization_id: uuid.UUID,
    ) -> None:
        await repos.hardening_profiles.create(
            HardeningProfile(
                organization_id=organization_id,
                name="api-profile",
                target_type=HardeningTargetType.API,
                benchmark=CisBenchmark.CUSTOM,
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/hardening", headers=headers)
        assert response.status_code == HTTP_OK
        body = response.json()["data"]
        assert body["total"] == 1
        assert body["profiles"][0]["name"] == "api-profile"


class TestHardeningRunRoute:
    async def test_start_run(
        self,
        client: AsyncClient,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
        organization_id: uuid.UUID,
    ) -> None:
        profile = await repos.hardening_profiles.create(
            HardeningProfile(
                organization_id=organization_id,
                name="run-profile",
                target_type=HardeningTargetType.OS,
                benchmark=CisBenchmark.LINUX_CIS,
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/hardening/run", headers=headers, json={"hardening_profile_id": str(profile.id)}
        )
        assert response.status_code == HTTP_OK
        body = response.json()["data"]
        assert body["status"] == "running"
        assert body["hardening_profile_id"] == str(profile.id)


class TestHardeningResultsRoute:
    async def test_list_results(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/hardening/results", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestSecurityFindingsRoute:
    async def test_list_findings(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/security/findings", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestVulnerabilitiesRoute:
    async def test_list_vulnerabilities(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/vulnerabilities", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestCertificationsRoute:
    async def test_create_and_list(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        create_response = await client.post(
            "/certifications",
            headers=headers,
            json={
                "name": "core-platform",
                "hardening_rate": 1.0,
                "compliance_rate": 1.0,
                "readiness_rate": 1.0,
            },
        )
        assert create_response.status_code == HTTP_OK
        assert create_response.json()["data"]["status"] == "granted"

        list_response = await client.get("/certifications", headers=headers)
        assert list_response.status_code == HTTP_OK
        assert list_response.json()["data"]["total"] == 1


class TestComplianceRoute:
    async def test_list_compliance(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/compliance", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0


class TestProductionReadinessRoute:
    async def test_compute_readiness(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/production-readiness", headers=headers)
        assert response.status_code == HTTP_OK
        body = response.json()["data"]
        # No hardening/operational-readiness/DR signals yet (honest zero each),
        # but compliance is vacuously 1.0 with nothing evaluated -- (0+1+0+0)/4.
        assert body["score"] == 0.25
        assert body["is_ready"] is False


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
    async def test_profiles_scoped_to_caller_organization(
        self,
        client: AsyncClient,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
        organization_id: uuid.UUID,
    ) -> None:
        await repos.hardening_profiles.create(
            HardeningProfile(
                organization_id=organization_id,
                name="mine",
                target_type=HardeningTargetType.OS,
                benchmark=CisBenchmark.LINUX_CIS,
            )
        )
        other_org = uuid.uuid4()
        headers = auth_headers(organization_id=other_org)
        response = await client.get("/hardening", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 0
