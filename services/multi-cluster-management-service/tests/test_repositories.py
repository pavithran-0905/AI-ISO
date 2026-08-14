"""Integration tests for repository query methods, against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from shared_core.exceptions.not_found import NotFoundError

from app.models.enums import (
    AuditAction,
    CapacityResourceKind,
    ClusterComplianceStatus,
    ClusterComponent,
    ClusterLifecycleState,
    ClusterType,
    ComplianceFramework,
    ComponentHealthStatus,
    DeploymentStrategy,
    PolicyPropagationStatus,
    PolicyType,
    RegistrationMethod,
    ReportFormat,
    ReportKind,
    ReportStatus,
    UpgradeStatus,
    UpgradeStrategy,
    WorkloadPlacementStatus,
)
from app.models.fleet import Cluster, ClusterCredential, ClusterGroup, ClusterRegion, ClusterVersion
from app.models.operations import (
    ClusterCapacity,
    ClusterCompliance,
    ClusterHealth,
    ClusterInventory,
    ClusterPolicy,
    ClusterUpgrade,
)
from app.models.reporting import (
    ClusterAudit,
    ClusterEvent,
    ClusterReport,
    ClusterStatistic,
    ClusterWorkload,
)

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _cluster(organization_id: UUID, *, name: str = "c1") -> Cluster:
    return Cluster(organization_id=organization_id, name=name, cluster_type=ClusterType.KUBERNETES)


class TestClusterRepository:
    async def test_find_by_name(self, repos, organization_id: UUID) -> None:
        created = await repos.clusters.create(_cluster(organization_id, name="find-me"))
        found = await repos.clusters.find_by_name(organization_id, "find-me")
        assert found is not None and found.id == created.id

    async def test_find_by_name_missing_returns_none(self, repos, organization_id: UUID) -> None:
        assert await repos.clusters.find_by_name(organization_id, "ghost") is None

    async def test_require_in_org(self, repos, organization_id: UUID) -> None:
        created = await repos.clusters.create(_cluster(organization_id))
        found = await repos.clusters.require_in_org(organization_id, created.id)
        assert found.id == created.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.clusters.require_in_org(organization_id, uuid4())

    async def test_list_recent_filters_by_lifecycle_state(
        self, repos, organization_id: UUID
    ) -> None:
        c1 = _cluster(organization_id, name="a")
        c1.lifecycle_state = ClusterLifecycleState.ACTIVE
        c2 = _cluster(organization_id, name="b")
        c2.lifecycle_state = ClusterLifecycleState.FAILED
        await repos.clusters.create(c1)
        await repos.clusters.create(c2)
        found = await repos.clusters.list_recent(
            organization_id, lifecycle_state=ClusterLifecycleState.ACTIVE
        )
        assert len(found) == 1

    async def test_list_recent_filters_by_group(self, repos, organization_id: UUID) -> None:
        group = await repos.groups.create(ClusterGroup(organization_id=organization_id, name="g1"))
        c1 = _cluster(organization_id, name="a")
        c1.group_id = group.id
        await repos.clusters.create(c1)
        await repos.clusters.create(_cluster(organization_id, name="b"))
        found = await repos.clusters.list_recent(organization_id, group_id=group.id)
        assert len(found) == 1

    async def test_list_active(self, repos, organization_id: UUID) -> None:
        c1 = _cluster(organization_id, name="active-one")
        c1.lifecycle_state = ClusterLifecycleState.ACTIVE
        await repos.clusters.create(c1)
        await repos.clusters.create(_cluster(organization_id, name="discovered-one"))
        found = await repos.clusters.list_active(organization_id)
        assert len(found) == 1

    async def test_list_organization_ids(self, repos, organization_id: UUID) -> None:
        await repos.clusters.create(_cluster(organization_id))
        ids = await repos.clusters.list_organization_ids()
        assert organization_id in ids


class TestClusterGroupRepository:
    async def test_find_by_name(self, repos, organization_id: UUID) -> None:
        created = await repos.groups.create(
            ClusterGroup(organization_id=organization_id, name="prod-group")
        )
        found = await repos.groups.find_by_name(organization_id, "prod-group")
        assert found is not None and found.id == created.id

    async def test_list_all(self, repos, organization_id: UUID) -> None:
        await repos.groups.create(ClusterGroup(organization_id=organization_id, name="g1"))
        found = await repos.groups.list_all(organization_id)
        assert len(found) == 1


class TestClusterRegionRepository:
    async def test_list_all(self, repos, organization_id: UUID) -> None:
        await repos.regions.create(
            ClusterRegion(organization_id=organization_id, name="US East", code="us-east-1")
        )
        found = await repos.regions.list_all(organization_id)
        assert len(found) == 1


class TestClusterCredentialRepository:
    async def test_list_for_cluster_and_latest(self, repos, organization_id: UUID) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        await repos.credentials.create(
            ClusterCredential(
                organization_id=organization_id,
                cluster_id=cluster.id,
                method=RegistrationMethod.KUBECONFIG,
                credential_ref="ref-1",
            )
        )
        found = await repos.credentials.list_for_cluster(cluster.id)
        assert len(found) == 1
        latest = await repos.credentials.latest_for_cluster(cluster.id)
        assert latest is not None

    async def test_latest_for_cluster_none_when_absent(self, repos) -> None:
        assert await repos.credentials.latest_for_cluster(uuid4()) is None


class TestClusterVersionRepository:
    async def test_find_by_type_and_version(self, repos, organization_id: UUID) -> None:
        await repos.versions.create(
            ClusterVersion(
                organization_id=organization_id,
                cluster_type=ClusterType.KUBERNETES,
                version_label="1.29.4",
                skew_rank=5,
            )
        )
        found = await repos.versions.find_by_type_and_version(ClusterType.KUBERNETES, "1.29.4")
        assert found is not None

    async def test_list_for_type_ordered_by_skew(self, repos, organization_id: UUID) -> None:
        await repos.versions.create(
            ClusterVersion(
                organization_id=organization_id,
                cluster_type=ClusterType.KUBERNETES,
                version_label="1.30.0",
                skew_rank=6,
            )
        )
        await repos.versions.create(
            ClusterVersion(
                organization_id=organization_id,
                cluster_type=ClusterType.KUBERNETES,
                version_label="1.29.4",
                skew_rank=5,
            )
        )
        found = await repos.versions.list_for_type(ClusterType.KUBERNETES)
        assert [v.version_label for v in found] == ["1.29.4", "1.30.0"]


class TestClusterInventoryRepository:
    async def test_latest_for_cluster_and_list(self, repos, organization_id: UUID) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        await repos.inventory.create(
            ClusterInventory(
                organization_id=organization_id,
                cluster_id=cluster.id,
                resource_kind="node",
                resource_count=3,
                collected_at=NOW - timedelta(hours=1),
            )
        )
        await repos.inventory.create(
            ClusterInventory(
                organization_id=organization_id,
                cluster_id=cluster.id,
                resource_kind="node",
                resource_count=5,
                collected_at=NOW,
            )
        )
        latest = await repos.inventory.latest_for_cluster(cluster.id, resource_kind="node")
        assert latest is not None and latest.resource_count == 5
        found = await repos.inventory.list_for_cluster(cluster.id)
        assert len(found) == 2


class TestClusterHealthRepository:
    async def test_latest_per_component(self, repos, organization_id: UUID) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        await repos.health.create(
            ClusterHealth(
                organization_id=organization_id,
                cluster_id=cluster.id,
                component=ClusterComponent.API_SERVER,
                status=ComponentHealthStatus.OK,
                checked_at=NOW - timedelta(hours=1),
            )
        )
        await repos.health.create(
            ClusterHealth(
                organization_id=organization_id,
                cluster_id=cluster.id,
                component=ClusterComponent.API_SERVER,
                status=ComponentHealthStatus.WARNING,
                checked_at=NOW,
            )
        )
        await repos.health.create(
            ClusterHealth(
                organization_id=organization_id,
                cluster_id=cluster.id,
                component=ClusterComponent.ETCD,
                status=ComponentHealthStatus.OK,
                checked_at=NOW,
            )
        )
        latest = await repos.health.latest_per_component(cluster.id)
        assert len(latest) == 2
        api_server_reading = next(r for r in latest if r.component == ClusterComponent.API_SERVER)
        assert api_server_reading.status == ComponentHealthStatus.WARNING

    async def test_list_for_cluster(self, repos, organization_id: UUID) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        await repos.health.create(
            ClusterHealth(
                organization_id=organization_id,
                cluster_id=cluster.id,
                component=ClusterComponent.ETCD,
                status=ComponentHealthStatus.OK,
                checked_at=NOW,
            )
        )
        found = await repos.health.list_for_cluster(cluster.id)
        assert len(found) == 1


class TestClusterCapacityRepository:
    async def test_latest_for_resource_and_list_recent(self, repos, organization_id: UUID) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        await repos.capacity.create(
            ClusterCapacity(
                organization_id=organization_id,
                cluster_id=cluster.id,
                resource_kind=CapacityResourceKind.CPU,
                total=100.0,
                used=50.0,
                measured_at=NOW - timedelta(hours=1),
            )
        )
        await repos.capacity.create(
            ClusterCapacity(
                organization_id=organization_id,
                cluster_id=cluster.id,
                resource_kind=CapacityResourceKind.CPU,
                total=100.0,
                used=80.0,
                measured_at=NOW,
            )
        )
        latest = await repos.capacity.latest_for_resource(
            cluster.id, resource_kind=CapacityResourceKind.CPU
        )
        assert latest is not None and latest.used == 80.0
        found = await repos.capacity.list_recent(cluster.id, resource_kind=CapacityResourceKind.CPU)
        assert len(found) == 2


class TestClusterUpgradeRepository:
    async def test_list_for_cluster_and_in_progress(self, repos, organization_id: UUID) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        await repos.upgrades.create(
            ClusterUpgrade(
                organization_id=organization_id,
                cluster_id=cluster.id,
                from_version="1.28.0",
                to_version="1.29.0",
                strategy=UpgradeStrategy.ROLLING,
                status=UpgradeStatus.IN_PROGRESS,
            )
        )
        await repos.upgrades.create(
            ClusterUpgrade(
                organization_id=organization_id,
                cluster_id=cluster.id,
                from_version="1.27.0",
                to_version="1.28.0",
                strategy=UpgradeStrategy.ROLLING,
                status=UpgradeStatus.COMPLETED,
            )
        )
        for_cluster = await repos.upgrades.list_for_cluster(cluster.id)
        assert len(for_cluster) == 2
        in_progress = await repos.upgrades.list_in_progress(organization_id)
        assert len(in_progress) == 1


class TestClusterComplianceRepository:
    async def test_latest_for_framework_and_list(self, repos, organization_id: UUID) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        await repos.compliance.create(
            ClusterCompliance(
                organization_id=organization_id,
                cluster_id=cluster.id,
                framework=ComplianceFramework.CIS_KUBERNETES,
                status=ClusterComplianceStatus.NON_COMPLIANT,
                assessed_at=NOW - timedelta(days=1),
            )
        )
        await repos.compliance.create(
            ClusterCompliance(
                organization_id=organization_id,
                cluster_id=cluster.id,
                framework=ComplianceFramework.CIS_KUBERNETES,
                status=ClusterComplianceStatus.COMPLIANT,
                assessed_at=NOW,
            )
        )
        latest = await repos.compliance.latest_for_framework(
            cluster.id, framework=ComplianceFramework.CIS_KUBERNETES
        )
        assert latest is not None and latest.status == ClusterComplianceStatus.COMPLIANT
        found = await repos.compliance.list_for_cluster(cluster.id)
        assert len(found) == 2
        org_ids = await repos.compliance.list_organization_ids()
        assert organization_id in org_ids


class TestClusterPolicyRepository:
    async def test_list_for_cluster_and_group(self, repos, organization_id: UUID) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        group = await repos.groups.create(ClusterGroup(organization_id=organization_id, name="g1"))
        await repos.policies.create(
            ClusterPolicy(
                organization_id=organization_id,
                cluster_id=cluster.id,
                name="p1",
                policy_type=PolicyType.SECURITY,
            )
        )
        await repos.policies.create(
            ClusterPolicy(
                organization_id=organization_id,
                group_id=group.id,
                name="p2",
                policy_type=PolicyType.NETWORK,
            )
        )
        for_cluster = await repos.policies.list_for_cluster(cluster.id)
        assert len(for_cluster) == 1
        for_group = await repos.policies.list_for_group(group.id)
        assert len(for_group) == 1

    async def test_list_pending_and_applied(self, repos, organization_id: UUID) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        await repos.policies.create(
            ClusterPolicy(
                organization_id=organization_id,
                cluster_id=cluster.id,
                name="pending-policy",
                policy_type=PolicyType.SECURITY,
                propagation_status=PolicyPropagationStatus.PENDING,
            )
        )
        await repos.policies.create(
            ClusterPolicy(
                organization_id=organization_id,
                cluster_id=cluster.id,
                name="applied-policy",
                policy_type=PolicyType.SECURITY,
                propagation_status=PolicyPropagationStatus.APPLIED,
            )
        )
        pending = await repos.policies.list_pending(organization_id)
        assert len(pending) == 1
        applied = await repos.policies.list_applied(organization_id)
        assert len(applied) == 1
        org_ids = await repos.policies.list_organization_ids()
        assert organization_id in org_ids


class TestClusterWorkloadRepository:
    async def test_list_for_cluster_and_pending(self, repos, organization_id: UUID) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        await repos.workloads.create(
            ClusterWorkload(
                organization_id=organization_id,
                cluster_id=cluster.id,
                name="w1",
                deployment_strategy=DeploymentStrategy.ROLLING_UPDATE,
                placement_status=WorkloadPlacementStatus.PENDING,
            )
        )
        found = await repos.workloads.list_for_cluster(cluster.id)
        assert len(found) == 1
        pending = await repos.workloads.list_pending(organization_id)
        assert len(pending) == 1


class TestClusterEventRepository:
    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        await repos.events.create(
            ClusterEvent(
                organization_id=organization_id,
                cluster_id=cluster.id,
                event_kind="lifecycle_transition",
                summary="moved to active",
                occurred_at=NOW,
            )
        )
        found = await repos.events.list_recent(cluster.id)
        assert len(found) == 1


class TestClusterStatisticRepository:
    async def test_find_window_and_list_range(self, repos, organization_id: UUID) -> None:
        await repos.statistics.create(
            ClusterStatistic(
                organization_id=organization_id,
                window_start=NOW,
                window_end=NOW + timedelta(hours=1),
            )
        )
        found = await repos.statistics.find_window(
            organization_id, window_start=NOW, window_end=NOW + timedelta(hours=1)
        )
        assert found is not None
        in_range = await repos.statistics.list_range(
            organization_id, start=NOW - timedelta(hours=1), end=NOW + timedelta(hours=2)
        )
        assert len(in_range) == 1

    async def test_find_window_missing_returns_none(self, repos, organization_id: UUID) -> None:
        found = await repos.statistics.find_window(
            organization_id, window_start=NOW, window_end=NOW + timedelta(hours=1)
        )
        assert found is None


class TestClusterReportRepository:
    async def test_require_in_org_and_list_recent(self, repos, organization_id: UUID) -> None:
        report = await repos.reports.create(
            ClusterReport(
                organization_id=organization_id,
                kind=ReportKind.FLEET,
                report_format=ReportFormat.JSON,
                title="Fleet Report",
                status=ReportStatus.COMPLETED,
            )
        )
        found = await repos.reports.require_in_org(organization_id, report.id)
        assert found.id == report.id
        recent = await repos.reports.list_recent(organization_id, status=ReportStatus.COMPLETED)
        assert len(recent) == 1

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.reports.require_in_org(organization_id, uuid4())


class TestClusterAuditRepository:
    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.audit.create(
            ClusterAudit(
                organization_id=organization_id,
                action=AuditAction.CLUSTER_REGISTERED,
                entity_type="cluster",
                occurred_at=NOW,
            )
        )
        found = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert len(found) == 1

    async def test_list_recent_excludes_before_since(self, repos, organization_id: UUID) -> None:
        await repos.audit.create(
            ClusterAudit(
                organization_id=organization_id,
                action=AuditAction.CLUSTER_REGISTERED,
                entity_type="cluster",
                occurred_at=NOW - timedelta(days=10),
            )
        )
        found = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert found == []
