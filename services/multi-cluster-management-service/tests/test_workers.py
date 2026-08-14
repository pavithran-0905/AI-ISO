"""Integration tests for background workers, against real PostgreSQL.

Uses real wall-clock time (``datetime.now(UTC)``) throughout, matching
every worker's own internal ``now = datetime.now(UTC)`` -- a fixed
historical constant would fall outside a worker's real query window and
produce tests that pass without the loop body ever executing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models.enums import (
    CapacityResourceKind,
    ClusterComplianceStatus,
    ClusterComponent,
    ClusterHealthStatus,
    ComplianceFramework,
    ComponentHealthStatus,
    PolicyPropagationStatus,
    PolicyType,
)
from app.models.fleet import Cluster
from app.models.operations import ClusterCapacity, ClusterCompliance, ClusterHealth, ClusterPolicy
from app.services.notifications import FleetNotifier
from app.workers.capacity_analysis import CapacityAnalysisWorker
from app.workers.compliance_sweep import ComplianceSweepWorker
from app.workers.health_sweep import HealthSweepWorker
from app.workers.policy_reconcile import PolicyReconcileWorker
from app.workers.statistics_rollup import StatisticsRollupWorker


def now() -> datetime:
    return datetime.now(UTC)


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def broadcast(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


def _cluster(organization_id: UUID, **kwargs: object) -> Cluster:
    from app.models.enums import ClusterType

    defaults = {
        "organization_id": organization_id,
        "name": "c1",
        "cluster_type": ClusterType.KUBERNETES,
    }
    defaults.update(kwargs)
    return Cluster(**defaults)


async def _noop_publish(event: object) -> None:
    pass


class TestHealthSweepWorker:
    async def test_tick_marks_stale_cluster_offline_and_notifies(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        cluster = await repos.clusters.create(
            _cluster(organization_id, last_seen_at=now() - timedelta(hours=1))
        )
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
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

        await db_session.refresh(cluster)
        assert cluster.health_status == ClusterHealthStatus.OFFLINE
        assert manager.calls[0]["topic"] == "multi_cluster.cluster_offline"

    async def test_tick_refreshes_healthy_cluster_from_readings(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id, last_seen_at=now()))
        await repos.health.create(
            ClusterHealth(
                organization_id=organization_id,
                cluster_id=cluster.id,
                component=ClusterComponent.API_SERVER,
                status=ComponentHealthStatus.OK,
                checked_at=now(),
            )
        )
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        worker = HealthSweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            degraded_threshold=1,
            unhealthy_threshold=2,
            stale_threshold_minutes=15,
        )
        await worker.tick()

        await db_session.refresh(cluster)
        assert cluster.health_status == ClusterHealthStatus.HEALTHY

    async def test_tick_no_clusters_checks_nothing(self, db_session_factory) -> None:
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        worker = HealthSweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            degraded_threshold=1,
            unhealthy_threshold=2,
            stale_threshold_minutes=15,
        )
        assert await worker.tick() == 0


class TestComplianceSweepWorker:
    async def test_tick_notifies_overdue_remediation(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        await repos.compliance.create(
            ClusterCompliance(
                organization_id=organization_id,
                cluster_id=cluster.id,
                framework=ComplianceFramework.CIS_KUBERNETES,
                status=ClusterComplianceStatus.NON_COMPLIANT,
                assessed_at=now() - timedelta(days=30),
                remediation_due_at=now() - timedelta(days=1),
            )
        )
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        worker = ComplianceSweepWorker(db_session_factory, notifier=notifier)
        flagged = await worker.tick()
        assert flagged == 1
        assert manager.calls[0]["topic"] == "multi_cluster.compliance_failure"

    async def test_tick_skips_not_yet_due_remediation(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        await repos.compliance.create(
            ClusterCompliance(
                organization_id=organization_id,
                cluster_id=cluster.id,
                framework=ComplianceFramework.CIS_KUBERNETES,
                status=ClusterComplianceStatus.NON_COMPLIANT,
                assessed_at=now(),
                remediation_due_at=now() + timedelta(days=14),
            )
        )
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        worker = ComplianceSweepWorker(db_session_factory, notifier=notifier)
        assert await worker.tick() == 0

    async def test_tick_no_organizations_flags_nothing(self, db_session_factory) -> None:
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        worker = ComplianceSweepWorker(db_session_factory, notifier=notifier)
        assert await worker.tick() == 0


class TestPolicyReconcileWorker:
    async def test_tick_times_out_stuck_pending_policy(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        policy = await repos.policies.create(
            ClusterPolicy(
                organization_id=organization_id,
                cluster_id=cluster.id,
                name="stuck-policy",
                policy_type=PolicyType.SECURITY,
                propagation_status=PolicyPropagationStatus.PENDING,
            )
        )
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        worker = PolicyReconcileWorker(
            db_session_factory,
            notifier=notifier,
            propagation_timeout_seconds=0.0,
            drift_check_interval_seconds=1_800,
        )
        timed_out = await worker.tick()
        assert timed_out == 1

        await db_session.refresh(policy)
        assert policy.propagation_status == PolicyPropagationStatus.FAILED
        assert manager.calls[0]["topic"] == "multi_cluster.policy_violation"

    async def test_tick_refreshes_due_applied_policy(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        policy = await repos.policies.create(
            ClusterPolicy(
                organization_id=organization_id,
                cluster_id=cluster.id,
                name="applied-policy",
                policy_type=PolicyType.SECURITY,
                propagation_status=PolicyPropagationStatus.APPLIED,
                last_checked_at=None,
            )
        )
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        worker = PolicyReconcileWorker(
            db_session_factory,
            notifier=notifier,
            propagation_timeout_seconds=3_600,
            drift_check_interval_seconds=0,
        )
        await worker.tick()

        await db_session.refresh(policy)
        assert policy.last_checked_at is not None

    async def test_tick_no_organizations_times_out_nothing(self, db_session_factory) -> None:
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        worker = PolicyReconcileWorker(
            db_session_factory,
            notifier=notifier,
            propagation_timeout_seconds=3_600,
            drift_check_interval_seconds=1_800,
        )
        assert await worker.tick() == 0


class TestCapacityAnalysisWorker:
    async def test_tick_notifies_on_high_utilization(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        await repos.capacity.create(
            ClusterCapacity(
                organization_id=organization_id,
                cluster_id=cluster.id,
                resource_kind=CapacityResourceKind.CPU,
                total=100.0,
                used=95.0,
                measured_at=now(),
            )
        )
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        worker = CapacityAnalysisWorker(
            db_session_factory, notifier=notifier, warning_threshold=0.8, critical_threshold=0.9
        )
        flagged = await worker.tick()
        assert flagged == 1
        assert manager.calls[0]["topic"] == "multi_cluster.capacity_warning"

    async def test_tick_no_warning_for_low_utilization(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        cluster = await repos.clusters.create(_cluster(organization_id))
        await repos.capacity.create(
            ClusterCapacity(
                organization_id=organization_id,
                cluster_id=cluster.id,
                resource_kind=CapacityResourceKind.CPU,
                total=100.0,
                used=10.0,
                measured_at=now(),
            )
        )
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        worker = CapacityAnalysisWorker(
            db_session_factory, notifier=notifier, warning_threshold=0.8, critical_threshold=0.9
        )
        assert await worker.tick() == 0

    async def test_tick_no_clusters_flags_nothing(self, db_session_factory) -> None:
        manager = _RecordingManager()
        notifier = FleetNotifier(manager)  # type: ignore[arg-type]
        worker = CapacityAnalysisWorker(
            db_session_factory, notifier=notifier, warning_threshold=0.8, critical_threshold=0.9
        )
        assert await worker.tick() == 0


class TestStatisticsRollupWorker:
    async def test_tick_rolls_up_current_window_idempotently(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        window_end = now().replace(minute=0, second=0, microsecond=0)
        cluster = await repos.clusters.create(
            _cluster(
                organization_id,
                registered_at=window_end - timedelta(minutes=30),
                health_status=ClusterHealthStatus.HEALTHY,
                node_count=5,
            )
        )
        assert cluster.id is not None

        worker = StatisticsRollupWorker(db_session_factory, window_hours=1)
        rolled_first = await worker.tick()
        rolled_second = await worker.tick()
        assert rolled_first == rolled_second == 1

    async def test_tick_no_organizations_rolls_up_nothing(self, db_session_factory) -> None:
        worker = StatisticsRollupWorker(db_session_factory)
        assert await worker.tick() == 0
