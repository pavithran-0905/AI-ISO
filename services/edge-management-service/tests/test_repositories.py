"""Integration tests for repository query methods, against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from shared_core.exceptions.not_found import NotFoundError

from app.models.devices import EdgeCluster, EdgeDevice, EdgeGateway, EdgeInventory
from app.models.enums import (
    AuditAction,
    ComponentHealthStatus,
    DeviceComponent,
    DeviceLifecycleState,
    EdgeDeviceType,
    ProtocolKind,
    ReportFormat,
    ReportKind,
    ReportStatus,
    SiteHierarchyLevel,
    SyncKind,
    SyncStatus,
    UpdateKind,
    UpdateStatus,
    UpdateStrategy,
)
from app.models.operations import (
    EdgeAiModel,
    EdgeApplication,
    EdgeConfiguration,
    EdgeFirmware,
    EdgeHealth,
    EdgeProtocol,
    EdgeSynchronization,
    EdgeUpdate,
)
from app.models.reporting import EdgeAudit, EdgeReport, EdgeStatistic
from app.models.sites import EdgeLocation, EdgeSite

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _site(organization_id: UUID, *, name: str = "s1") -> EdgeSite:
    return EdgeSite(organization_id=organization_id, name=name)


def _device(organization_id: UUID, site_id: UUID, *, name: str = "d1") -> EdgeDevice:
    return EdgeDevice(
        organization_id=organization_id, site_id=site_id, name=name, device_type=EdgeDeviceType.PLC
    )


class TestEdgeSiteRepository:
    async def test_find_by_name(self, repos, organization_id: UUID) -> None:
        created = await repos.sites.create(_site(organization_id, name="find-me"))
        found = await repos.sites.find_by_name(organization_id, "find-me")
        assert found is not None and found.id == created.id

    async def test_find_by_name_missing_returns_none(self, repos, organization_id: UUID) -> None:
        assert await repos.sites.find_by_name(organization_id, "ghost") is None

    async def test_require_in_org(self, repos, organization_id: UUID) -> None:
        created = await repos.sites.create(_site(organization_id))
        found = await repos.sites.require_in_org(organization_id, created.id)
        assert found.id == created.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.sites.require_in_org(organization_id, uuid4())

    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.sites.create(_site(organization_id))
        found = await repos.sites.list_recent(organization_id)
        assert len(found) == 1

    async def test_list_organization_ids(self, repos, organization_id: UUID) -> None:
        await repos.sites.create(_site(organization_id))
        ids = await repos.sites.list_organization_ids()
        assert organization_id in ids


class TestEdgeLocationRepository:
    async def test_list_for_site_and_children(self, repos, organization_id: UUID) -> None:
        site = await repos.sites.create(_site(organization_id))
        parent = await repos.locations.create(
            EdgeLocation(
                organization_id=organization_id,
                site_id=site.id,
                name="Floor 1",
                hierarchy_level=SiteHierarchyLevel.FLOOR,
            )
        )
        await repos.locations.create(
            EdgeLocation(
                organization_id=organization_id,
                site_id=site.id,
                parent_location_id=parent.id,
                name="Cell A",
                hierarchy_level=SiteHierarchyLevel.CELL,
            )
        )
        for_site = await repos.locations.list_for_site(site.id)
        assert len(for_site) == 2
        children = await repos.locations.list_children(parent.id)
        assert len(children) == 1


class TestEdgeClusterRepository:
    async def test_list_for_site(self, repos, organization_id: UUID) -> None:
        site = await repos.sites.create(_site(organization_id))
        await repos.clusters.create(
            EdgeCluster(organization_id=organization_id, site_id=site.id, name="line-3")
        )
        found = await repos.clusters.list_for_site(site.id)
        assert len(found) == 1


class TestEdgeGatewayRepository:
    async def test_list_for_site_and_organization_ids(self, repos, organization_id: UUID) -> None:
        site = await repos.sites.create(_site(organization_id))
        await repos.gateways.create(
            EdgeGateway(organization_id=organization_id, site_id=site.id, name="gw-1")
        )
        found = await repos.gateways.list_for_site(site.id)
        assert len(found) == 1
        ids = await repos.gateways.list_organization_ids()
        assert organization_id in ids


class TestEdgeDeviceRepository:
    async def test_find_by_name(self, repos, organization_id: UUID) -> None:
        site = await repos.sites.create(_site(organization_id))
        created = await repos.devices.create(_device(organization_id, site.id, name="find-me"))
        found = await repos.devices.find_by_name(organization_id, "find-me")
        assert found is not None and found.id == created.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.devices.require_in_org(organization_id, uuid4())

    async def test_list_recent_filters_by_lifecycle_state(
        self, repos, organization_id: UUID
    ) -> None:
        site = await repos.sites.create(_site(organization_id))
        d1 = _device(organization_id, site.id, name="a")
        d1.lifecycle_state = DeviceLifecycleState.ACTIVE
        d2 = _device(organization_id, site.id, name="b")
        d2.lifecycle_state = DeviceLifecycleState.FAILED
        await repos.devices.create(d1)
        await repos.devices.create(d2)
        found = await repos.devices.list_recent(
            organization_id, lifecycle_state=DeviceLifecycleState.ACTIVE
        )
        assert len(found) == 1

    async def test_list_recent_filters_by_site_and_type(self, repos, organization_id: UUID) -> None:
        site_a = await repos.sites.create(_site(organization_id, name="site-a"))
        site_b = await repos.sites.create(_site(organization_id, name="site-b"))
        await repos.devices.create(_device(organization_id, site_a.id, name="a"))
        await repos.devices.create(_device(organization_id, site_b.id, name="b"))
        found = await repos.devices.list_recent(organization_id, site_id=site_a.id)
        assert len(found) == 1
        found_by_type = await repos.devices.list_recent(
            organization_id, device_type=EdgeDeviceType.PLC
        )
        assert len(found_by_type) == 2

    async def test_list_organization_ids(self, repos, organization_id: UUID) -> None:
        site = await repos.sites.create(_site(organization_id))
        await repos.devices.create(_device(organization_id, site.id))
        ids = await repos.devices.list_organization_ids()
        assert organization_id in ids


class TestEdgeInventoryRepository:
    async def test_latest_for_device_and_list(self, repos, organization_id: UUID) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id))
        await repos.inventory.create(
            EdgeInventory(
                organization_id=organization_id,
                device_id=device.id,
                resource_kind="application",
                resource_count=3,
                collected_at=NOW - timedelta(hours=1),
            )
        )
        await repos.inventory.create(
            EdgeInventory(
                organization_id=organization_id,
                device_id=device.id,
                resource_kind="application",
                resource_count=5,
                collected_at=NOW,
            )
        )
        latest = await repos.inventory.latest_for_device(device.id, resource_kind="application")
        assert latest is not None and latest.resource_count == 5
        found = await repos.inventory.list_for_device(device.id)
        assert len(found) == 2


class TestEdgeConfigurationRepository:
    async def test_active_for_key_and_list(self, repos, organization_id: UUID) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id))
        await repos.configuration.create(
            EdgeConfiguration(
                organization_id=organization_id,
                device_id=device.id,
                config_key="network",
                revision=1,
                is_active=True,
            )
        )
        active = await repos.configuration.active_for_key(device.id, config_key="network")
        assert active is not None
        found = await repos.configuration.list_for_device(device.id)
        assert len(found) == 1


class TestEdgeSynchronizationRepository:
    async def test_latest_completed_and_list_failed(self, repos, organization_id: UUID) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id))
        await repos.synchronization.create(
            EdgeSynchronization(
                organization_id=organization_id,
                device_id=device.id,
                sync_kind=SyncKind.FULL,
                status=SyncStatus.COMPLETED,
                completed_at=NOW,
            )
        )
        await repos.synchronization.create(
            EdgeSynchronization(
                organization_id=organization_id,
                device_id=device.id,
                sync_kind=SyncKind.INCREMENTAL,
                status=SyncStatus.FAILED,
            )
        )
        latest = await repos.synchronization.latest_completed_for_device(device.id)
        assert latest is not None
        failed = await repos.synchronization.list_failed(organization_id)
        assert len(failed) == 1
        found = await repos.synchronization.list_for_device(device.id)
        assert len(found) == 2
        ids = await repos.synchronization.list_organization_ids()
        assert organization_id in ids

    async def test_list_stuck(self, repos, organization_id: UUID) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id))
        await repos.synchronization.create(
            EdgeSynchronization(
                organization_id=organization_id,
                device_id=device.id,
                sync_kind=SyncKind.FULL,
                status=SyncStatus.IN_PROGRESS,
                started_at=NOW - timedelta(hours=2),
            )
        )
        stuck = await repos.synchronization.list_stuck(
            organization_id, before=NOW - timedelta(minutes=30)
        )
        assert len(stuck) == 1


class TestEdgeUpdateRepository:
    async def test_list_for_device_and_in_progress(self, repos, organization_id: UUID) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id))
        await repos.updates.create(
            EdgeUpdate(
                organization_id=organization_id,
                device_id=device.id,
                update_kind=UpdateKind.FIRMWARE,
                strategy=UpdateStrategy.STAGED,
                from_version="1.0.0",
                to_version="1.1.0",
                status=UpdateStatus.APPLYING,
                started_at=NOW - timedelta(hours=2),
            )
        )
        await repos.updates.create(
            EdgeUpdate(
                organization_id=organization_id,
                device_id=device.id,
                update_kind=UpdateKind.FIRMWARE,
                strategy=UpdateStrategy.STAGED,
                from_version="0.9.0",
                to_version="1.0.0",
                status=UpdateStatus.COMPLETED,
            )
        )
        for_device = await repos.updates.list_for_device(device.id)
        assert len(for_device) == 2
        in_progress = await repos.updates.list_in_progress(organization_id)
        assert len(in_progress) == 1
        stuck = await repos.updates.list_in_progress(
            organization_id, started_before=NOW - timedelta(minutes=30)
        )
        assert len(stuck) == 1
        ids = await repos.updates.list_organization_ids()
        assert organization_id in ids


class TestEdgeFirmwareRepository:
    async def test_find_by_type_and_version_and_list_for_type(
        self, repos, organization_id: UUID
    ) -> None:
        await repos.firmware.create(
            EdgeFirmware(
                organization_id=organization_id,
                device_type=EdgeDeviceType.PLC,
                version_label="2.0.0",
                skew_rank=6,
            )
        )
        await repos.firmware.create(
            EdgeFirmware(
                organization_id=organization_id,
                device_type=EdgeDeviceType.PLC,
                version_label="1.0.0",
                skew_rank=5,
            )
        )
        found = await repos.firmware.find_by_type_and_version(EdgeDeviceType.PLC, "2.0.0")
        assert found is not None
        for_type = await repos.firmware.list_for_type(EdgeDeviceType.PLC)
        assert [f.version_label for f in for_type] == ["1.0.0", "2.0.0"]


class TestEdgeApplicationRepository:
    async def test_list_for_device(self, repos, organization_id: UUID) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id))
        await repos.applications.create(
            EdgeApplication(
                organization_id=organization_id,
                device_id=device.id,
                name="collector",
                version_label="1.0.0",
            )
        )
        found = await repos.applications.list_for_device(device.id)
        assert len(found) == 1


class TestEdgeAiModelRepository:
    async def test_list_for_device(self, repos, organization_id: UUID) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id))
        await repos.ai_models.create(
            EdgeAiModel(
                organization_id=organization_id,
                device_id=device.id,
                name="defect-detector",
                version_label="1.0.0",
            )
        )
        found = await repos.ai_models.list_for_device(device.id)
        assert len(found) == 1


class TestEdgeProtocolRepository:
    async def test_list_for_device_and_organization_ids(self, repos, organization_id: UUID) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id))
        await repos.protocols.create(
            EdgeProtocol(
                organization_id=organization_id,
                device_id=device.id,
                protocol_kind=ProtocolKind.MODBUS_TCP,
            )
        )
        found = await repos.protocols.list_for_device(device.id)
        assert len(found) == 1
        ids = await repos.protocols.list_organization_ids()
        assert organization_id in ids


class TestEdgeHealthRepository:
    async def test_latest_per_component(self, repos, organization_id: UUID) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id))
        await repos.health.create(
            EdgeHealth(
                organization_id=organization_id,
                device_id=device.id,
                component=DeviceComponent.CPU,
                status=ComponentHealthStatus.OK,
                checked_at=NOW - timedelta(hours=1),
            )
        )
        await repos.health.create(
            EdgeHealth(
                organization_id=organization_id,
                device_id=device.id,
                component=DeviceComponent.CPU,
                status=ComponentHealthStatus.WARNING,
                checked_at=NOW,
            )
        )
        await repos.health.create(
            EdgeHealth(
                organization_id=organization_id,
                device_id=device.id,
                component=DeviceComponent.MEMORY,
                status=ComponentHealthStatus.OK,
                checked_at=NOW,
            )
        )
        latest = await repos.health.latest_per_component(device.id)
        assert len(latest) == 2
        cpu_reading = next(r for r in latest if r.component == DeviceComponent.CPU)
        assert cpu_reading.status == ComponentHealthStatus.WARNING

    async def test_list_for_device(self, repos, organization_id: UUID) -> None:
        site = await repos.sites.create(_site(organization_id))
        device = await repos.devices.create(_device(organization_id, site.id))
        await repos.health.create(
            EdgeHealth(
                organization_id=organization_id,
                device_id=device.id,
                component=DeviceComponent.MEMORY,
                status=ComponentHealthStatus.OK,
                checked_at=NOW,
            )
        )
        found = await repos.health.list_for_device(device.id)
        assert len(found) == 1


class TestEdgeStatisticRepository:
    async def test_find_window_and_list_range(self, repos, organization_id: UUID) -> None:
        await repos.statistics.create(
            EdgeStatistic(
                organization_id=organization_id,
                window_start=NOW,
                window_end=NOW + timedelta(hours=1),
            )
        )
        found = await repos.statistics.find_window(organization_id, window_start=NOW)
        assert found is not None
        in_range = await repos.statistics.list_range(
            organization_id, since=NOW - timedelta(hours=1)
        )
        assert len(in_range) == 1
        ids = await repos.statistics.list_organization_ids()
        assert organization_id in ids

    async def test_find_window_missing_returns_none(self, repos, organization_id: UUID) -> None:
        assert await repos.statistics.find_window(organization_id, window_start=NOW) is None


class TestEdgeReportRepository:
    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.reports.create(
            EdgeReport(
                organization_id=organization_id,
                kind=ReportKind.FLEET,
                report_format=ReportFormat.JSON,
                title="Fleet Report",
                status=ReportStatus.COMPLETED,
            )
        )
        recent = await repos.reports.list_recent(organization_id, status=ReportStatus.COMPLETED)
        assert len(recent) == 1
        by_kind = await repos.reports.list_recent(organization_id, kind=ReportKind.FLEET)
        assert len(by_kind) == 1


class TestEdgeAuditRepository:
    async def test_list_recent_and_for_entity(self, repos, organization_id: UUID) -> None:
        entity_id = uuid4()
        await repos.audit.create(
            EdgeAudit(
                organization_id=organization_id,
                action=AuditAction.DEVICE_REGISTERED,
                entity_type="edge_device",
                entity_id=entity_id,
                occurred_at=NOW,
            )
        )
        found = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert len(found) == 1
        for_entity = await repos.audit.list_for_entity("edge_device", entity_id)
        assert len(for_entity) == 1

    async def test_list_recent_excludes_before_since(self, repos, organization_id: UUID) -> None:
        await repos.audit.create(
            EdgeAudit(
                organization_id=organization_id,
                action=AuditAction.DEVICE_REGISTERED,
                entity_type="edge_device",
                occurred_at=NOW - timedelta(days=10),
            )
        )
        found = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert found == []
