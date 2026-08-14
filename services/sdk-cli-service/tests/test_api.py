"""End-to-end API tests against the real FastAPI app (real Postgres/Redis)."""

from __future__ import annotations

from uuid import UUID

from httpx import AsyncClient

from app.models.enums import PluginStatus, SdkLanguage
from app.models.sdk import SdkLanguageCatalog
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
        response = await client.get("/sdk")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_non_admin_cannot_generate_sdk(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id, roles=["viewer"])
        response = await client.post(
            "/sdk/generate",
            json={
                "language": "python",
                "version": "1.0.0",
                "api_compatibility_version": "1.0.0",
                "models": [{"class_name": "User", "fields": [{"name": "id", "type_name": "uuid"}]}],
            },
            headers=headers,
        )
        assert response.status_code == HTTP_FORBIDDEN


class TestSdkRoutes:
    async def test_list_sdk_languages_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/sdk", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["languages"] == []

    async def test_list_sdk_languages(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        await repos.sdk_languages.create(
            SdkLanguageCatalog(
                organization_id=organization_id, language=SdkLanguage.PYTHON, display_name="Python"
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/sdk", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1

    async def test_list_sdk_releases_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/sdk/releases", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["releases"] == []

    async def test_list_sdk_downloads_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/sdk/downloads", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["downloads"] == []

    async def test_generate_sdk(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/sdk/generate",
            json={
                "language": "python",
                "version": "1.0.0",
                "api_compatibility_version": "1.0.0",
                "models": [{"class_name": "User", "fields": [{"name": "id", "type_name": "uuid"}]}],
                "release_notes": "Initial release",
            },
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        data = response.json()["data"]
        assert len(data["artifacts"]) == 1
        assert "class User:" in data["artifacts"][0]["source"]

    async def test_generate_sdk_invalid_field_type_is_unprocessable(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/sdk/generate",
            json={
                "language": "python",
                "version": "1.0.0",
                "api_compatibility_version": "1.0.0",
                "models": [
                    {"class_name": "User", "fields": [{"name": "id", "type_name": "not_a_type"}]}
                ],
            },
            headers=headers,
        )
        assert response.status_code == HTTP_CONFLICT or response.status_code >= 400

    async def test_get_sdk_reports_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/sdk/reports", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["reports"] == []

    async def test_get_sdk_statistics_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/sdk/statistics", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["windows"] == []


class TestCliRoutes:
    async def test_list_cli_versions_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/cli", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["versions"] == []

    async def test_list_cli_releases_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/cli/releases", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["versions"] == []

    async def test_update_cli_succeeded(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/cli/update",
            json={"from_version": "1.0.0", "to_version": "1.1.0", "succeeded": True},
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["status"] == "applied"

    async def test_update_cli_failed(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/cli/update",
            json={"from_version": "1.0.0", "to_version": "1.1.0", "succeeded": False},
            headers=headers,
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["status"] == "failed"

    async def test_install_then_remove_plugin(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        install_response = await client.post(
            "/cli/plugins/install",
            json={"name": "observability", "version": "1.0.0", "checksum_sha256": "abc"},
            headers=headers,
        )
        assert install_response.status_code == HTTP_CREATED
        assert install_response.json()["data"]["status"] == "installed"

        remove_response = await client.post(
            "/cli/plugins/remove", json={"name": "observability"}, headers=headers
        )
        assert remove_response.status_code == HTTP_OK
        assert remove_response.json()["data"]["status"] == "removed"

    async def test_remove_unknown_plugin_is_conflict(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/cli/plugins/remove", json={"name": "does-not-exist"}, headers=headers
        )
        assert response.status_code == HTTP_CONFLICT

    async def test_install_already_installed_plugin_is_conflict(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID, repos
    ) -> None:
        from app.models.cli import CliPlugin

        await repos.cli_plugins.create(
            CliPlugin(
                organization_id=organization_id,
                name="observability",
                version_label="1.0.0",
                status=PluginStatus.INSTALLED,
                checksum_sha256="abc",
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.post(
            "/cli/plugins/install",
            json={"name": "observability", "version": "1.0.0", "checksum_sha256": "abc"},
            headers=headers,
        )
        assert response.status_code == HTTP_CONFLICT

    async def test_get_cli_statistics_empty(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/cli/statistics", headers=headers)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["windows"] == []
