"""Auth edge cases and direct tests for the notification layer."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from httpx import AsyncClient
from shared_core.enums.notification_type import NotificationType
from shared_core.events.base import BaseEvent

from app.events.domain_events import (
    ClusterRegisteredEvent,
    ClusterUpgradedEvent,
    PolicyAppliedEvent,
)
from app.services.notifications import FleetNotifier, NotifyingPublisher
from tests.conftest import HTTP_FORBIDDEN, HTTP_OK, HTTP_UNAUTHORIZED, AuthHeadersFn


class TestAuthEdgeCases:
    async def test_malformed_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get("/clusters", headers={"Authorization": "Bearer not-a-real-jwt"})
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_missing_organization_claim_is_forbidden(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=None)
        response = await client.get("/clusters", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_empty_roles_cannot_administer(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=[])
        response = await client.post(
            "/clusters",
            json={"name": "c1", "cluster_type": "kubernetes"},
            headers=headers,
        )
        assert response.status_code == HTTP_FORBIDDEN

    async def test_administrator_role_case_insensitive(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=["  Cluster_Admin  "])
        response = await client.get("/clusters", headers=headers)
        assert response.status_code == HTTP_OK


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestFleetNotifier:
    async def test_notify_cluster_offline(self) -> None:
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_cluster_offline(cluster_id="c-1", cluster_name="prod-1")
        assert manager.calls[0]["topic"] == "multi_cluster.cluster_offline"

    async def test_notify_upgrade_failed(self) -> None:
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_upgrade_failed(
            cluster_id="c-1", upgrade_id="u-1", error_message="node drain timeout"
        )
        assert manager.calls[0]["priority"].name == "CRITICAL"

    async def test_notify_policy_violation(self) -> None:
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_policy_violation(
            cluster_id="c-1", policy_id="p-1", policy_name="no-root"
        )
        assert manager.calls[0]["topic"] == "multi_cluster.policy_violation"

    async def test_notify_compliance_failure(self) -> None:
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_compliance_failure(
            cluster_id="c-1", framework="cis_kubernetes", status="non_compliant"
        )
        assert manager.calls[0]["topic"] == "multi_cluster.compliance_failure"

    async def test_notify_capacity_warning(self) -> None:
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_capacity_warning(
            cluster_id="c-1", resource_kind="cpu", utilization_fraction=0.92
        )
        assert "92%" in manager.calls[0]["body"]

    async def test_notify_cluster_registered(self) -> None:
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_cluster_registered(cluster_id="c-1", cluster_name="prod-1")
        assert manager.calls[0]["notification_type"] is NotificationType.INFORMATION

    async def test_notify_maintenance_scheduled(self) -> None:
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_maintenance_scheduled(
            cluster_id="c-1", scheduled_at="2026-01-01T00:00:00Z"
        )
        assert manager.calls[0]["topic"] == "multi_cluster.maintenance_scheduled"


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        forwarded: list[BaseEvent] = []

        async def _inner(event: BaseEvent) -> None:
            forwarded.append(event)

        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = PolicyAppliedEvent(source_service="multi-cluster-management-service", payload={})
        await publisher(event)
        assert forwarded == [event]
        assert manager.calls == []

    async def test_cluster_registered_triggers_notification(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = ClusterRegisteredEvent(
            source_service="multi-cluster-management-service",
            payload={"cluster_id": "c-1", "name": "prod-1"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "multi_cluster.cluster_registered"

    async def test_cluster_upgraded_failed_triggers_notification(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = ClusterUpgradedEvent(
            source_service="multi-cluster-management-service",
            payload={"cluster_id": "c-1", "upgrade_id": "u-1", "status": "failed"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "multi_cluster.upgrade_failed"

    async def test_cluster_upgraded_completed_does_not_notify(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = ClusterUpgradedEvent(
            source_service="multi-cluster-management-service",
            payload={"cluster_id": "c-1", "upgrade_id": "u-1", "status": "completed"},
        )
        await publisher(event)
        assert manager.calls == []
