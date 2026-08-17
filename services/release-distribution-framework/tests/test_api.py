"""HTTP integration tests for every REST route, against the real
ASGI app (real PostgreSQL, real JWT verification). Every route
requires an administrator role -- see ``app.api.deps``."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from app.models.channels import ReleaseChannelConfig
from app.models.enums import ReleaseChannelType
from app.models.releases import ReleaseVersion
from app.services.bundle import Repositories
from tests.conftest import (
    HTTP_BAD_REQUEST,
    HTTP_FORBIDDEN,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    AuthHeadersFn,
)


async def _make_channel(
    repos: Repositories, organization_id: uuid.UUID, name: str = "c1"
) -> ReleaseChannelConfig:
    return await repos.release_channels.create(
        ReleaseChannelConfig(
            organization_id=organization_id, name=name, channel_type=ReleaseChannelType.STABLE
        )
    )


async def _make_version(
    repos: Repositories, organization_id: uuid.UUID, *, channel_name: str, label: str
) -> ReleaseVersion:
    channel = await _make_channel(repos, organization_id, name=channel_name)
    return await repos.release_versions.create(
        ReleaseVersion(
            organization_id=organization_id, version_label=label, release_channel_id=channel.id
        )
    )


class TestRbac:
    async def test_no_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get("/releases")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_non_administrator_is_forbidden(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id, roles=["viewer"])
        response = await client.get("/releases", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_administrator_is_authorized(
        self, client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id, roles=["admin"])
        response = await client.get("/releases", headers=headers)
        assert response.status_code == HTTP_OK


class TestReleaseVersionRoutes:
    async def test_create_list_and_get(
        self,
        client: AsyncClient,
        repos: Repositories,
        auth_headers: AuthHeadersFn,
        organization_id: uuid.UUID,
    ) -> None:
        channel = await _make_channel(repos, organization_id, name="api-c1")
        headers = auth_headers(organization_id=organization_id, roles=["admin"])

        create_response = await client.post(
            "/releases",
            headers=headers,
            json={"version_label": "10.0.0", "release_channel_id": str(channel.id)},
        )
        assert create_response.status_code == HTTP_OK
        version_id = create_response.json()["data"]["id"]
        assert create_response.json()["data"]["status"] == "draft"

        list_response = await client.get("/releases", headers=headers)
        assert list_response.status_code == HTTP_OK
        assert any(row["id"] == version_id for row in list_response.json()["data"]["releases"])

        get_response = await client.get(f"/releases/{version_id}", headers=headers)
        assert get_response.status_code == HTTP_OK
        assert get_response.json()["data"]["version_label"] == "10.0.0"

    async def test_publish_walks_full_lifecycle(
        self,
        client: AsyncClient,
        repos: Repositories,
        auth_headers: AuthHeadersFn,
        organization_id: uuid.UUID,
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="api-c2", label="10.1.0")
        headers = auth_headers(organization_id=organization_id, roles=["admin"])

        response = await client.post(
            "/releases/publish", headers=headers, json={"release_version_id": str(version.id)}
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] == "published"
        assert response.json()["data"]["released_at"] is not None

    async def test_publish_is_idempotent_once_already_published(
        self,
        client: AsyncClient,
        repos: Repositories,
        auth_headers: AuthHeadersFn,
        organization_id: uuid.UUID,
    ) -> None:
        """The lifecycle has no failure branch -- a release can always be
        re-attempted, so re-publishing an already-published version is a
        no-op, not an error."""
        version = await _make_version(repos, organization_id, channel_name="api-c3", label="10.2.0")
        headers = auth_headers(organization_id=organization_id, roles=["admin"])

        first = await client.post(
            "/releases/publish", headers=headers, json={"release_version_id": str(version.id)}
        )
        assert first.status_code == HTTP_OK

        second = await client.post(
            "/releases/publish", headers=headers, json={"release_version_id": str(version.id)}
        )
        assert second.status_code == HTTP_OK
        assert second.json()["data"]["status"] == "published"

    async def test_publish_after_archive_is_a_validation_error(
        self,
        client: AsyncClient,
        repos: Repositories,
        auth_headers: AuthHeadersFn,
        organization_id: uuid.UUID,
    ) -> None:
        version = await _make_version(
            repos, organization_id, channel_name="api-c3b", label="10.2.1"
        )
        headers = auth_headers(organization_id=organization_id, roles=["admin"])

        published = await client.post(
            "/releases/publish", headers=headers, json={"release_version_id": str(version.id)}
        )
        assert published.status_code == HTTP_OK

        version = await repos.release_versions.require_by_id(version.id)
        version.status = "archived"
        await repos.release_versions.update(version)

        response = await client.post(
            "/releases/publish", headers=headers, json={"release_version_id": str(version.id)}
        )
        assert response.status_code == HTTP_BAD_REQUEST


class TestReleasePromotionRoute:
    async def test_promote_valid_path_completes_and_moves_channel(
        self,
        client: AsyncClient,
        repos: Repositories,
        auth_headers: AuthHeadersFn,
        organization_id: uuid.UUID,
    ) -> None:
        canary_channel = await repos.release_channels.create(
            ReleaseChannelConfig(
                organization_id=organization_id,
                name="api-c4-canary",
                channel_type=ReleaseChannelType.CANARY,
            )
        )
        version = await repos.release_versions.create(
            ReleaseVersion(
                organization_id=organization_id,
                version_label="11.0.0",
                release_channel_id=canary_channel.id,
            )
        )
        await _make_channel(repos, organization_id, name="api-c4-stable")
        headers = auth_headers(organization_id=organization_id, roles=["admin"])

        response = await client.post(
            "/releases/promote",
            headers=headers,
            json={
                "release_version_id": str(version.id),
                "to_channel_type": "stable",
                "approved_by": "qa-lead",
            },
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] == "completed"

    async def test_promote_invalid_path_rejects(
        self,
        client: AsyncClient,
        repos: Repositories,
        auth_headers: AuthHeadersFn,
        organization_id: uuid.UUID,
    ) -> None:
        channel = await repos.release_channels.create(
            ReleaseChannelConfig(
                organization_id=organization_id,
                name="api-c5",
                channel_type=ReleaseChannelType.DEVELOPMENT,
            )
        )
        version = await repos.release_versions.create(
            ReleaseVersion(
                organization_id=organization_id,
                version_label="11.1.0",
                release_channel_id=channel.id,
            )
        )
        headers = auth_headers(organization_id=organization_id, roles=["admin"])

        response = await client.post(
            "/releases/promote",
            headers=headers,
            json={
                "release_version_id": str(version.id),
                "to_channel_type": "lts",
                "approved_by": "qa-lead",
            },
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["status"] == "rejected"


class TestReadOnlyRoutes:
    async def test_artifacts_downloads_channels_lts_eol_reports_statistics(
        self,
        client: AsyncClient,
        repos: Repositories,
        auth_headers: AuthHeadersFn,
        organization_id: uuid.UUID,
    ) -> None:
        await _make_channel(repos, organization_id, name="api-c6")
        headers = auth_headers(organization_id=organization_id, roles=["admin"])

        for path in (
            "/artifacts",
            "/downloads",
            "/channels",
            "/lts",
            "/eol",
            "/reports",
            "/statistics",
        ):
            response = await client.get(path, headers=headers)
            assert response.status_code == HTTP_OK, path


class TestTenantIsolation:
    async def test_release_created_in_one_org_is_invisible_to_another(
        self,
        client: AsyncClient,
        repos: Repositories,
        auth_headers: AuthHeadersFn,
        organization_id: uuid.UUID,
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="api-c7", label="12.0.0")
        other_org_id = uuid.uuid4()
        other_headers = auth_headers(organization_id=other_org_id, roles=["admin"])

        response = await client.get(f"/releases/{version.id}", headers=other_headers)
        assert response.status_code == HTTP_NOT_FOUND
