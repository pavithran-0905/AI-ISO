"""End-to-end API tests against the real FastAPI app (real Postgres/Redis)."""

from __future__ import annotations

from uuid import UUID, uuid4

from httpx import AsyncClient

from app.models.devices import EdgeDevice
from app.models.enums import EdgeDeviceType
from app.models.sites import EdgeSite
from tests.conftest import (
    HTTP_CONFLICT,
    HTTP_CREATED,
    HTTP_FORBIDDEN,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    AuthHeadersFn,
)


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
        response = await client.get("/edge/devices")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_non_admin_cannot_register_site(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id, roles=["viewer"])
        response = await client.post("/edge/sites", json={"name": "s1"}, headers=headers)
        assert response.status_code == HTTP_FORBIDDEN


async def _create_site(repos, organization_id: UUID, **kwargs: object) -> EdgeSite:
    defaults: dict[str, object] = {"organization_id": organization_id, "name": "s1"}
    defaults.update(kwargs)
    return await repos.sites.create(EdgeSite(**defaults))


async def _create_device(
    repos, organization_id: UUID, site_id: UUID, **kwargs: object
) -> EdgeDevice:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "site_id": site_id,
        "name": "d1",
        "device_type": EdgeDeviceType.PLC,
    }
    defaults.update(kwargs)
    return await repos.devices.create(EdgeDevice(**defaults))


class TestSiteRoutes:
    async def test_list_sites_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/edge/sites", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["sites"] == []

    async def test_create_site(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/edge/sites",
            json={"name": "Plant 1", "business_unit": "manufacturing"},
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["name"] == "Plant 1"


class TestDeviceCrudRoutes:
    async def test_list_devices_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/edge/devices", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["devices"] == []

    async def test_create_and_get_device(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        site = await _create_site(repos, organization_id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/edge/devices",
            json={
                "site_id": str(site.id),
                "name": "plc-1",
                "device_type": "plc",
                "credential_ref": "enrollment-token",
            },
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        device_id = response.json()["data"]["id"]

        get_response = await client.get(f"/edge/devices/{device_id}", headers=headers)
        assert get_response.status_code == HTTP_OK
        assert get_response.json()["data"]["name"] == "plc-1"

    async def test_create_device_refused_on_empty_credential(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        site = await _create_site(repos, organization_id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/edge/devices",
            json={
                "site_id": str(site.id),
                "name": "plc-1",
                "device_type": "plc",
                "credential_ref": "   ",
            },
            headers=headers,
        )
        assert response.status_code == HTTP_CONFLICT

    async def test_get_missing_device_is_not_authorized_range(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get(f"/edge/devices/{uuid4()}", headers=headers)
        assert response.status_code >= HTTP_FORBIDDEN

    async def test_update_device(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        site = await _create_site(repos, organization_id)
        device = await _create_device(repos, organization_id, site.id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.put(
            f"/edge/devices/{device.id}",
            json={"description": "updated description"},
            headers=headers,
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["id"] == str(device.id)

    async def test_delete_device_starts_retiring(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        site = await _create_site(repos, organization_id)
        device = await _create_device(repos, organization_id, site.id, lifecycle_state="active")
        headers = auth_headers(organization_id=organization_id)
        response = await client.delete(f"/edge/devices/{device.id}", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["lifecycle_state"] == "retiring"

    async def test_delete_device_invalid_transition_is_conflict(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        """A retired (terminal) device cannot be retired again -- the
        route must surface that refusal as a clear 409, not an
        unhandled 500."""
        site = await _create_site(repos, organization_id)
        device = await _create_device(repos, organization_id, site.id, lifecycle_state="retired")
        headers = auth_headers(organization_id=organization_id)
        response = await client.delete(f"/edge/devices/{device.id}", headers=headers)
        assert response.status_code == HTTP_CONFLICT


class TestProvisionRoute:
    async def test_provision_advances_lifecycle(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        site = await _create_site(repos, organization_id)
        device = await _create_device(repos, organization_id, site.id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            f"/edge/devices/{device.id}/provision",
            json={"target_state": "registered"},
            headers=headers,
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["lifecycle_state"] == "registered"

    async def test_provision_invalid_transition_is_conflict(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        site = await _create_site(repos, organization_id)
        device = await _create_device(repos, organization_id, site.id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            f"/edge/devices/{device.id}/provision",
            json={"target_state": "active"},
            headers=headers,
        )
        assert response.status_code == HTTP_CONFLICT


class TestSyncRoute:
    async def test_sync_completes_synchronously(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        site = await _create_site(repos, organization_id)
        device = await _create_device(repos, organization_id, site.id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            f"/edge/devices/{device.id}/sync", json={"sync_kind": "full"}, headers=headers
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["status"] == "completed"


class TestUpdateRoute:
    async def test_update_refused_without_catalog_entries(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        site = await _create_site(repos, organization_id)
        device = await _create_device(repos, organization_id, site.id, firmware_version="1.0.0")
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            f"/edge/devices/{device.id}/update",
            json={"to_version": "1.0.0"},
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        data = response.json()["data"]
        assert data["update_id"] is None
        assert data["refusal"] == "same_version"


class TestRemoteAccessRoute:
    async def test_remote_access_refused_when_offline(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        site = await _create_site(repos, organization_id)
        device = await _create_device(repos, organization_id, site.id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            f"/edge/devices/{device.id}/remote-access",
            json={"reason": "diagnostics"},
            headers=headers,
        )
        assert response.status_code == HTTP_OK
        assert not response.json()["data"]["granted"]

    async def test_remote_access_granted_when_online(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        site = await _create_site(repos, organization_id)
        device = await _create_device(repos, organization_id, site.id, is_online=True)
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            f"/edge/devices/{device.id}/remote-access",
            json={"reason": "diagnostics"},
            headers=headers,
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["granted"]


class TestFleetWideRoutes:
    async def test_fleet_health(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        site = await _create_site(repos, organization_id)
        await _create_device(repos, organization_id, site.id)
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/edge/health", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1

    async def test_fleet_statistics_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/edge/statistics", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["windows"] == []

    async def test_fleet_reports_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/edge/reports", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["reports"] == []
