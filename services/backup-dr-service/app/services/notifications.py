"""Notifications (docs/065 "NOTIFICATIONS", integrating Prompt 025).

**Four of the seven notification kinds have a domain event behind
them** (Backup Failed, Restore Failed, DR Test Failed, Recovery
Completed) and are dispatched by :class:`NotifyingPublisher`, an
``EventPublisher`` that wraps the real one, forwards every event
unchanged, and opportunistically notifies for the subset that warrant
it -- exactly the pattern
``services/observability-platform-service/app/services/notifications.py``
established.

**Three do not** (Replication Failed, Storage Capacity Warning,
Retention Policy Violation): none maps to a domain event this service
publishes, because replication health and storage capacity are read
continuously by a worker rather than announced as discrete facts, and a
retention violation is a policy check with no corresponding event
either. Those three are called directly by the workers that observe
them.
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_BACKUP_FAILED = "backup_dr.backup_failed"
TOPIC_RESTORE_FAILED = "backup_dr.restore_failed"
TOPIC_REPLICATION_FAILED = "backup_dr.replication_failed"
TOPIC_STORAGE_CAPACITY_WARNING = "backup_dr.storage_capacity_warning"
TOPIC_DR_TEST_FAILED = "backup_dr.dr_test_failed"
TOPIC_RECOVERY_COMPLETED = "backup_dr.recovery_completed"
TOPIC_RETENTION_POLICY_VIOLATION = "backup_dr.retention_policy_violation"


class BackupDrNotifier:
    """Sends the seven notification kinds docs/065 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_backup_failed(
        self, *, job_id: str, target_name: str, error_message: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_BACKUP_FAILED,
            notification_type=NotificationType.MONITORING,
            body=f"Backup job {job_id} for {target_name} failed: {error_message}",
            priority=Priority.HIGH,
            variables={"job_id": job_id, "target_name": target_name},
        )

    async def notify_restore_failed(self, *, restore_job_id: str, error_message: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_RESTORE_FAILED,
            notification_type=NotificationType.MONITORING,
            body=f"Restore job {restore_job_id} failed: {error_message}",
            priority=Priority.CRITICAL,
            variables={"restore_job_id": restore_job_id},
        )

    async def notify_replication_failed(
        self, *, target_id: str, destination_ref: str, error_message: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_REPLICATION_FAILED,
            notification_type=NotificationType.MONITORING,
            body=f"Replication for target {target_id} to {destination_ref} failed: {error_message}",
            priority=Priority.HIGH,
            variables={"target_id": target_id, "destination_ref": destination_ref},
        )

    async def notify_storage_capacity_warning(
        self, *, used_fraction: float, threshold_fraction: float
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_STORAGE_CAPACITY_WARNING,
            notification_type=NotificationType.WARNING,
            body=(
                f"Backup storage is at {used_fraction:.0%}, "
                f"past the {threshold_fraction:.0%} threshold."
            ),
            priority=Priority.HIGH,
            variables={"used_fraction": used_fraction},
        )

    async def notify_dr_test_failed(
        self, *, dr_test_id: str, dr_plan_id: str, summary: str | None
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_DR_TEST_FAILED,
            notification_type=NotificationType.MONITORING,
            body=f"DR test {dr_test_id} for plan {dr_plan_id} failed"
            + (f": {summary}" if summary else "."),
            priority=Priority.CRITICAL,
            variables={"dr_test_id": dr_test_id, "dr_plan_id": dr_plan_id},
        )

    async def notify_recovery_completed(self, *, restore_job_id: str, status: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_RECOVERY_COMPLETED,
            notification_type=NotificationType.INFORMATION,
            body=f"Recovery {restore_job_id} completed with status {status}.",
            priority=Priority.NORMAL,
            variables={"restore_job_id": restore_job_id, "status": status},
        )

    async def notify_retention_policy_violation(self, *, archive_id: str, reason: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_RETENTION_POLICY_VIOLATION,
            notification_type=NotificationType.WARNING,
            body=f"Archive {archive_id} could not be purged on schedule: {reason}.",
            priority=Priority.NORMAL,
            variables={"archive_id": archive_id, "reason": reason},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination exactly as if this wrapper were
    not there.
    """

    def __init__(self, inner: EventPublisher, notifier: BackupDrNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "BackupFailed":
            await self._notifier.notify_backup_failed(
                job_id=str(payload.get("job_id", "")),
                target_name=str(payload.get("target_id", "")),
                error_message=str(payload.get("error_message", "")),
            )
        elif event.event_name == "RestoreCompleted":
            status = str(payload.get("status", ""))
            if status == "failed":
                await self._notifier.notify_restore_failed(
                    restore_job_id=str(payload.get("restore_job_id", "")),
                    error_message="see restore job details",
                )
            else:
                await self._notifier.notify_recovery_completed(
                    restore_job_id=str(payload.get("restore_job_id", "")), status=status
                )
        elif event.event_name == "DRTestCompleted" and str(payload.get("status", "")) == "failed":
            await self._notifier.notify_dr_test_failed(
                dr_test_id=str(payload.get("dr_test_id", "")),
                dr_plan_id=str(payload.get("dr_plan_id", "")),
                summary=None,
            )


__all__ = ["BackupDrNotifier", "NotifyingPublisher"]
