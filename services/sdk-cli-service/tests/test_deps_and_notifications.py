"""Auth edge cases and direct tests for the notification layer."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from httpx import AsyncClient
from shared_core.enums.notification_type import NotificationType
from shared_core.events.base import BaseEvent

from app.events.domain_events import CliReleasedEvent, SdkReleasedEvent
from app.services.notifications import NotifyingPublisher, SdkCliNotifier
from tests.conftest import HTTP_FORBIDDEN, HTTP_OK, HTTP_UNAUTHORIZED, AuthHeadersFn


class TestAuthEdgeCases:
    async def test_malformed_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get("/sdk", headers={"Authorization": "Bearer not-a-real-jwt"})
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_missing_organization_claim_is_forbidden(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=None)
        response = await client.get("/sdk", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_empty_roles_cannot_administer(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=[])
        response = await client.post(
            "/cli/update",
            json={"from_version": "1.0.0", "to_version": "1.1.0", "succeeded": True},
            headers=headers,
        )
        assert response.status_code == HTTP_FORBIDDEN

    async def test_administrator_role_case_insensitive(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=["  Sdk_Admin  "])
        response = await client.get("/sdk", headers=headers)
        assert response.status_code == HTTP_OK


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestSdkCliNotifier:
    async def test_notify_new_sdk_release(self) -> None:
        manager = _RecordingManager()
        notifier = SdkCliNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_new_sdk_release(language="python", version="1.0.0")
        assert manager.calls[0]["topic"] == "sdk_cli.new_sdk_release"

    async def test_notify_cli_update_available(self) -> None:
        manager = _RecordingManager()
        notifier = SdkCliNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_cli_update_available(current_version="1.0.0", latest_version="1.1.0")
        assert manager.calls[0]["topic"] == "sdk_cli.cli_update_available"

    async def test_notify_plugin_update_available(self) -> None:
        manager = _RecordingManager()
        notifier = SdkCliNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_plugin_update_available(
            plugin_name="observability", latest_version="2.0.0"
        )
        assert manager.calls[0]["topic"] == "sdk_cli.plugin_update_available"

    async def test_notify_authentication_failure(self) -> None:
        manager = _RecordingManager()
        notifier = SdkCliNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_authentication_failure(profile_name="default", auth_method="api_key")
        assert manager.calls[0]["priority"].name == "HIGH"

    async def test_notify_breaking_api_changes(self) -> None:
        manager = _RecordingManager()
        notifier = SdkCliNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_breaking_api_changes(language="python", version="2.0.0")
        assert manager.calls[0]["topic"] == "sdk_cli.breaking_api_changes"

    async def test_notify_deprecation_notice(self) -> None:
        manager = _RecordingManager()
        notifier = SdkCliNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_deprecation_notice(
            kind="SDK", version="1.0.0", deprecated_at="2026-01-01T00:00:00Z"
        )
        assert manager.calls[0]["notification_type"] is NotificationType.WARNING


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        forwarded: list[BaseEvent] = []

        async def _inner(event: BaseEvent) -> None:
            forwarded.append(event)

        manager = _RecordingManager()
        notifier = SdkCliNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = SdkReleasedEvent(
            source_service="sdk-cli-service",
            payload={"sdk_release_id": "r-1", "language": "python", "version": "1.0.0"},
        )
        await publisher(event)
        assert forwarded == [event]
        assert manager.calls[0]["topic"] == "sdk_cli.new_sdk_release"

    async def test_breaking_changes_fans_out_to_second_notification(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = SdkCliNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = SdkReleasedEvent(
            source_service="sdk-cli-service",
            payload={
                "sdk_release_id": "r-1",
                "language": "python",
                "version": "2.0.0",
                "breaking_changes": True,
            },
        )
        await publisher(event)
        topics = [call["topic"] for call in manager.calls]
        assert "sdk_cli.new_sdk_release" in topics
        assert "sdk_cli.breaking_api_changes" in topics

    async def test_non_breaking_release_does_not_fan_out(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = SdkCliNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = SdkReleasedEvent(
            source_service="sdk-cli-service",
            payload={"sdk_release_id": "r-1", "language": "python", "version": "1.1.0"},
        )
        await publisher(event)
        assert len(manager.calls) == 1

    async def test_unmapped_event_does_not_notify(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = SdkCliNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = CliReleasedEvent(
            source_service="sdk-cli-service", payload={"cli_version_id": "v-1", "version": "1.0.0"}
        )
        await publisher(event)
        assert manager.calls == []
