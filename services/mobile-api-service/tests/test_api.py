"""Integration tests for the 13 REST endpoints, against the real app
through its actual lifespan (real PostgreSQL, Redis; RabbitMQ event
publishing goes through the real broker too, since these tests exercise
``app.state.publish_event`` end-to-end)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.models.configuration import MobileAppVersion, MobileConfiguration
from app.models.enums import (
    QrPurpose,
    ReleaseChannel,
    ReportFormat,
    ReportKind,
    ReportStatus,
)
from app.models.notifications import MobileNotification
from app.models.reporting import MobileReport
from app.services.bundle import Repositories
from app.services.qr import QrService
from tests.conftest import (
    HTTP_BAD_REQUEST,
    HTTP_CONFLICT,
    HTTP_CREATED,
    HTTP_FORBIDDEN,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    AuthHeadersFn,
)


def _now() -> datetime:
    return datetime.now(UTC)


class TestLoginLogout:
    async def test_login_registers_device_and_returns_token(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-1", organization_id=organization_id)
        response = await client.post(
            "/mobile/login",
            headers=headers,
            json={
                "device_identifier": "device-a",
                "platform": "android",
                "device_model": "Pixel 9",
                "os_version": "15",
                "app_version": "1.0.0",
                "auth_method": "jwt",
            },
        )
        assert response.status_code == HTTP_CREATED, response.text
        data = response.json()["data"]
        assert data["is_new_device"] is True
        assert len(data["mobile_token"]) >= 32

    async def test_login_refused_for_jailbroken_device(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-2", organization_id=organization_id)
        response = await client.post(
            "/mobile/login",
            headers=headers,
            json={
                "device_identifier": "device-jb",
                "platform": "ios",
                "auth_method": "jwt",
                "is_jailbroken": True,
            },
        )
        assert response.status_code == HTTP_FORBIDDEN

    async def test_login_requires_token(self, client: AsyncClient) -> None:
        response = await client.post(
            "/mobile/login",
            json={"device_identifier": "d", "platform": "android", "auth_method": "jwt"},
        )
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_logout_success(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-3", organization_id=organization_id)
        await client.post(
            "/mobile/login",
            headers=headers,
            json={"device_identifier": "device-b", "platform": "android", "auth_method": "jwt"},
        )
        response = await client.post(
            "/mobile/logout", headers=headers, json={"device_identifier": "device-b"}
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] == "revoked"

    async def test_logout_unknown_device_is_404(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-4", organization_id=organization_id)
        response = await client.post(
            "/mobile/logout", headers=headers, json={"device_identifier": "ghost"}
        )
        assert response.status_code == HTTP_NOT_FOUND

    async def test_logout_no_active_session_is_404(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-5", organization_id=organization_id)
        await client.post(
            "/mobile/register-device",
            headers=headers,
            json={"device_identifier": "device-c", "platform": "android"},
        )
        response = await client.post(
            "/mobile/logout", headers=headers, json={"device_identifier": "device-c"}
        )
        assert response.status_code == HTTP_NOT_FOUND


class TestRegisterDevice:
    async def test_register_device(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-6", organization_id=organization_id)
        response = await client.post(
            "/mobile/register-device",
            headers=headers,
            json={"device_identifier": "device-d", "platform": "flutter", "app_version": "3.0.0"},
        )
        assert response.status_code == HTTP_CREATED
        data = response.json()["data"]
        assert data["trust_status"] == "pending"
        assert data["platform"] == "flutter"


class TestProfile:
    async def test_get_profile_lazily_creates(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-7", organization_id=organization_id)
        response = await client.get("/mobile/profile", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["user_id"] == "user-7"

    async def test_put_profile_updates(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-8", organization_id=organization_id)
        await client.get("/mobile/profile", headers=headers)
        response = await client.put(
            "/mobile/profile",
            headers=headers,
            json={
                "display_name": "Ada Lovelace",
                "locale": "en-GB",
                "preferences": {"dark_mode": True},
            },
        )
        assert response.status_code == HTTP_OK
        data = response.json()["data"]
        assert data["display_name"] == "Ada Lovelace"
        assert data["preferences"] == {"dark_mode": True}


class TestSync:
    async def test_create_sync_enqueues_job(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-9", organization_id=organization_id)
        await client.post(
            "/mobile/register-device",
            headers=headers,
            json={"device_identifier": "device-e", "platform": "android"},
        )
        response = await client.post(
            "/mobile/sync",
            headers=headers,
            json={
                "device_identifier": "device-e",
                "sync_type": "delta",
                "items": [
                    {
                        "action_type": "update_note",
                        "payload": {"note_id": "n1"},
                        "client_updated_at": _now().isoformat(),
                    }
                ],
            },
        )
        assert response.status_code == HTTP_CREATED
        data = response.json()["data"]
        assert data["status"] == "pending"
        assert data["item_count"] == 1

    async def test_create_sync_unknown_device_is_404(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-10", organization_id=organization_id)
        response = await client.post(
            "/mobile/sync",
            headers=headers,
            json={"device_identifier": "ghost", "sync_type": "manual", "items": []},
        )
        assert response.status_code == HTTP_NOT_FOUND


class TestConfiguration:
    async def test_get_configuration_resolves_global_and_platform_entries(
        self,
        client: AsyncClient,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
    ) -> None:
        await repos.configuration.create(
            MobileConfiguration(
                organization_id=organization_id, key="feature_x", value={"on": True}
            )
        )
        headers = auth_headers("user-11", organization_id=organization_id)
        response = await client.get(
            "/mobile/configuration",
            headers=headers,
            params={"platform": "android", "environment": "production"},
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["entries"]["feature_x"] == {"on": True}


class TestNotifications:
    async def test_list_notifications(
        self,
        client: AsyncClient,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
    ) -> None:
        headers = auth_headers("user-12", organization_id=organization_id)
        register = await client.post(
            "/mobile/register-device",
            headers=headers,
            json={"device_identifier": "device-f", "platform": "android"},
        )
        device_id = uuid.UUID(register.json()["data"]["id"])
        await repos.notifications.create(
            MobileNotification(
                organization_id=organization_id, device_id=device_id, title="Hi", body="There"
            )
        )
        response = await client.get(
            "/mobile/notifications", headers=headers, params={"device_identifier": "device-f"}
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1

    async def test_list_notifications_unknown_device_is_404(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-13", organization_id=organization_id)
        response = await client.get(
            "/mobile/notifications", headers=headers, params={"device_identifier": "ghost"}
        )
        assert response.status_code == HTTP_NOT_FOUND


class TestPushRegister:
    async def test_register_push_token(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-14", organization_id=organization_id)
        await client.post(
            "/mobile/register-device",
            headers=headers,
            json={"device_identifier": "device-g", "platform": "ios"},
        )
        response = await client.post(
            "/mobile/push/register",
            headers=headers,
            json={"device_identifier": "device-g", "platform": "apns", "token_value": "abc123"},
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["status"] == "active"

    async def test_register_push_token_unknown_device_is_404(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-15", organization_id=organization_id)
        response = await client.post(
            "/mobile/push/register",
            headers=headers,
            json={"device_identifier": "ghost", "platform": "fcm", "token_value": "x"},
        )
        assert response.status_code == HTTP_NOT_FOUND


class TestQrRegister:
    async def test_qr_register_success(
        self,
        client: AsyncClient,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
        cache_framework: object,
    ) -> None:
        qr_service = QrService(cache_framework.manager)  # type: ignore[attr-defined]
        token = await qr_service.issue(
            organization_id, purpose=QrPurpose.DEVICE_ENROLLMENT, ttl_minutes=15, now=_now()
        )
        headers = auth_headers("user-16", organization_id=organization_id)
        response = await client.post(
            "/mobile/qr/register",
            headers=headers,
            json={"qr_token": token, "device_identifier": "device-h", "platform": "android"},
        )
        assert response.status_code == HTTP_CREATED

    async def test_qr_register_invalid_token_is_conflict(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-17", organization_id=organization_id)
        response = await client.post(
            "/mobile/qr/register",
            headers=headers,
            json={
                "qr_token": "does-not-exist",
                "device_identifier": "device-i",
                "platform": "android",
            },
        )
        assert response.status_code == HTTP_CONFLICT

    async def test_qr_register_wrong_organization_is_forbidden(
        self,
        client: AsyncClient,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
        cache_framework: object,
    ) -> None:
        qr_service = QrService(cache_framework.manager)  # type: ignore[attr-defined]
        token = await qr_service.issue(
            uuid.uuid4(), purpose=QrPurpose.DEVICE_ENROLLMENT, ttl_minutes=15, now=_now()
        )
        headers = auth_headers("user-18", organization_id=organization_id)
        response = await client.post(
            "/mobile/qr/register",
            headers=headers,
            json={"qr_token": token, "device_identifier": "device-j", "platform": "android"},
        )
        assert response.status_code == HTTP_FORBIDDEN

    async def test_qr_register_wrong_purpose_is_conflict(
        self,
        client: AsyncClient,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
        cache_framework: object,
    ) -> None:
        qr_service = QrService(cache_framework.manager)  # type: ignore[attr-defined]
        token = await qr_service.issue(
            organization_id, purpose=QrPurpose.ORGANIZATION_JOIN, ttl_minutes=15, now=_now()
        )
        headers = auth_headers("user-19", organization_id=organization_id)
        response = await client.post(
            "/mobile/qr/register",
            headers=headers,
            json={"qr_token": token, "device_identifier": "device-k", "platform": "android"},
        )
        assert response.status_code == HTTP_CONFLICT


class TestVersionPolicy:
    async def test_get_version_policy(
        self,
        client: AsyncClient,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
    ) -> None:
        await repos.app_versions.create(
            MobileAppVersion(
                organization_id=organization_id,
                platform="android",
                version_label="3.0.0",
                release_channel=ReleaseChannel.STABLE,
                minimum_version_label="2.0.0",
                recommended_version_label="3.0.0",
                is_forced_upgrade=False,
                released_at=_now(),
            )
        )
        headers = auth_headers("user-20", organization_id=organization_id)
        response = await client.get(
            "/mobile/version",
            headers=headers,
            params={"platform": "android", "current_version": "1.0.0"},
        )
        assert response.status_code == HTTP_OK
        data = response.json()["data"]
        assert data["is_below_minimum"] is True
        assert data["is_update_recommended"] is True

    async def test_get_version_policy_missing_is_404(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-21", organization_id=organization_id)
        response = await client.get(
            "/mobile/version",
            headers=headers,
            params={"platform": "ios", "current_version": "1.0.0"},
        )
        assert response.status_code == HTTP_NOT_FOUND

    async def test_get_version_policy_bad_current_version_is_422(
        self,
        client: AsyncClient,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
    ) -> None:
        await repos.app_versions.create(
            MobileAppVersion(
                organization_id=organization_id,
                platform="react_native",
                version_label="1.0.0",
                minimum_version_label="1.0.0",
                recommended_version_label="1.0.0",
                released_at=_now(),
            )
        )
        headers = auth_headers("user-22", organization_id=organization_id)
        response = await client.get(
            "/mobile/version",
            headers=headers,
            params={"platform": "react_native", "current_version": "not-a-version"},
        )
        assert response.status_code == HTTP_BAD_REQUEST


class TestStatisticsAndReports:
    async def test_statistics_requires_admin(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-23", organization_id=organization_id, roles=["member"])
        response = await client.get("/mobile/statistics", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_statistics_success_for_admin(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-24", organization_id=organization_id, roles=["admin"])
        response = await client.get("/mobile/statistics", headers=headers)
        assert response.status_code == HTTP_OK
        assert "daily_active_users" in response.json()["data"]

    async def test_reports_requires_admin(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-25", organization_id=organization_id, roles=["member"])
        response = await client.get("/mobile/reports", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_reports_success_for_admin(
        self,
        client: AsyncClient,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
        repos: Repositories,
    ) -> None:
        await repos.reports.create(
            MobileReport(
                organization_id=organization_id,
                kind=ReportKind.DEVICE,
                report_format=ReportFormat.JSON,
                title="Devices",
                status=ReportStatus.COMPLETED,
                period_start=_now() - timedelta(days=1),
                period_end=_now(),
            )
        )
        headers = auth_headers("user-26", organization_id=organization_id, roles=["admin"])
        response = await client.get("/mobile/reports", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1


class TestNoOrganizationClaim:
    async def test_missing_organization_claim_is_forbidden(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("user-27")
        response = await client.get("/mobile/profile", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN
