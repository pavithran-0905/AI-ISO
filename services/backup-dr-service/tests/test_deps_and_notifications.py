"""Auth edge cases and direct tests for the notification layer."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from httpx import AsyncClient
from shared_core.enums.notification_type import NotificationType
from shared_core.events.base import BaseEvent

from app.events.domain_events import (
    BackupFailedEvent,
    DRTestCompletedEvent,
    RecoveryValidatedEvent,
    RestoreCompletedEvent,
)
from app.services.notifications import BackupDrNotifier, NotifyingPublisher
from tests.conftest import HTTP_FORBIDDEN, HTTP_OK, HTTP_UNAUTHORIZED, AuthHeadersFn


class TestAuthEdgeCases:
    async def test_malformed_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get(
            "/backup/jobs", headers={"Authorization": "Bearer not-a-real-jwt"}
        )
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_missing_organization_claim_is_forbidden(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=None)
        response = await client.get("/backup/jobs", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_empty_roles_cannot_administer(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=[])
        response = await client.post(
            "/backup/schedules",
            json={"target_id": str(uuid4()), "backup_type": "full", "frequency": "daily"},
            headers=headers,
        )
        assert response.status_code == HTTP_FORBIDDEN

    async def test_administrator_role_case_insensitive(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=["  Backup_Admin  "])
        response = await client.get("/backup/jobs", headers=headers)
        assert response.status_code == HTTP_OK


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestBackupDrNotifier:
    async def test_notify_backup_failed(self) -> None:
        manager = _RecordingManager()
        notifier = BackupDrNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_backup_failed(
            job_id="job-1", target_name="db-1", error_message="disk full"
        )
        assert manager.calls[0]["topic"] == "backup_dr.backup_failed"

    async def test_notify_restore_failed(self) -> None:
        manager = _RecordingManager()
        notifier = BackupDrNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_restore_failed(restore_job_id="r-1", error_message="boom")
        assert manager.calls[0]["priority"].name == "CRITICAL"

    async def test_notify_replication_failed(self) -> None:
        manager = _RecordingManager()
        notifier = BackupDrNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_replication_failed(
            target_id="t-1", destination_ref="dest-1", error_message="unreachable"
        )
        assert manager.calls[0]["topic"] == "backup_dr.replication_failed"

    async def test_notify_storage_capacity_warning(self) -> None:
        manager = _RecordingManager()
        notifier = BackupDrNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_storage_capacity_warning(used_fraction=0.92, threshold_fraction=0.9)
        assert "92%" in manager.calls[0]["body"]

    async def test_notify_dr_test_failed_with_summary(self) -> None:
        manager = _RecordingManager()
        notifier = BackupDrNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_dr_test_failed(
            dr_test_id="dt-1", dr_plan_id="dp-1", summary="RPO missed"
        )
        assert "RPO missed" in manager.calls[0]["body"]

    async def test_notify_dr_test_failed_without_summary(self) -> None:
        manager = _RecordingManager()
        notifier = BackupDrNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_dr_test_failed(dr_test_id="dt-1", dr_plan_id="dp-1", summary=None)
        assert manager.calls[0]["body"].endswith("failed.")

    async def test_notify_recovery_completed(self) -> None:
        manager = _RecordingManager()
        notifier = BackupDrNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_recovery_completed(restore_job_id="r-1", status="completed")
        assert manager.calls[0]["notification_type"] is NotificationType.INFORMATION

    async def test_notify_retention_policy_violation(self) -> None:
        manager = _RecordingManager()
        notifier = BackupDrNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_retention_policy_violation(archive_id="a-1", reason="legal hold")
        assert manager.calls[0]["topic"] == "backup_dr.retention_policy_violation"


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        forwarded: list[BaseEvent] = []

        async def _inner(event: BaseEvent) -> None:
            forwarded.append(event)

        manager = _RecordingManager()
        notifier = BackupDrNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = RecoveryValidatedEvent(
            source_service="backup-dr-service", organization_id=uuid4(), payload={}
        )
        await publisher(event)
        assert forwarded == [event]
        assert manager.calls == []

    async def test_backup_failed_triggers_notification(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = BackupDrNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = BackupFailedEvent(
            source_service="backup-dr-service",
            organization_id=uuid4(),
            payload={"job_id": "j-1", "target_id": "t-1", "error_message": "boom"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "backup_dr.backup_failed"

    async def test_restore_completed_failed_status_notifies_failure(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = BackupDrNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = RestoreCompletedEvent(
            source_service="backup-dr-service",
            organization_id=uuid4(),
            payload={"restore_job_id": "r-1", "status": "failed"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "backup_dr.restore_failed"

    async def test_restore_completed_success_status_notifies_recovery(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = BackupDrNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = RestoreCompletedEvent(
            source_service="backup-dr-service",
            organization_id=uuid4(),
            payload={"restore_job_id": "r-1", "status": "validated"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "backup_dr.recovery_completed"

    async def test_dr_test_completed_failed_notifies(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = BackupDrNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = DRTestCompletedEvent(
            source_service="backup-dr-service",
            organization_id=uuid4(),
            payload={"dr_test_id": "dt-1", "dr_plan_id": "dp-1", "status": "failed"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "backup_dr.dr_test_failed"

    async def test_dr_test_completed_passed_does_not_notify(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = BackupDrNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = DRTestCompletedEvent(
            source_service="backup-dr-service",
            organization_id=uuid4(),
            payload={"dr_test_id": "dt-1", "dr_plan_id": "dp-1", "status": "passed"},
        )
        await publisher(event)
        assert manager.calls == []
