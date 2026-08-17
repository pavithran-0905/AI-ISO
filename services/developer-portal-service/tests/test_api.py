"""API integration tests for all 12 REST routes, exercised through the
real FastAPI app (real DB session, real JWT verification)."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import CommunityPost
from app.models.developers import DeveloperBookmark
from app.models.documentation import DocumentationPage
from app.models.enums import CommunityPostType, ContentStatus, SearchContentType
from app.models.knowledge import SearchIndexEntry
from app.models.learning import Tutorial
from app.models.reporting import PortalReport, PortalStatistic
from app.models.samples import SampleProject
from app.services.bundle import build_repositories
from tests.conftest import (
    HTTP_BAD_REQUEST,
    HTTP_CREATED,
    HTTP_FORBIDDEN,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    AuthHeadersFn,
    hours_ago,
    utcnow,
)


class TestHomeRoute:
    async def test_home_reflects_bookmarks(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        repos = build_repositories(db_session)
        await repos.bookmarks.create(
            DeveloperBookmark(
                organization_id=organization_id,
                user_id="tester",
                content_type=SearchContentType.DOCUMENTATION,
                content_id=uuid.uuid4(),
            )
        )
        await db_session.flush()

        response = await client.get(
            "/portal/home", headers=auth_headers("tester", organization_id=organization_id)
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["bookmark_count"] == 1

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.get("/portal/home")
        assert response.status_code == HTTP_UNAUTHORIZED


class TestDocumentationRoute:
    async def test_lists_only_published(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        repos = build_repositories(db_session)
        await repos.documentation_pages.create(
            DocumentationPage(
                organization_id=organization_id,
                slug="pub",
                title="Published",
                status=ContentStatus.PUBLISHED,
                published_at=utcnow(),
            )
        )
        await repos.documentation_pages.create(
            DocumentationPage(organization_id=organization_id, slug="draft", title="Draft")
        )
        await db_session.flush()

        response = await client.get(
            "/portal/documentation", headers=auth_headers("tester", organization_id=organization_id)
        )
        assert response.status_code == HTTP_OK
        body = response.json()["data"]
        assert body["total"] == 1
        assert body["pages"][0]["slug"] == "pub"


class TestTutorialsRoute:
    async def test_lists_published_tutorials(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        repos = build_repositories(db_session)
        await repos.tutorials.create(
            Tutorial(
                organization_id=organization_id,
                slug="t1",
                title="T1",
                status=ContentStatus.PUBLISHED,
                published_at=utcnow(),
            )
        )
        await db_session.flush()

        response = await client.get(
            "/portal/tutorials", headers=auth_headers("tester", organization_id=organization_id)
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1


class TestSamplesRoute:
    async def test_lists_published_samples(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        from app.models.enums import SampleProjectCategory

        repos = build_repositories(db_session)
        await repos.sample_projects.create(
            SampleProject(
                organization_id=organization_id,
                slug="s1",
                title="S1",
                category=SampleProjectCategory.STARTER,
                status=ContentStatus.PUBLISHED,
                published_at=utcnow(),
            )
        )
        await db_session.flush()

        response = await client.get(
            "/portal/samples", headers=auth_headers("tester", organization_id=organization_id)
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1


class TestPluginsRoute:
    async def test_submit_then_list(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("tester", organization_id=organization_id)
        response = await client.post(
            "/portal/plugins",
            headers=headers,
            json={"plugin_name": "my-plugin", "version": "1.0.0", "checksum_sha256": "a" * 64},
        )
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["plugin_name"] == "my-plugin"

        listed = await client.get("/portal/plugins", headers=headers)
        assert listed.status_code == HTTP_OK
        assert listed.json()["data"]["total"] == 1

    async def test_submit_rejects_short_checksum(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        response = await client.post(
            "/portal/plugins",
            headers=auth_headers("tester", organization_id=organization_id),
            json={"plugin_name": "my-plugin", "version": "1.0.0", "checksum_sha256": "short"},
        )
        assert response.status_code == HTTP_BAD_REQUEST


class TestPlaygroundRoute:
    async def test_lists_only_caller_own_sessions(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        from app.models.enums import PlaygroundExampleType
        from app.models.explorer import PlaygroundSession

        repos = build_repositories(db_session)
        await repos.playground_sessions.create(
            PlaygroundSession(
                organization_id=organization_id,
                user_id="tester",
                example_type=PlaygroundExampleType.REST,
                started_at=utcnow(),
                last_active_at=utcnow(),
            )
        )
        await repos.playground_sessions.create(
            PlaygroundSession(
                organization_id=organization_id,
                user_id="someone-else",
                example_type=PlaygroundExampleType.REST,
                started_at=utcnow(),
                last_active_at=utcnow(),
            )
        )
        await db_session.flush()

        response = await client.get(
            "/portal/playground", headers=auth_headers("tester", organization_id=organization_id)
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1


class TestSearchRoute:
    async def test_search_ranks_indexed_content(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        repos = build_repositories(db_session)
        await repos.search_index.create(
            SearchIndexEntry(
                organization_id=organization_id,
                content_type=SearchContentType.DOCUMENTATION,
                content_id=uuid.uuid4(),
                title="Getting Started with Webhooks",
                summary="How to configure webhooks",
                keywords=["webhook", "setup"],
                indexed_at=utcnow(),
            )
        )
        await db_session.flush()

        response = await client.post(
            "/portal/search",
            headers=auth_headers("tester", organization_id=organization_id),
            json={"query": "webhook setup"},
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["total"] == 1


class TestCommunityRoute:
    async def test_create_then_list_visible(
        self, client: AsyncClient, organization_id: uuid.UUID, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers("tester", organization_id=organization_id)
        created = await client.post(
            "/portal/community",
            headers=headers,
            json={
                "post_type": CommunityPostType.QUESTION.value,
                "title": "Q1",
                "body": "body text",
            },
        )
        assert created.status_code == HTTP_CREATED

        listed = await client.get("/portal/community", headers=headers)
        assert listed.status_code == HTTP_OK
        assert listed.json()["data"]["total"] == 1

    async def test_list_excludes_hidden(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        from app.models.enums import ModerationStatus

        repos = build_repositories(db_session)
        await repos.community_posts.create(
            CommunityPost(
                organization_id=organization_id,
                user_id="u1",
                post_type=CommunityPostType.DISCUSSION,
                title="Hidden",
                body="body",
                moderation_status=ModerationStatus.HIDDEN,
            )
        )
        await db_session.flush()

        response = await client.get(
            "/portal/community", headers=auth_headers("tester", organization_id=organization_id)
        )
        assert response.json()["data"]["total"] == 0


class TestStatisticsAndReportsRoutes:
    async def test_statistics_requires_administrator_role(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        repos = build_repositories(db_session)
        await repos.statistics.create(
            PortalStatistic(
                organization_id=organization_id, window_start=hours_ago(1), window_end=utcnow()
            )
        )
        await db_session.flush()

        admin_response = await client.get(
            "/portal/statistics",
            headers=auth_headers("admin-user", organization_id=organization_id, roles=["admin"]),
        )
        assert admin_response.status_code == HTTP_OK
        assert admin_response.json()["data"]["total"] == 1

        forbidden_response = await client.get(
            "/portal/statistics",
            headers=auth_headers(
                "regular-user", organization_id=organization_id, roles=["developer"]
            ),
        )
        assert forbidden_response.status_code == HTTP_FORBIDDEN

    async def test_reports_requires_administrator_role(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        auth_headers: AuthHeadersFn,
    ) -> None:
        from app.models.enums import ReportFormat, ReportKind, ReportStatus

        repos = build_repositories(db_session)
        await repos.reports.create(
            PortalReport(
                organization_id=organization_id,
                kind=ReportKind.PORTAL_USAGE,
                report_format=ReportFormat.JSON,
                title="Usage",
                status=ReportStatus.COMPLETED,
                period_start=hours_ago(1),
                period_end=utcnow(),
            )
        )
        await db_session.flush()

        admin_response = await client.get(
            "/portal/reports",
            headers=auth_headers("admin-user", organization_id=organization_id, roles=["admin"]),
        )
        assert admin_response.status_code == HTTP_OK
        assert admin_response.json()["data"]["total"] == 1

        forbidden_response = await client.get(
            "/portal/reports",
            headers=auth_headers(
                "regular-user", organization_id=organization_id, roles=["developer"]
            ),
        )
        assert forbidden_response.status_code == HTTP_FORBIDDEN
