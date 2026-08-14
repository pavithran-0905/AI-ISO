"""Integration tests for the service layer, against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.devices.engine import TransitionRefusal
from app.models.devices import EdgeDevice
from app.models.enums import (
    ApplicationDeploymentStrategy,
    AuditAction,
    ConflictResolutionStrategy,
    DeviceLifecycleState,
    EdgeDeviceType,
    ProtocolKind,
    ReportFormat,
    ReportKind,
    SiteHierarchyLevel,
    SyncKind,
    UpdateKind,
    UpdateStrategy,
)
from app.models.operations import EdgeFirmware
from app.models.sites import EdgeSite
from app.services.applications import ApplicationService
from app.services.audit import AuditService
from app.services.configuration import ConfigurationService, RollbackRefusedError
from app.services.devices import (
    CredentialRefusedError,
    EdgeClusterService,
    EdgeDeviceService,
    EdgeGatewayService,
    TransitionRefusedError,
)
from app.services.digital_twins import DigitalTwinService
from app.services.edge_ai import EdgeAiModelService, PromotionRefusedError
from app.services.firmware import FirmwareService
from app.services.health import HealthService
from app.services.inventory import InventoryService
from app.services.ota import OTAService, UpdatePlanRefusedError
from app.services.protocols import ProtocolService
from app.services.reports import ReportService
from app.services.sites import EdgeLocationService, EdgeSiteService
from app.services.statistics import StatisticsService
from app.services.synchronization import SynchronizationService

NOW = datetime(2026, 6, 1, tzinfo=UTC)


async def _site(repos, organization_id: UUID, **kwargs: object) -> EdgeSite:
    defaults: dict[str, object] = {"organization_id": organization_id, "name": "s1"}
    defaults.update(kwargs)
    return await repos.sites.create(EdgeSite(**defaults))


async def _device(repos, organization_id: UUID, site_id: UUID, **kwargs: object) -> EdgeDevice:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "site_id": site_id,
        "name": "d1",
        "device_type": EdgeDeviceType.PLC,
    }
    defaults.update(kwargs)
    return await repos.devices.create(EdgeDevice(**defaults))


class TestAuditService:
    async def test_record_creates_entry(self, repos, organization_id: UUID) -> None:
        service = AuditService(repos.audit)
        entry = await service.record(
            organization_id,
            action=AuditAction.ADMINISTRATIVE,
            entity_type="edge_device",
            entity_id=uuid4(),
            occurred_at=NOW,
            summary="test entry",
        )
        assert entry.id is not None

    async def test_record_defaults_details_to_empty_dict(
        self, repos, organization_id: UUID
    ) -> None:
        service = AuditService(repos.audit)
        entry = await service.record(
            organization_id,
            action=AuditAction.ADMINISTRATIVE,
            entity_type="edge_device",
            entity_id=None,
            occurred_at=NOW,
        )
        assert entry.details == {}


class TestEdgeSiteService:
    async def test_register_site_publishes_event_and_audits(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        audit = AuditService(repos.audit)
        service = EdgeSiteService(repos.sites, publish=publisher, audit=audit)
        site = await service.register_site(
            organization_id,
            name="Plant 1",
            business_unit="manufacturing",
            description=None,
            geo_latitude=None,
            geo_longitude=None,
            actor_id="tester",
            now=NOW,
        )
        assert site.id is not None
        assert publisher.names() == ["EdgeSiteRegistered"]
        trail = await repos.audit.list_recent(organization_id, since=NOW - timedelta(minutes=1))
        assert len(trail) == 1


class TestEdgeLocationService:
    async def test_create_location(self, repos, organization_id: UUID) -> None:
        site = await _site(repos, organization_id)
        service = EdgeLocationService(repos.locations)
        location = await service.create_location(
            organization_id,
            site_id=site.id,
            parent_location_id=None,
            name="Floor 1",
            hierarchy_level=SiteHierarchyLevel.FLOOR,
        )
        assert location.id is not None


class TestEdgeClusterService:
    async def test_create_cluster(self, repos, organization_id: UUID) -> None:
        site = await _site(repos, organization_id)
        service = EdgeClusterService(repos.clusters)
        cluster = await service.create_cluster(
            organization_id, site_id=site.id, name="line-3", description=None
        )
        assert cluster.id is not None


class TestEdgeGatewayService:
    async def test_register_gateway(self, repos, organization_id: UUID) -> None:
        site = await _site(repos, organization_id)
        service = EdgeGatewayService(repos.gateways)
        gateway = await service.register_gateway(
            organization_id, site_id=site.id, location_id=None, name="gw-1", ip_address="10.0.0.1"
        )
        assert gateway.lifecycle_state == DeviceLifecycleState.DISCOVERED


class TestEdgeDeviceService:
    async def test_register_device_publishes_event_and_audits(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        site = await _site(repos, organization_id)
        audit = AuditService(repos.audit)
        service = EdgeDeviceService(repos.devices, publish=publisher, audit=audit)
        device = await service.register_device(
            organization_id,
            site_id=site.id,
            name="plc-1",
            device_type=EdgeDeviceType.PLC,
            credential_ref="enrollment-token",
            credential_expires_at=None,
            actor_id="tester",
            now=NOW,
        )
        assert device.lifecycle_state == DeviceLifecycleState.REGISTERED
        assert publisher.names() == ["EdgeDeviceRegistered"]

    async def test_register_device_refuses_empty_credential(
        self, repos, organization_id: UUID
    ) -> None:
        site = await _site(repos, organization_id)
        service = EdgeDeviceService(repos.devices)
        with pytest.raises(CredentialRefusedError):
            await service.register_device(
                organization_id,
                site_id=site.id,
                name="plc-1",
                device_type=EdgeDeviceType.PLC,
                credential_ref="   ",
                credential_expires_at=None,
                actor_id=None,
                now=NOW,
            )

    async def test_transition_lifecycle_allowed(self, repos, organization_id: UUID) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = EdgeDeviceService(repos.devices)
        updated = await service.transition_lifecycle(
            device, target=DeviceLifecycleState.REGISTERED, now=NOW
        )
        assert updated.lifecycle_state == DeviceLifecycleState.REGISTERED

    async def test_transition_lifecycle_refused(self, repos, organization_id: UUID) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = EdgeDeviceService(repos.devices)
        with pytest.raises(TransitionRefusedError) as exc_info:
            await service.transition_lifecycle(device, target=DeviceLifecycleState.ACTIVE, now=NOW)
        assert exc_info.value.result.refusal == TransitionRefusal.INVALID_TRANSITION

    async def test_mark_online_then_offline_publish_boundary_events_only(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = EdgeDeviceService(repos.devices, publish=publisher)

        await service.mark_online(device, now=NOW)
        await service.mark_online(device, now=NOW)  # already online: no second event
        await service.mark_offline(device, now=NOW)
        await service.mark_offline(device, now=NOW)  # already offline: no second event

        assert publisher.names() == ["DeviceOnline", "DeviceOffline"]

    async def test_cordon_and_uncordon(self, repos, organization_id: UUID) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = EdgeDeviceService(repos.devices)
        cordoned = await service.cordon(device)
        assert not cordoned.is_schedulable
        uncordoned = await service.uncordon(device)
        assert uncordoned.is_schedulable


class TestInventoryService:
    async def test_record_snapshot(self, repos, organization_id: UUID) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = InventoryService(repos.inventory)
        snapshot = await service.record_snapshot(
            organization_id,
            device_id=device.id,
            resource_kind="application",
            resource_count=4,
            details=None,
            now=NOW,
        )
        assert snapshot.details == {}


class TestHealthService:
    async def test_refresh_overall_status_updates_device(
        self, repos, organization_id: UUID
    ) -> None:
        from app.models.enums import ComponentHealthStatus, DeviceComponent

        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        health_service = HealthService(repos.health, repos.devices)
        await health_service.record_reading(
            device,
            component=DeviceComponent.CPU,
            status=ComponentHealthStatus.CRITICAL,
            reading_value=99.0,
            detail=None,
            now=NOW,
        )
        aggregation = await health_service.refresh_overall_status(
            device, degraded_threshold=1, unhealthy_threshold=1
        )
        from app.models.enums import DeviceHealthStatus

        assert aggregation.overall == DeviceHealthStatus.UNHEALTHY
        refreshed = await repos.devices.require_in_org(organization_id, device.id)
        assert refreshed.health_status == DeviceHealthStatus.UNHEALTHY


class TestSynchronizationService:
    async def test_complete_sync_publishes_event(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = SynchronizationService(repos.synchronization, publish=publisher)
        sync = await service.start_sync(
            organization_id, device_id=device.id, sync_kind=SyncKind.FULL, now=NOW
        )
        completed = await service.complete_sync(sync, bytes_transferred=1024, now=NOW)
        assert completed.duration_ms is not None
        assert publisher.names() == ["SynchronizationCompleted"]

    async def test_fail_sync_publishes_event(self, repos, organization_id: UUID, publisher) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = SynchronizationService(repos.synchronization, publish=publisher)
        sync = await service.start_sync(
            organization_id, device_id=device.id, sync_kind=SyncKind.FULL, now=NOW
        )
        failed = await service.fail_sync(sync, error_message="dropped", now=NOW)
        assert failed.error_message == "dropped"
        assert publisher.names() == ["SynchronizationFailed"]

    async def test_mark_conflict_resolves_via_engine(self, repos, organization_id: UUID) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = SynchronizationService(repos.synchronization)
        sync = await service.start_sync(
            organization_id, device_id=device.id, sync_kind=SyncKind.FULL, now=NOW
        )
        updated, winner = await service.mark_conflict(
            sync, resolution=ConflictResolutionStrategy.SERVER_WINS, now=NOW
        )
        assert winner == "server"
        assert updated.conflict_resolution == ConflictResolutionStrategy.SERVER_WINS

    async def test_decide_retry_and_backoff(self, repos, organization_id: UUID) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = SynchronizationService(repos.synchronization)
        sync = await service.start_sync(
            organization_id, device_id=device.id, sync_kind=SyncKind.FULL, now=NOW
        )
        failed = await service.fail_sync(sync, error_message="x", now=NOW)
        decision = service.decide_retry(failed, attempt_count=0, max_attempts=3)
        assert decision.should_retry
        assert service.next_retry_delay_seconds(attempt_count=0) == 5.0


class TestOTAService:
    async def test_plan_update_valid(self, repos, organization_id: UUID, publisher) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id, firmware_version="1.0.0")
        await repos.firmware.create(
            EdgeFirmware(
                organization_id=organization_id,
                device_type=EdgeDeviceType.PLC,
                version_label="1.0.0",
                skew_rank=1,
            )
        )
        await repos.firmware.create(
            EdgeFirmware(
                organization_id=organization_id,
                device_type=EdgeDeviceType.PLC,
                version_label="1.1.0",
                skew_rank=2,
            )
        )
        service = OTAService(repos.updates, repos.firmware, publish=publisher, max_skew=2)
        update = await service.plan_update(
            device,
            update_kind=UpdateKind.FIRMWARE,
            strategy=UpdateStrategy.STAGED,
            to_version="1.1.0",
        )
        assert update.from_version == "1.0.0"

    async def test_plan_update_refused_on_downgrade(self, repos, organization_id: UUID) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id, firmware_version="1.1.0")
        await repos.firmware.create(
            EdgeFirmware(
                organization_id=organization_id,
                device_type=EdgeDeviceType.PLC,
                version_label="1.1.0",
                skew_rank=2,
            )
        )
        await repos.firmware.create(
            EdgeFirmware(
                organization_id=organization_id,
                device_type=EdgeDeviceType.PLC,
                version_label="1.0.0",
                skew_rank=1,
            )
        )
        service = OTAService(repos.updates, repos.firmware, max_skew=2)
        with pytest.raises(UpdatePlanRefusedError):
            await service.plan_update(
                device,
                update_kind=UpdateKind.FIRMWARE,
                strategy=UpdateStrategy.STAGED,
                to_version="1.0.0",
            )

    async def test_start_and_complete_update_advances_firmware_version(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id, firmware_version="1.0.0")
        await repos.firmware.create(
            EdgeFirmware(
                organization_id=organization_id,
                device_type=EdgeDeviceType.PLC,
                version_label="1.0.0",
                skew_rank=1,
            )
        )
        await repos.firmware.create(
            EdgeFirmware(
                organization_id=organization_id,
                device_type=EdgeDeviceType.PLC,
                version_label="2.0.0",
                skew_rank=2,
            )
        )
        service = OTAService(repos.updates, repos.firmware, publish=publisher, max_skew=5)
        update = await service.plan_update(
            device,
            update_kind=UpdateKind.FIRMWARE,
            strategy=UpdateStrategy.STAGED,
            to_version="2.0.0",
        )
        await service.start_update(update, now=NOW)
        completed = await service.complete_update(update, device, verification_passed=True, now=NOW)
        assert completed.status.value == "completed"
        assert device.firmware_version == "2.0.0"
        assert "OTAStarted" in publisher.names()
        assert "OTACompleted" in publisher.names()

    async def test_complete_update_rolls_back_on_failed_verification(
        self, repos, organization_id: UUID
    ) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id, firmware_version="1.0.0")
        await repos.firmware.create(
            EdgeFirmware(
                organization_id=organization_id,
                device_type=EdgeDeviceType.PLC,
                version_label="1.0.0",
                skew_rank=1,
            )
        )
        await repos.firmware.create(
            EdgeFirmware(
                organization_id=organization_id,
                device_type=EdgeDeviceType.PLC,
                version_label="2.0.0",
                skew_rank=2,
            )
        )
        service = OTAService(repos.updates, repos.firmware, max_skew=5)
        update = await service.plan_update(
            device,
            update_kind=UpdateKind.FIRMWARE,
            strategy=UpdateStrategy.STAGED,
            to_version="2.0.0",
        )
        completed = await service.complete_update(
            update, device, verification_passed=False, now=NOW
        )
        assert completed.status.value == "rolled_back"
        assert device.firmware_version == "1.0.0"

    async def test_fail_update(self, repos, organization_id: UUID, publisher) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id, firmware_version="1.0.0")
        await repos.firmware.create(
            EdgeFirmware(
                organization_id=organization_id,
                device_type=EdgeDeviceType.PLC,
                version_label="1.0.0",
                skew_rank=1,
            )
        )
        await repos.firmware.create(
            EdgeFirmware(
                organization_id=organization_id,
                device_type=EdgeDeviceType.PLC,
                version_label="2.0.0",
                skew_rank=2,
            )
        )
        service = OTAService(repos.updates, repos.firmware, publish=publisher, max_skew=5)
        update = await service.plan_update(
            device,
            update_kind=UpdateKind.FIRMWARE,
            strategy=UpdateStrategy.STAGED,
            to_version="2.0.0",
        )
        failed = await service.fail_update(update, error_message="disk full", now=NOW)
        assert failed.status.value == "failed"


class TestFirmwareService:
    async def test_register_and_deprecate(self, repos, organization_id: UUID) -> None:
        service = FirmwareService(repos.firmware)
        firmware = await service.register_version(
            organization_id,
            device_type=EdgeDeviceType.PLC,
            version_label="3.0.0",
            skew_rank=3,
            release_date=None,
            end_of_life_at=None,
        )
        deprecated = await service.deprecate(firmware)
        assert deprecated.is_deprecated


class TestApplicationService:
    async def test_deploy_mark_deployed_and_failed(self, repos, organization_id: UUID) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = ApplicationService(repos.applications)
        application = await service.deploy(
            organization_id,
            device_id=device.id,
            name="collector",
            version_label="1.0.0",
            deployment_strategy=ApplicationDeploymentStrategy.ROLLING,
        )
        deployed = await service.mark_deployed(application, now=NOW)
        assert deployed.deployed_at == NOW
        failed = await service.mark_failed(application)
        assert failed.status.value == "failed"


class TestEdgeAiModelService:
    async def test_stage_promote_and_roll_back(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = EdgeAiModelService(repos.ai_models, publish=publisher)
        model = await service.stage_model(
            organization_id,
            device_id=device.id,
            name="defect-detector",
            version_label="1.0.0",
            gpu_available=True,
            model_requires_gpu=False,
        )
        assert model.inference_target.value == "gpu"
        promoted = await service.promote(model, now=NOW)
        assert promoted.status.value == "deployed"
        assert publisher.names() == ["AIModelDeployed"]
        rolled_back = await service.roll_back(promoted)
        assert rolled_back.status.value == "rolled_back"

    async def test_promote_refuses_non_staged_model(self, repos, organization_id: UUID) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = EdgeAiModelService(repos.ai_models)
        model = await service.stage_model(
            organization_id,
            device_id=device.id,
            name="m1",
            version_label="1.0.0",
            gpu_available=False,
            model_requires_gpu=False,
        )
        await service.promote(model, now=NOW)
        with pytest.raises(PromotionRefusedError):
            await service.promote(model, now=NOW)


class TestProtocolService:
    async def test_register_endpoint_and_record_check(self, repos, organization_id: UUID) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = ProtocolService(repos.protocols)
        protocol = await service.register_endpoint(
            organization_id,
            device_id=device.id,
            protocol_kind=ProtocolKind.MODBUS_TCP,
            endpoint="10.0.0.5:502",
        )
        checked = await service.record_check(
            protocol, had_error=False, error_message=None, now=NOW, stale_after_minutes=30
        )
        assert checked.status.value == "connected"


class TestDigitalTwinService:
    def test_classify_delegates_to_engine(self) -> None:
        service = DigitalTwinService()
        assert service.classify("a", "a", is_syncing=False).value == "completed"
        assert service.classify(None, None, is_syncing=True).value == "in_progress"


class TestConfigurationService:
    async def test_apply_deactivates_previous_active_revision(
        self, repos, organization_id: UUID
    ) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = ConfigurationService(repos.configuration)
        first = await service.apply(
            organization_id,
            device_id=device.id,
            config_key="network",
            config_value={"vlan": 10},
            revision=1,
            now=NOW,
        )
        second = await service.apply(
            organization_id,
            device_id=device.id,
            config_key="network",
            config_value={"vlan": 20},
            revision=2,
            now=NOW,
        )
        assert second.is_current
        refreshed_first = await repos.configuration.list_for_device(device.id)
        first_row = next(r for r in refreshed_first if r.id == first.id)
        assert not first_row.is_current

    async def test_roll_back_reactivates_earlier_revision(
        self, repos, organization_id: UUID
    ) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = ConfigurationService(repos.configuration)
        await service.apply(
            organization_id,
            device_id=device.id,
            config_key="network",
            config_value={"vlan": 10},
            revision=1,
            now=NOW,
        )
        await service.apply(
            organization_id,
            device_id=device.id,
            config_key="network",
            config_value={"vlan": 20},
            revision=2,
            now=NOW,
        )
        rolled_back = await service.roll_back(
            device.id, config_key="network", target_revision=1, now=NOW
        )
        assert rolled_back.revision == 1
        assert rolled_back.is_current

    async def test_roll_back_refuses_unknown_revision(self, repos, organization_id: UUID) -> None:
        site = await _site(repos, organization_id)
        device = await _device(repos, organization_id, site.id)
        service = ConfigurationService(repos.configuration)
        await service.apply(
            organization_id,
            device_id=device.id,
            config_key="network",
            config_value={},
            revision=1,
            now=NOW,
        )
        with pytest.raises(RollbackRefusedError):
            await service.roll_back(device.id, config_key="network", target_revision=99, now=NOW)


class TestStatisticsService:
    async def test_roll_up_window_is_idempotent(self, repos, organization_id: UUID) -> None:
        service = StatisticsService(repos.statistics)
        window_start = NOW
        window_end = NOW + timedelta(hours=1)
        first = await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=window_end,
            sites_registered=1,
            devices_online=2,
            devices_offline=1,
            synchronizations_completed=3,
            synchronizations_failed=0,
            updates_completed=1,
            updates_failed=0,
        )
        second = await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=window_end,
            sites_registered=1,
            devices_online=5,
            devices_offline=0,
            synchronizations_completed=3,
            synchronizations_failed=0,
            updates_completed=1,
            updates_failed=0,
        )
        assert first.id == second.id
        assert second.devices_online == 5


class TestReportService:
    async def test_generate(self, repos, organization_id: UUID) -> None:
        service = ReportService(repos.reports)
        report = await service.generate(
            organization_id,
            kind=ReportKind.FLEET,
            title="Fleet Report",
            report_format=ReportFormat.JSON,
            period_start=None,
            period_end=None,
            content={"devices": 10},
            row_count=10,
            generated_by="tester",
            now=NOW,
        )
        assert report.status.value == "completed"
