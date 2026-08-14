"""Integration tests for background workers, against real PostgreSQL.

Uses real wall-clock time (``datetime.now(UTC)``) throughout, matching
every worker's own internal ``now = datetime.now(UTC)`` -- a fixed
historical constant would fall outside a worker's real query window and
produce tests that pass without the loop body ever executing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models.devices import EdgeDevice
from app.models.enums import (
    ComponentHealthStatus,
    DeviceComponent,
    DeviceHealthStatus,
    EdgeDeviceType,
    ProtocolKind,
    SyncKind,
    SyncStatus,
    UpdateKind,
    UpdateStatus,
    UpdateStrategy,
)
from app.models.operations import EdgeHealth, EdgeProtocol, EdgeSynchronization, EdgeUpdate
from app.models.sites import EdgeSite
from app.services.notifications import EdgeNotifier
from app.workers.health_sweep import HealthSweepWorker
from app.workers.protocol_sweep import ProtocolSweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from app.workers.synchronization_sweep import SynchronizationSweepWorker
from app.workers.update_reconcile import UpdateReconcileWorker


def now() -> datetime:
    return datetime.now(UTC)


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def broadcast(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


async def _noop_publish(event: object) -> None:
    pass


def _site(organization_id: UUID, **kwargs: object) -> EdgeSite:
    defaults: dict[str, object] = {"organization_id": organization_id, "name": "s1"}
    defaults.update(kwargs)
    return EdgeSite(**defaults)


def _device(organization_id: UUID, site_id: UUID, **kwargs: object) -> EdgeDevice:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "site_id": site_id,
        "name": "d1",
        "device_type": EdgeDeviceType.PLC,
    }
    defaults.update(kwargs)
    return EdgeDevice(**defaults)


class TestHealthSweepWorker:
    async def test_tick_marks_stale_device_offline_and_notifies(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(
            _device(
                organization_id,
                site.id,
                is_online=True,
                last_seen_at=now() - timedelta(hours=1),
            )
        )
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        worker = HealthSweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            degraded_threshold=1,
            unhealthy_threshold=2,
            stale_threshold_minutes=15,
        )
        checked = await worker.tick()
        assert checked == 1

        await db_session.refresh(device)
        assert not device.is_online
        assert manager.calls[0]["topic"] == "edge_management.device_offline"

    async def test_tick_refreshes_healthy_device_from_readings(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id, last_seen_at=now()))
        await repos.health.create(
            EdgeHealth(
                organization_id=organization_id,
                device_id=device.id,
                component=DeviceComponent.CPU,
                status=ComponentHealthStatus.OK,
                checked_at=now(),
            )
        )
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        worker = HealthSweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            degraded_threshold=1,
            unhealthy_threshold=2,
            stale_threshold_minutes=15,
        )
        await worker.tick()

        await db_session.refresh(device)
        assert device.health_status == DeviceHealthStatus.HEALTHY

    async def test_tick_no_devices_checks_nothing(self, db_session_factory) -> None:
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        worker = HealthSweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            degraded_threshold=1,
            unhealthy_threshold=2,
            stale_threshold_minutes=15,
        )
        assert await worker.tick() == 0


class TestSynchronizationSweepWorker:
    async def test_tick_times_out_stuck_sync_and_notifies(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id))
        sync = await repos.synchronization.create(
            EdgeSynchronization(
                organization_id=organization_id,
                device_id=device.id,
                sync_kind=SyncKind.FULL,
                status=SyncStatus.IN_PROGRESS,
                started_at=now() - timedelta(hours=2),
            )
        )
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        worker = SynchronizationSweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            stale_threshold_minutes=60,
        )
        timed_out = await worker.tick()
        assert timed_out == 1

        await db_session.refresh(sync)
        assert sync.status == SyncStatus.FAILED
        assert manager.calls[0]["topic"] == "edge_management.synchronization_failed"

    async def test_tick_leaves_recent_sync_alone(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id))
        sync = await repos.synchronization.create(
            EdgeSynchronization(
                organization_id=organization_id,
                device_id=device.id,
                sync_kind=SyncKind.FULL,
                status=SyncStatus.IN_PROGRESS,
                started_at=now(),
            )
        )
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        worker = SynchronizationSweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            stale_threshold_minutes=60,
        )
        assert await worker.tick() == 0
        await db_session.refresh(sync)
        assert sync.status == SyncStatus.IN_PROGRESS

    async def test_tick_no_organizations_times_out_nothing(self, db_session_factory) -> None:
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        worker = SynchronizationSweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            stale_threshold_minutes=60,
        )
        assert await worker.tick() == 0


class TestUpdateReconcileWorker:
    async def test_tick_times_out_stuck_update_and_notifies(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id))
        update = await repos.updates.create(
            EdgeUpdate(
                organization_id=organization_id,
                device_id=device.id,
                update_kind=UpdateKind.FIRMWARE,
                strategy=UpdateStrategy.STAGED,
                from_version="1.0.0",
                to_version="1.1.0",
                status=UpdateStatus.APPLYING,
                started_at=now() - timedelta(hours=2),
            )
        )
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        worker = UpdateReconcileWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            max_skew=2,
            stale_threshold_minutes=60,
        )
        timed_out = await worker.tick()
        assert timed_out == 1

        await db_session.refresh(update)
        assert update.status == UpdateStatus.FAILED
        assert manager.calls[0]["topic"] == "edge_management.ota_failed"

    async def test_tick_no_organizations_times_out_nothing(self, db_session_factory) -> None:
        manager = _RecordingManager()
        notifier = EdgeNotifier(manager)  # type: ignore[arg-type]
        worker = UpdateReconcileWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            max_skew=2,
            stale_threshold_minutes=60,
        )
        assert await worker.tick() == 0


class TestProtocolSweepWorker:
    async def test_tick_reclassifies_stale_connection_as_unknown(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        from app.models.enums import ProtocolHealthStatus

        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id))
        protocol = await repos.protocols.create(
            EdgeProtocol(
                organization_id=organization_id,
                device_id=device.id,
                protocol_kind=ProtocolKind.MODBUS_TCP,
                status=ProtocolHealthStatus.CONNECTED,
                last_checked_at=now() - timedelta(hours=2),
            )
        )
        worker = ProtocolSweepWorker(db_session_factory, stale_after_minutes=30)
        checked = await worker.tick()
        assert checked == 1

        await db_session.refresh(protocol)
        assert protocol.status == ProtocolHealthStatus.UNKNOWN

    async def test_tick_no_devices_checks_nothing(self, db_session_factory) -> None:
        worker = ProtocolSweepWorker(db_session_factory, stale_after_minutes=30)
        assert await worker.tick() == 0


class TestStatisticsRollupWorker:
    async def test_tick_rolls_up_current_window_idempotently(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id, is_online=True))
        assert device.id is not None
        assert site.id is not None

        worker = StatisticsRollupWorker(db_session_factory, window_hours=1)
        rolled_first = await worker.tick()
        rolled_second = await worker.tick()
        assert rolled_first == rolled_second == 1

    async def test_tick_no_organizations_rolls_up_nothing(self, db_session_factory) -> None:
        worker = StatisticsRollupWorker(db_session_factory)
        assert await worker.tick() == 0
