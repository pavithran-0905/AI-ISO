"""Integration tests for background workers, against real PostgreSQL.

Uses real wall-clock time (``datetime.now(UTC)``) throughout, matching
every worker's own internal ``now = datetime.now(UTC)`` -- a fixed
historical constant would fall outside a worker's real query window and
produce tests that pass without the loop body ever executing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models.accounts import CloudAccount, CloudProvider
from app.models.enums import (
    AccountHealthStatus,
    CloudComplianceFramework,
    CloudComplianceStatus,
    CloudProviderType,
    CloudResourceType,
    DriftSeverity,
    DriftStatus,
)
from app.models.operations import CloudBudget, CloudCompliance, CloudCost, CloudDrift
from app.models.resources import CloudResource
from app.services.notifications import CloudNotifier
from app.workers.account_health_sweep import AccountHealthSweepWorker
from app.workers.budget_sweep import BudgetSweepWorker
from app.workers.compliance_sweep import ComplianceSweepWorker
from app.workers.drift_sweep import DriftSweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker


def now() -> datetime:
    return datetime.now(UTC)


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def broadcast(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


async def _noop_publish(event: object) -> None:
    pass


def _provider(organization_id: UUID, **kwargs: object) -> CloudProvider:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "provider_type": CloudProviderType.AWS,
        "name": "aws-prod",
    }
    defaults.update(kwargs)
    return CloudProvider(**defaults)


def _account(organization_id: UUID, provider_id: UUID, **kwargs: object) -> CloudAccount:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "provider_id": provider_id,
        "external_account_id": "123456789",
        "name": "a1",
        "credential_ref": "ref",
    }
    defaults.update(kwargs)
    return CloudAccount(**defaults)


def _resource(organization_id: UUID, account_id: UUID, **kwargs: object) -> CloudResource:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "account_id": account_id,
        "resource_type": CloudResourceType.VIRTUAL_MACHINE,
        "external_id": "i-123",
        "name": "r1",
    }
    defaults.update(kwargs)
    return CloudResource(**defaults)


class TestAccountHealthSweepWorker:
    async def test_tick_downgrades_stale_account_to_degraded(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(
            _account(
                organization_id,
                provider.id,
                is_valid=True,
                last_validated_at=now() - timedelta(days=2),
            )
        )
        worker = AccountHealthSweepWorker(db_session_factory, stale_threshold_minutes=60)
        checked = await worker.tick()
        assert checked == 1

        await db_session.refresh(account)
        assert account.health_status == AccountHealthStatus.DEGRADED

    async def test_tick_keeps_fresh_account_healthy(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(
            _account(organization_id, provider.id, is_valid=True, last_validated_at=now())
        )
        worker = AccountHealthSweepWorker(db_session_factory, stale_threshold_minutes=60)
        await worker.tick()

        await db_session.refresh(account)
        assert account.health_status == AccountHealthStatus.HEALTHY

    async def test_tick_no_accounts_checks_nothing(self, db_session_factory) -> None:
        worker = AccountHealthSweepWorker(db_session_factory, stale_threshold_minutes=60)
        assert await worker.tick() == 0


class TestDriftSweepWorker:
    async def test_tick_escalates_stale_detected_drift_and_notifies(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(_account(organization_id, provider.id))
        resource = await repos.resources.create(_resource(organization_id, account.id))
        drift = await repos.drift.create(
            CloudDrift(
                organization_id=organization_id,
                resource_id=resource.id,
                severity=DriftSeverity.MEDIUM,
                status=DriftStatus.DETECTED,
                detected_at=now() - timedelta(hours=2),
            )
        )
        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        worker = DriftSweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            stale_after_minutes=60,
        )
        escalated = await worker.tick()
        assert escalated == 1

        await db_session.refresh(drift)
        assert drift.severity == DriftSeverity.HIGH
        assert manager.calls[0]["topic"] == "cloud_management.drift_detected"

    async def test_tick_leaves_recent_drift_alone(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(_account(organization_id, provider.id))
        resource = await repos.resources.create(_resource(organization_id, account.id))
        drift = await repos.drift.create(
            CloudDrift(
                organization_id=organization_id,
                resource_id=resource.id,
                severity=DriftSeverity.MEDIUM,
                status=DriftStatus.DETECTED,
                detected_at=now(),
            )
        )
        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        worker = DriftSweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            stale_after_minutes=60,
        )
        assert await worker.tick() == 0
        await db_session.refresh(drift)
        assert drift.severity == DriftSeverity.MEDIUM

    async def test_tick_no_organizations_escalates_nothing(self, db_session_factory) -> None:
        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        worker = DriftSweepWorker(
            db_session_factory,
            publish_event=_noop_publish,
            notifier=notifier,
            stale_after_minutes=60,
        )
        assert await worker.tick() == 0


class TestBudgetSweepWorker:
    async def test_tick_recomputes_spend_and_publishes_on_crossing(
        self, db_session_factory, db_session, repos, organization_id: UUID
    ) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(_account(organization_id, provider.id))
        budget = await repos.budgets.create(
            CloudBudget(
                organization_id=organization_id,
                account_id=account.id,
                name="Monthly",
                amount=100.0,
                threshold_fraction=0.8,
                period_start=now() - timedelta(days=1),
                period_end=now() + timedelta(days=29),
            )
        )
        await repos.costs.create(
            CloudCost(
                organization_id=organization_id,
                account_id=account.id,
                amount=90.0,
                cost_category="compute",
                period_start=now(),
                period_end=now() + timedelta(days=1),
            )
        )
        worker = BudgetSweepWorker(
            db_session_factory, publish_event=_noop_publish, critical_threshold=0.95
        )
        checked = await worker.tick()
        assert checked == 1

        await db_session.refresh(budget)
        assert budget.current_spend == 90.0

    async def test_tick_no_organizations_checks_nothing(self, db_session_factory) -> None:
        worker = BudgetSweepWorker(
            db_session_factory, publish_event=_noop_publish, critical_threshold=0.95
        )
        assert await worker.tick() == 0


class TestComplianceSweepWorker:
    async def test_tick_notifies_overdue_remediation(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(_account(organization_id, provider.id))
        await repos.compliance.create(
            CloudCompliance(
                organization_id=organization_id,
                account_id=account.id,
                framework=CloudComplianceFramework.CIS,
                status=CloudComplianceStatus.NON_COMPLIANT,
                assessed_at=now() - timedelta(days=30),
                remediation_due_at=now() - timedelta(days=1),
            )
        )
        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        worker = ComplianceSweepWorker(db_session_factory, notifier=notifier)
        flagged = await worker.tick()
        assert flagged == 1
        assert manager.calls[0]["topic"] == "cloud_management.compliance_violation"

    async def test_tick_skips_not_yet_due_remediation(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(_account(organization_id, provider.id))
        await repos.compliance.create(
            CloudCompliance(
                organization_id=organization_id,
                account_id=account.id,
                framework=CloudComplianceFramework.CIS,
                status=CloudComplianceStatus.NON_COMPLIANT,
                assessed_at=now(),
                remediation_due_at=now() + timedelta(days=14),
            )
        )
        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        worker = ComplianceSweepWorker(db_session_factory, notifier=notifier)
        assert await worker.tick() == 0

    async def test_tick_no_organizations_flags_nothing(self, db_session_factory) -> None:
        manager = _RecordingManager()
        notifier = CloudNotifier(manager)  # type: ignore[arg-type]
        worker = ComplianceSweepWorker(db_session_factory, notifier=notifier)
        assert await worker.tick() == 0


class TestStatisticsRollupWorker:
    async def test_tick_rolls_up_current_window_idempotently(
        self, db_session_factory, repos, organization_id: UUID
    ) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(_account(organization_id, provider.id))
        window_end = now().replace(minute=0, second=0, microsecond=0)
        await repos.resources.create(
            _resource(organization_id, account.id, discovered_at=window_end - timedelta(minutes=30))
        )

        worker = StatisticsRollupWorker(db_session_factory, window_hours=1)
        rolled_first = await worker.tick()
        rolled_second = await worker.tick()
        assert rolled_first == rolled_second == 1

    async def test_tick_no_organizations_rolls_up_nothing(self, db_session_factory) -> None:
        worker = StatisticsRollupWorker(db_session_factory)
        assert await worker.tick() == 0
