"""Maintenance window scheduling, approval, and lifecycle transitions.

Wires ``app.maintenance.engine``'s pure transition table and overlap
check onto the repository that persists maintenance windows, notifying
``notify_maintenance_scheduled`` on creation and publishing
``MaintenanceStarted``/``MaintenanceCompleted`` on those transitions.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import MaintenanceCompletedEvent, MaintenanceStartedEvent
from app.maintenance.engine import TransitionResult, validate_transition, windows_overlap
from app.models.enums import MaintenanceKind, MaintenanceStatus
from app.models.maintenance import MaintenanceWindow
from app.repositories.maintenance import MaintenanceWindowRepository
from app.services.notifications import AdminNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "administration-portal-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class MaintenanceConflictError(Exception):
    """Raised when a new maintenance window overlaps an existing
    scheduled/approved/in-progress one."""

    def __init__(self, conflicting: MaintenanceWindow) -> None:
        super().__init__(f"Overlaps existing maintenance window {conflicting.id!s}.")
        self.conflicting = conflicting


class MaintenanceService:
    def __init__(
        self,
        repo: MaintenanceWindowRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: AdminNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def schedule(
        self,
        organization_id: UUID,
        *,
        title: str,
        kind: MaintenanceKind,
        starts_at: datetime,
        ends_at: datetime,
        read_only_mode: bool = False,
    ) -> MaintenanceWindow:
        """Schedule a new maintenance window.

        Raises:
            MaintenanceConflictError: If it overlaps any existing
                non-terminal window.
        """
        active_windows = await self._repo.list_recent(organization_id, limit=500)
        for existing in active_windows:
            if existing.status in (
                MaintenanceStatus.COMPLETED,
                MaintenanceStatus.CANCELLED,
            ):
                continue
            if windows_overlap(starts_at, ends_at, existing.starts_at, existing.ends_at):
                raise MaintenanceConflictError(existing)

        window = await self._repo.create(
            MaintenanceWindow(
                organization_id=organization_id,
                title=title,
                kind=kind,
                starts_at=starts_at,
                ends_at=ends_at,
                read_only_mode=read_only_mode,
            )
        )
        if self._notifier is not None:
            await self._notifier.notify_maintenance_scheduled(
                maintenance_window_id=str(window.id), starts_at=starts_at.isoformat()
            )
        return window

    async def approve(
        self, window: MaintenanceWindow, *, approved_by: str, now: datetime
    ) -> MaintenanceWindow:
        window = await self.transition(window, target=MaintenanceStatus.APPROVED)
        window.approved_by = approved_by
        window.approved_at = now
        return await self._repo.update(window)

    async def transition(
        self, window: MaintenanceWindow, *, target: MaintenanceStatus
    ) -> MaintenanceWindow:
        """Move *window* to *target*, raising
        :class:`TransitionRefusedError` if the transition is not
        allowed."""
        result = validate_transition(window.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        window.status = target
        await self._repo.update(window)

        if target == MaintenanceStatus.IN_PROGRESS:
            await self._publish(
                MaintenanceStartedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=window.organization_id,
                    payload={"maintenance_window_id": str(window.id), "title": window.title},
                )
            )
        elif target == MaintenanceStatus.COMPLETED:
            await self._publish(
                MaintenanceCompletedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=window.organization_id,
                    payload={"maintenance_window_id": str(window.id)},
                )
            )
        return window


__all__ = ["MaintenanceConflictError", "MaintenanceService", "TransitionRefusedError"]
