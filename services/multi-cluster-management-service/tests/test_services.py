"""Integration tests for the service layer, against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.lifecycle.engine import TransitionRefusal
from app.models.enums import (
    AuditAction,
    CapacityResourceKind,
    ClusterComponent,
    ClusterLifecycleState,
    ClusterType,
    ComplianceFramework,
    ComponentHealthStatus,
    DeploymentStrategy,
    PolicyType,
    RegistrationMethod,
    ReportFormat,
    ReportKind,
    UpgradeStrategy,
)
from app.models.fleet import Cluster, ClusterCredential, ClusterVersion
from app.models.operations import ClusterUpgrade
from app.services.audit import AuditService
from app.services.capacity import CapacityService
from app.services.compliance import ComplianceService
from app.services.credentials import CredentialService
from app.services.federation import FederationService
from app.services.fleet import (
    ClusterGroupService,
    ClusterRegionService,
    ClusterService,
    TransitionRefusedError,
)
from app.services.health import HealthService
from app.services.inventory import InventoryService
from app.services.placement import PlacementService
from app.services.policies import PolicyService, PolicyTargetRefusedError
from app.services.reports import ReportService
from app.services.statistics import StatisticsService
from app.services.upgrades import UpgradePlanRefusedError, UpgradeService

NOW = datetime(2026, 6, 1, tzinfo=UTC)


async def _cluster(repos, organization_id: UUID, **kwargs: object) -> Cluster:
    defaults = {
        "organization_id": organization_id,
        "name": "c1",
        "cluster_type": ClusterType.KUBERNETES,
    }
    defaults.update(kwargs)
    return await repos.clusters.create(Cluster(**defaults))


class TestAuditService:
    async def test_record_creates_entry(self, repos, organization_id: UUID) -> None:
        service = AuditService(repos.audit)
        entry = await service.record(
            organization_id,
            action=AuditAction.ADMINISTRATIVE,
            entity_type="cluster",
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
            entity_type="cluster",
            entity_id=None,
            occurred_at=NOW,
        )
        assert entry.details == {}


class TestClusterGroupAndRegionServices:
    async def test_create_group(self, repos, organization_id: UUID) -> None:
        service = ClusterGroupService(repos.groups)
        group = await service.create_group(
            organization_id,
            name="prod-fleet",
            description="Production clusters",
            business_unit="platform",
        )
        assert group.name == "prod-fleet"

    async def test_create_region(self, repos, organization_id: UUID) -> None:
        service = ClusterRegionService(repos.regions)
        region = await service.create_region(
            organization_id,
            name="US East",
            code="us-east-1",
            provider="aws",
            availability_zones=["us-east-1a", "us-east-1b"],
        )
        assert region.code == "us-east-1"


class TestClusterService:
    async def test_register_cluster_publishes_event(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        audit = AuditService(repos.audit)
        service = ClusterService(repos.clusters, publish=publisher, audit=audit)
        cluster = await service.register_cluster(
            organization_id,
            name="prod-1",
            cluster_type=ClusterType.KUBERNETES,
            environment="production",
            group_id=None,
            region_id=None,
            actor_id="tester",
            now=NOW,
        )
        assert cluster.lifecycle_state == ClusterLifecycleState.DISCOVERED
        assert publisher.names() == ["ClusterRegistered"]
        entries = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert len(entries) == 1

    async def test_transition_lifecycle_allowed(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        service = ClusterService(repos.clusters, publish=publisher)
        cluster = await _cluster(repos, organization_id)
        updated = await service.transition_lifecycle(
            cluster, target=ClusterLifecycleState.REGISTERED, now=NOW
        )
        assert updated.lifecycle_state == ClusterLifecycleState.REGISTERED

    async def test_transition_lifecycle_invalid_raises(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        service = ClusterService(repos.clusters, publish=publisher)
        cluster = await _cluster(repos, organization_id)
        try:
            await service.transition_lifecycle(
                cluster, target=ClusterLifecycleState.ACTIVE, now=NOW
            )
            raise AssertionError("expected TransitionRefusedError")
        except TransitionRefusedError as exc:
            assert exc.result.refusal == TransitionRefusal.INVALID_TRANSITION

    async def test_transition_to_archived_publishes_removed_event(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        service = ClusterService(repos.clusters, publish=publisher)
        cluster = await _cluster(
            repos, organization_id, lifecycle_state=ClusterLifecycleState.DECOMMISSIONED
        )
        await service.transition_lifecycle(cluster, target=ClusterLifecycleState.ARCHIVED, now=NOW)
        assert "ClusterRemoved" in publisher.names()

    async def test_cordon_and_uncordon(self, repos, organization_id: UUID) -> None:
        service = ClusterService(repos.clusters)
        cluster = await _cluster(repos, organization_id)
        assert cluster.is_schedulable
        cordoned = await service.cordon(cluster)
        assert not cordoned.is_schedulable
        uncordoned = await service.uncordon(cordoned)
        assert uncordoned.is_schedulable


class TestCredentialService:
    async def test_register_credential_valid(self, repos, organization_id: UUID, publisher) -> None:
        cluster = await _cluster(repos, organization_id)
        service = CredentialService(repos.credentials, publish=publisher)
        credential = await service.register_credential(
            organization_id,
            cluster_id=cluster.id,
            method=RegistrationMethod.KUBECONFIG,
            credential_ref="ref-1",
            expires_at=None,
            actor_id="tester",
            now=NOW,
        )
        assert credential.is_valid
        assert "ClusterValidated" in publisher.names()

    async def test_register_credential_empty_ref_invalid(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        cluster = await _cluster(repos, organization_id)
        service = CredentialService(repos.credentials, publish=publisher)
        credential = await service.register_credential(
            organization_id,
            cluster_id=cluster.id,
            method=RegistrationMethod.KUBECONFIG,
            credential_ref="",
            expires_at=None,
            actor_id="tester",
            now=NOW,
        )
        assert not credential.is_valid

    async def test_revalidate(self, repos, organization_id: UUID, publisher) -> None:
        cluster = await _cluster(repos, organization_id)
        credential = await repos.credentials.create(
            ClusterCredential(
                organization_id=organization_id,
                cluster_id=cluster.id,
                method=RegistrationMethod.API_TOKEN,
                credential_ref="ref-1",
                expires_at=NOW - timedelta(days=1),
                is_valid=True,
            )
        )
        service = CredentialService(repos.credentials, publish=publisher)
        revalidated = await service.revalidate(credential, now=NOW)
        assert not revalidated.is_valid


class TestHealthService:
    async def test_record_reading(self, repos, organization_id: UUID) -> None:
        cluster = await _cluster(repos, organization_id)
        service = HealthService(repos.health, repos.clusters)
        reading = await service.record_reading(
            cluster,
            component=ClusterComponent.API_SERVER,
            status=ComponentHealthStatus.OK,
            detail=None,
            now=NOW,
        )
        assert reading.status == ComponentHealthStatus.OK

    async def test_refresh_overall_status_publishes_on_change(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        cluster = await _cluster(repos, organization_id)
        service = HealthService(repos.health, repos.clusters, publish=publisher)
        await service.record_reading(
            cluster,
            component=ClusterComponent.API_SERVER,
            status=ComponentHealthStatus.OK,
            detail=None,
            now=NOW,
        )
        aggregation = await service.refresh_overall_status(
            cluster, degraded_threshold=1, unhealthy_threshold=2, now=NOW
        )
        assert aggregation.overall.value == "healthy"
        assert "ClusterHealthChanged" in publisher.names()

    async def test_refresh_overall_status_no_change_no_event(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        cluster = await _cluster(repos, organization_id)
        cluster.health_status = "unknown"
        await repos.clusters.update(cluster)
        service = HealthService(repos.health, repos.clusters, publish=publisher)
        await service.refresh_overall_status(
            cluster, degraded_threshold=1, unhealthy_threshold=2, now=NOW
        )
        assert publisher.names() == []


class TestCapacityService:
    async def test_record_reading_and_assess(self, repos, organization_id: UUID) -> None:
        cluster = await _cluster(repos, organization_id)
        service = CapacityService(repos.capacity)
        reading = await service.record_reading(
            organization_id,
            cluster_id=cluster.id,
            resource_kind=CapacityResourceKind.CPU,
            total=100.0,
            used=85.0,
            measured_at=NOW,
        )
        assessment = service.assess(reading, warning_threshold=0.8, critical_threshold=0.9)
        assert assessment.severity == "warning"


class TestUpgradeService:
    async def test_plan_upgrade_success(self, repos, organization_id: UUID) -> None:
        cluster = await _cluster(repos, organization_id, kubernetes_version="1.28.0")
        await repos.versions.create(
            ClusterVersion(
                organization_id=organization_id,
                cluster_type=ClusterType.KUBERNETES,
                version_label="1.28.0",
                skew_rank=1,
            )
        )
        await repos.versions.create(
            ClusterVersion(
                organization_id=organization_id,
                cluster_type=ClusterType.KUBERNETES,
                version_label="1.29.0",
                skew_rank=2,
            )
        )
        service = UpgradeService(repos.upgrades, repos.versions, repos.clusters)
        upgrade = await service.plan_upgrade(
            cluster,
            to_version="1.29.0",
            strategy=UpgradeStrategy.ROLLING,
            max_skew=2,
            actor_id="tester",
            now=NOW,
        )
        assert upgrade.status.value == "planned"

    async def test_plan_upgrade_refused_on_downgrade(self, repos, organization_id: UUID) -> None:
        cluster = await _cluster(repos, organization_id, kubernetes_version="1.29.0")
        await repos.versions.create(
            ClusterVersion(
                organization_id=organization_id,
                cluster_type=ClusterType.KUBERNETES,
                version_label="1.29.0",
                skew_rank=2,
            )
        )
        await repos.versions.create(
            ClusterVersion(
                organization_id=organization_id,
                cluster_type=ClusterType.KUBERNETES,
                version_label="1.28.0",
                skew_rank=1,
            )
        )
        service = UpgradeService(repos.upgrades, repos.versions, repos.clusters)
        try:
            await service.plan_upgrade(
                cluster,
                to_version="1.28.0",
                strategy=UpgradeStrategy.ROLLING,
                max_skew=2,
                actor_id="tester",
                now=NOW,
            )
            raise AssertionError("expected UpgradePlanRefusedError")
        except UpgradePlanRefusedError:
            pass

    async def test_complete_upgrade_updates_cluster_version(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        cluster = await _cluster(repos, organization_id, kubernetes_version="1.28.0")
        service = UpgradeService(repos.upgrades, repos.versions, repos.clusters, publish=publisher)
        upgrade = await repos.upgrades.create(
            ClusterUpgrade(
                organization_id=organization_id,
                cluster_id=cluster.id,
                from_version="1.28.0",
                to_version="1.29.0",
                strategy=UpgradeStrategy.ROLLING,
                started_at=NOW,
            )
        )
        completed = await service.complete_upgrade(
            upgrade,
            pre_validation_passed=True,
            post_validation_passed=True,
            now=NOW + timedelta(minutes=10),
        )
        assert completed.status.value == "completed"
        refreshed = await repos.clusters.require_by_id(cluster.id)
        assert refreshed.kubernetes_version == "1.29.0"

    async def test_complete_upgrade_rolls_back_on_post_validation_failure(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        cluster = await _cluster(repos, organization_id, kubernetes_version="1.28.0")
        service = UpgradeService(repos.upgrades, repos.versions, repos.clusters, publish=publisher)
        upgrade = await repos.upgrades.create(
            ClusterUpgrade(
                organization_id=organization_id,
                cluster_id=cluster.id,
                from_version="1.28.0",
                to_version="1.29.0",
                strategy=UpgradeStrategy.ROLLING,
                started_at=NOW,
            )
        )
        completed = await service.complete_upgrade(
            upgrade, pre_validation_passed=True, post_validation_passed=False, now=NOW
        )
        assert completed.status.value == "rolled_back"

    async def test_fail_upgrade(self, repos, organization_id: UUID, publisher) -> None:
        cluster = await _cluster(repos, organization_id)
        service = UpgradeService(repos.upgrades, repos.versions, repos.clusters, publish=publisher)
        upgrade = await repos.upgrades.create(
            ClusterUpgrade(
                organization_id=organization_id,
                cluster_id=cluster.id,
                from_version="1.28.0",
                to_version="1.29.0",
                strategy=UpgradeStrategy.ROLLING,
            )
        )
        failed = await service.fail_upgrade(upgrade, error_message="node drain timeout", now=NOW)
        assert failed.status.value == "failed"
        assert "ClusterUpgraded" in publisher.names()


class TestPolicyService:
    async def test_create_policy_cluster_scoped(self, repos, organization_id: UUID) -> None:
        cluster = await _cluster(repos, organization_id)
        audit = AuditService(repos.audit)
        service = PolicyService(repos.policies, repos.clusters, audit=audit)
        policy = await service.create_policy(
            organization_id,
            name="no-privileged-pods",
            policy_type=PolicyType.SECURITY,
            definition={"rule": "deny-privileged"},
            cluster_id=cluster.id,
            group_id=None,
            group_member_ids=[],
            actor_id="tester",
            now=NOW,
        )
        assert policy.cluster_id == cluster.id

    async def test_create_policy_no_target_refused(self, repos, organization_id: UUID) -> None:
        service = PolicyService(repos.policies, repos.clusters)
        try:
            await service.create_policy(
                organization_id,
                name="orphan-policy",
                policy_type=PolicyType.SECURITY,
                definition={},
                cluster_id=None,
                group_id=None,
                group_member_ids=[],
                actor_id="tester",
                now=NOW,
            )
            raise AssertionError("expected PolicyTargetRefusedError")
        except PolicyTargetRefusedError:
            pass

    async def test_mark_applied_publishes_event(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        cluster = await _cluster(repos, organization_id)
        service = PolicyService(repos.policies, repos.clusters, publish=publisher)
        policy = await service.create_policy(
            organization_id,
            name="p1",
            policy_type=PolicyType.SECURITY,
            definition={},
            cluster_id=cluster.id,
            group_id=None,
            group_member_ids=[],
            actor_id="tester",
            now=NOW,
        )
        applied = await service.mark_applied(policy, now=NOW)
        assert applied.propagation_status.value == "applied"
        assert "PolicyApplied" in publisher.names()

    async def test_check_drift_marks_drifted(self, repos, organization_id: UUID) -> None:
        cluster = await _cluster(repos, organization_id)
        service = PolicyService(repos.policies, repos.clusters)
        policy = await service.create_policy(
            organization_id,
            name="p1",
            policy_type=PolicyType.SECURITY,
            definition={},
            cluster_id=cluster.id,
            group_id=None,
            group_member_ids=[],
            actor_id="tester",
            now=NOW,
        )
        await service.mark_applied(policy, now=NOW)
        drifted = await service.check_drift(
            policy, live_state_hash="different-hash", desired_hash="original-hash", now=NOW
        )
        assert drifted.propagation_status.value == "drifted"


class TestComplianceService:
    async def test_record_assessment_compliant_no_remediation(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        cluster = await _cluster(repos, organization_id)
        service = ComplianceService(repos.compliance, publish=publisher)
        assessment = await service.record_assessment(
            organization_id,
            cluster_id=cluster.id,
            framework=ComplianceFramework.CIS_KUBERNETES,
            score=100.0,
            findings=[],
            compliant_threshold=95.0,
            partial_threshold=70.0,
            grace_days=14,
            actor_id="tester",
            now=NOW,
        )
        assert assessment.status.value == "compliant"
        assert assessment.remediation_due_at is None
        assert "ComplianceUpdated" in publisher.names()

    async def test_record_assessment_non_compliant_has_remediation_due(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        cluster = await _cluster(repos, organization_id)
        service = ComplianceService(repos.compliance, publish=publisher)
        assessment = await service.record_assessment(
            organization_id,
            cluster_id=cluster.id,
            framework=ComplianceFramework.CIS_KUBERNETES,
            score=30.0,
            findings=[{"rule": "no-root-containers", "passed": False}],
            compliant_threshold=95.0,
            partial_threshold=70.0,
            grace_days=14,
            actor_id="tester",
            now=NOW,
        )
        assert assessment.status.value == "non_compliant"
        assert assessment.remediation_due_at == NOW + timedelta(days=14)


class TestPlacementService:
    def test_select_candidates(self, repos, organization_id: UUID) -> None:
        c1 = Cluster(
            organization_id=organization_id,
            name="a",
            cluster_type=ClusterType.KUBERNETES,
            labels={"env": "prod"},
        )
        c1.id = uuid4()
        service = PlacementService(repos.workloads)
        selected = service.select_candidates(
            [c1], required_labels={"env": "prod"}, forbidden_labels={}
        )
        assert selected == (c1.id,)

    async def test_place_workload_success(self, repos, organization_id: UUID) -> None:
        cluster = await _cluster(repos, organization_id)
        service = PlacementService(repos.workloads)
        workload = await service.place_workload(
            organization_id,
            name="api",
            namespace="default",
            cluster_id=cluster.id,
            deployment_strategy=DeploymentStrategy.ROLLING_UPDATE,
            replicas=3,
            affinity_rules={},
            now=NOW,
        )
        assert workload.placement_status.value == "placed"

    async def test_place_workload_no_cluster_is_failed(self, repos, organization_id: UUID) -> None:
        service = PlacementService(repos.workloads)
        workload = await service.place_workload(
            organization_id,
            name="api",
            namespace=None,
            cluster_id=None,
            deployment_strategy=DeploymentStrategy.ROLLING_UPDATE,
            replicas=None,
            affinity_rules={},
            now=NOW,
        )
        assert workload.placement_status.value == "failed"
        assert workload.cluster_id is None

    async def test_drain_cluster_marks_placed_workloads_rebalancing(
        self, repos, organization_id: UUID
    ) -> None:
        cluster = await _cluster(repos, organization_id)
        service = PlacementService(repos.workloads)
        await service.place_workload(
            organization_id,
            name="api",
            namespace=None,
            cluster_id=cluster.id,
            deployment_strategy=DeploymentStrategy.ROLLING_UPDATE,
            replicas=1,
            affinity_rules={},
            now=NOW,
        )
        count = await service.drain_cluster(cluster.id)
        assert count == 1


class TestFederationService:
    async def test_plan_success(self, repos, organization_id: UUID) -> None:
        audit = AuditService(repos.audit)
        service = FederationService(audit)
        src = uuid4()
        target = uuid4()
        plan = await service.plan(
            organization_id,
            source_cluster_id=src,
            requested_target_ids=[target],
            resource_kind="secret",
            actor_id="tester",
            now=NOW,
        )
        assert plan.is_planned
        entries = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert len(entries) == 1
        assert entries[0].succeeded

    async def test_plan_refused_still_audited(self, repos, organization_id: UUID) -> None:
        audit = AuditService(repos.audit)
        service = FederationService(audit)
        src = uuid4()
        plan = await service.plan(
            organization_id,
            source_cluster_id=src,
            requested_target_ids=[src],
            resource_kind="secret",
            actor_id="tester",
            now=NOW,
        )
        assert not plan.is_planned
        entries = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert not entries[0].succeeded


class TestStatisticsService:
    async def test_roll_up_window_idempotent(self, repos, organization_id: UUID) -> None:
        service = StatisticsService(repos.statistics)
        window_end = NOW + timedelta(hours=1)
        first = await service.roll_up_window(
            organization_id,
            window_start=NOW,
            window_end=window_end,
            clusters_registered=5,
            clusters_healthy=4,
            clusters_degraded=1,
            clusters_unhealthy=0,
            policy_violations=0,
            compliance_violations=0,
            upgrades_completed=1,
            upgrades_failed=0,
            total_node_count=20,
        )
        second = await service.roll_up_window(
            organization_id,
            window_start=NOW,
            window_end=window_end,
            clusters_registered=10,
            clusters_healthy=8,
            clusters_degraded=2,
            clusters_unhealthy=0,
            policy_violations=1,
            compliance_violations=1,
            upgrades_completed=2,
            upgrades_failed=1,
            total_node_count=40,
        )
        assert first.id == second.id
        assert second.clusters_registered == 10


class TestReportService:
    async def test_generate(self, repos, organization_id: UUID) -> None:
        service = ReportService(repos.reports)
        report = await service.generate(
            organization_id,
            kind=ReportKind.FLEET,
            title="Monthly Fleet Report",
            report_format=ReportFormat.JSON,
            period_start=NOW - timedelta(days=30),
            period_end=NOW,
            content={"total_clusters": 50},
            row_count=50,
            generated_by="tester",
            now=NOW,
        )
        assert report.status.value == "completed"


class TestInventoryService:
    async def test_record_snapshot(self, repos, organization_id: UUID) -> None:
        cluster = await _cluster(repos, organization_id)
        service = InventoryService(repos.inventory)
        snapshot = await service.record_snapshot(
            organization_id,
            cluster_id=cluster.id,
            resource_kind="namespace",
            resource_count=12,
            details={"names": ["default", "kube-system"]},
            collected_at=NOW,
        )
        assert snapshot.resource_count == 12
