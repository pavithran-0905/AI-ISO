"""Auth edge cases, direct tests for the notification layer, and worker
registration validation."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient
from shared_core.events.base import BaseEvent

from app.events.domain_events import DeveloperLoggedInEvent, DocumentationPublishedEvent
from app.services.notifications import NotifyingPublisher, PortalNotifier
from app.workers.registrar import (
    register_playground_session_expiry_sweep,
    register_plugin_submission_staleness_sweep,
    register_search_index_rebuild,
    register_session_expiry_sweep,
    register_statistics_rollup,
)
from tests.conftest import HTTP_FORBIDDEN, HTTP_OK, HTTP_UNAUTHORIZED, AuthHeadersFn


class TestAuthEdgeCases:
    async def test_malformed_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get(
            "/portal/home", headers={"Authorization": "Bearer not-a-real-jwt"}
        )
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_no_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get("/portal/home")
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_missing_organization_claim_is_forbidden(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=None)
        response = await client.get("/portal/home", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_empty_roles_cannot_administer(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=[])
        response = await client.get("/portal/statistics", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_administrator_role_case_insensitive(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=["  Portal_Admin  "])
        response = await client.get("/portal/statistics", headers=headers)
        assert response.status_code == HTTP_OK


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestPortalNotifier:
    async def test_notify_documentation_updated(self) -> None:
        manager = _RecordingManager()
        notifier = PortalNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_documentation_updated(title="Intro")
        assert manager.calls[0]["topic"] == "developer_portal.documentation_updated"

    async def test_notify_sdk_released(self) -> None:
        manager = _RecordingManager()
        notifier = PortalNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_sdk_released(language="python", version="1.0.0")
        assert manager.calls[0]["topic"] == "developer_portal.sdk_released"

    async def test_notify_plugin_approved(self) -> None:
        manager = _RecordingManager()
        notifier = PortalNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_plugin_approved(plugin_name="my-plugin")
        assert manager.calls[0]["topic"] == "developer_portal.plugin_approved"

    async def test_notify_plugin_rejected(self) -> None:
        manager = _RecordingManager()
        notifier = PortalNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_plugin_rejected(plugin_name="my-plugin", reason="bad checksum")
        assert manager.calls[0]["priority"].name == "HIGH"

    async def test_notify_tutorial_available(self) -> None:
        manager = _RecordingManager()
        notifier = PortalNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_tutorial_available(title="Getting Started")
        assert manager.calls[0]["topic"] == "developer_portal.tutorial_available"

    async def test_notify_ai_recommendation(self) -> None:
        manager = _RecordingManager()
        notifier = PortalNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_ai_recommendation(title="Webhooks Guide")
        assert manager.calls[0]["topic"] == "developer_portal.ai_recommendation"

    async def test_notify_community_reply(self) -> None:
        manager = _RecordingManager()
        notifier = PortalNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_community_reply(post_title="How do I...")
        assert manager.calls[0]["topic"] == "developer_portal.community_reply"

    async def test_notify_security_notice(self) -> None:
        manager = _RecordingManager()
        notifier = PortalNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_security_notice(message="Unusual login activity detected.")
        assert manager.calls[0]["topic"] == "developer_portal.security_notice"
        assert manager.calls[0]["priority"].name == "HIGH"


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        forwarded: list[BaseEvent] = []

        async def _inner(event: BaseEvent) -> None:
            forwarded.append(event)

        manager = _RecordingManager()
        notifier = PortalNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = DeveloperLoggedInEvent(
            source_service="developer-portal-service", payload={"user_id": "u1"}
        )
        await publisher(event)
        assert forwarded == [event]
        assert manager.calls == []  # not a mapped event -- no notification fired

    async def test_documentation_published_fans_out(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = PortalNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = DocumentationPublishedEvent(
            source_service="developer-portal-service",
            payload={"documentation_page_id": "d-1", "slug": "intro", "title": "Intro"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "developer_portal.documentation_updated"


class TestRegistrar:
    def test_rejects_non_positive_interval(self) -> None:
        manager = MagicMock()
        with pytest.raises(ValueError, match="must be positive"):
            register_session_expiry_sweep(manager, lambda job: None, interval_seconds=0)

    def test_registers_session_expiry_sweep(self) -> None:
        manager = MagicMock()
        register_session_expiry_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_playground_session_expiry_sweep(self) -> None:
        manager = MagicMock()
        register_playground_session_expiry_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_search_index_rebuild(self) -> None:
        manager = MagicMock()
        register_search_index_rebuild(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_statistics_rollup(self) -> None:
        manager = MagicMock()
        register_statistics_rollup(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called

    def test_registers_plugin_submission_staleness_sweep(self) -> None:
        manager = MagicMock()
        register_plugin_submission_staleness_sweep(manager, lambda job: None, interval_seconds=60)
        assert manager.register_job.called
