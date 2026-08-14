"""Auth edge cases and direct tests for the notification layer."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from httpx import AsyncClient
from shared_core.enums.notification_type import NotificationType
from shared_core.events.base import BaseEvent

from app.events.domain_events import (
    BudgetThresholdExceededEvent,
    CloudAccountRegisteredEvent,
    DriftDetectedEvent,
)
from app.services.notifications import CloudNotifier, NotifyingPublisher
from tests.conftest import HTTP_FORBIDDEN, HTTP_OK, HTTP_UNAUTHORIZED, AuthHeadersFn


class TestAuthEdgeCases:
    async def test_malformed_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get(
            "/cloud/accounts", headers={"Authorization": "Bearer not-a-real-jwt"}
        )
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_missing_organization_claim_is_forbidden(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=None)
        response = await client.get("/cloud/accounts", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_empty_roles_cannot_administer(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=[])
        response = await client.post(
            "/cloud/accounts",
            json={
                "provider_id": str(uuid4()),
                "external_account_id": "123",
                "name": "a1",
                "credential_ref": "ref",
            },
            headers=headers,
        )
        assert response.status_code == HTTP_FORBIDDEN

    async def test_administrator_role_case_insensitive(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=["  Cloud_Admin  "])
        response = await client.get("/cloud/accounts", headers=headers)
        assert response.status_code == HTTP_OK


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestCloudNotifier:
    async def test_notify_budget_exceeded(self) -> None:
        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_budget_exceeded(
            budget_id="b-1", status="critical", current_spend=95.0
        )
        assert manager.calls[0]["topic"] == "cloud_management.budget_exceeded"

    async def test_notify_idle_resource_detected(self) -> None:
        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_idle_resource_detected(resource_id="r-1", utilization_fraction=0.02)
        assert manager.calls[0]["topic"] == "cloud_management.idle_resource_detected"

    async def test_notify_compliance_violation(self) -> None:
        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_compliance_violation(
            account_id="a-1", framework="cis", status="non_compliant"
        )
        assert manager.calls[0]["topic"] == "cloud_management.compliance_violation"

    async def test_notify_provisioning_failed(self) -> None:
        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_provisioning_failed(resource_id="r-1", detail="quota exceeded")
        assert manager.calls[0]["priority"].name == "CRITICAL"

    async def test_notify_credential_expiring(self) -> None:
        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_credential_expiring(
            account_id="a-1", expires_at="2026-01-01T00:00:00Z"
        )
        assert manager.calls[0]["topic"] == "cloud_management.credential_expiring"

    async def test_notify_drift_detected(self) -> None:
        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_drift_detected(resource_id="r-1", severity="high")
        assert manager.calls[0]["topic"] == "cloud_management.drift_detected"

    async def test_notify_optimization_available(self) -> None:
        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_optimization_available(account_id="a-1", idle_resource_count=3)
        assert manager.calls[0]["notification_type"] is NotificationType.INFORMATION


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        forwarded: list[BaseEvent] = []

        async def _inner(event: BaseEvent) -> None:
            forwarded.append(event)

        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = CloudAccountRegisteredEvent(source_service="cloud-management-service", payload={})
        await publisher(event)
        assert forwarded == [event]
        assert manager.calls == []

    async def test_budget_threshold_exceeded_triggers_notification(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = BudgetThresholdExceededEvent(
            source_service="cloud-management-service",
            payload={"budget_id": "b-1", "status": "critical", "current_spend": 95.0},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "cloud_management.budget_exceeded"

    async def test_drift_detected_triggers_notification(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = DriftDetectedEvent(
            source_service="cloud-management-service",
            payload={"resource_id": "r-1", "severity": "high"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "cloud_management.drift_detected"
