"""Tests for FastAPI dependency wiring and the notification layer."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from shared_core.exceptions.authentication import AuthenticationError
from shared_core.exceptions.authorization import AuthorizationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.events.domain_events import BenchmarkStartedEvent, RegressionDetectedEvent
from app.services.audit import AuditService
from app.services.benchmark_definitions import BenchmarkSuiteService
from app.services.benchmark_execution import BenchmarkRunService
from app.services.bundle import Repositories
from app.services.notifications import BenchmarkNotifier, NotifyingPublisher
from tests.conftest import RecordingPublisher


class TestTokenClaimHelpers:
    async def test_get_current_user_id_returns_subject(self) -> None:
        user_id = await deps.get_current_user_id({"sub": "user-123"})
        assert user_id == "user-123"

    async def test_get_current_user_id_rejects_missing_subject(self) -> None:
        with pytest.raises(AuthenticationError):
            await deps.get_current_user_id({})

    async def test_get_organization_id_parses_valid_uuid(self) -> None:
        org_id = uuid.uuid4()
        result = await deps.get_organization_id({"organization_id": str(org_id)})
        assert result == org_id

    async def test_get_organization_id_rejects_missing_claim(self) -> None:
        with pytest.raises(AuthorizationError):
            await deps.get_organization_id({})

    async def test_get_organization_id_rejects_malformed_claim(self) -> None:
        with pytest.raises(AuthorizationError):
            await deps.get_organization_id({"organization_id": "not-a-uuid"})

    async def test_get_roles_normalizes_single_string(self) -> None:
        roles = await deps.get_roles({"roles": "Admin"})
        assert roles == frozenset({"admin"})

    async def test_get_roles_normalizes_list(self) -> None:
        roles = await deps.get_roles({"roles": ["Admin", " performance_admin "]})
        assert roles == frozenset({"admin", "performance_admin"})

    async def test_get_roles_defaults_to_empty(self) -> None:
        roles = await deps.get_roles({})
        assert roles == frozenset()


class TestRequireAdministrator:
    async def test_allows_administrator_role(self) -> None:
        await deps.require_administrator(frozenset({"performance_admin"}))

    async def test_denies_non_administrator_role(self) -> None:
        with pytest.raises(AuthorizationError):
            await deps.require_administrator(frozenset({"member"}))

    async def test_denies_no_roles(self) -> None:
        with pytest.raises(AuthorizationError):
            await deps.require_administrator(frozenset())


class TestRepositoryAndServiceProviders:
    def test_get_repos_scopes_to_organization(
        self, db_session: AsyncSession, organization_id: uuid.UUID
    ) -> None:
        repos = deps.get_repos(db_session, organization_id)
        assert isinstance(repos, Repositories)

    def test_get_audit_service(self, db_session: AsyncSession, organization_id: uuid.UUID) -> None:
        repos = deps.get_repos(db_session, organization_id)
        service = deps.get_audit_service(repos)
        assert isinstance(service, AuditService)

    def test_get_benchmark_suite_service(
        self, db_session: AsyncSession, organization_id: uuid.UUID
    ) -> None:
        repos = deps.get_repos(db_session, organization_id)
        service = deps.get_benchmark_suite_service(repos)
        assert isinstance(service, BenchmarkSuiteService)

    def test_get_benchmark_run_service(
        self, db_session: AsyncSession, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        repos = deps.get_repos(db_session, organization_id)
        notifier = BenchmarkNotifier(manager=None)  # type: ignore[arg-type]
        service = deps.get_benchmark_run_service(repos, publisher, notifier)
        assert isinstance(service, BenchmarkRunService)


class _FakeNotificationManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestBenchmarkNotifier:
    async def test_notify_performance_regression(self) -> None:
        manager = _FakeNotificationManager()
        notifier = BenchmarkNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_performance_regression(metric_name="latency_ms", severity="critical")
        assert manager.calls[0]["variables"] == {
            "metric_name": "latency_ms",
            "severity": "critical",
        }

    async def test_notify_capacity_warning(self) -> None:
        manager = _FakeNotificationManager()
        notifier = BenchmarkNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_capacity_warning(
            resource_name="db-storage", projected_value=95.0, threshold_value=90.0
        )
        assert manager.calls[0]["variables"]["resource_name"] == "db-storage"

    async def test_notify_slo_violation(self) -> None:
        manager = _FakeNotificationManager()
        notifier = BenchmarkNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_slo_violation(
            slo_name="api-availability", actual_value=99.0, target_value=99.9
        )
        assert manager.calls[0]["variables"]["slo_name"] == "api-availability"

    async def test_notify_benchmark_completed(self) -> None:
        manager = _FakeNotificationManager()
        notifier = BenchmarkNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_benchmark_completed(
            benchmark_suite_name="api-suite", status="succeeded"
        )
        assert manager.calls[0]["variables"] == {
            "benchmark_suite_name": "api-suite",
            "status": "succeeded",
        }

    async def test_notify_optimization_available(self) -> None:
        manager = _FakeNotificationManager()
        notifier = BenchmarkNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_optimization_available(title="optimize query", impact_score=40.0)
        assert manager.calls[0]["variables"]["title"] == "optimize query"

    async def test_notify_infrastructure_bottleneck(self) -> None:
        manager = _FakeNotificationManager()
        notifier = BenchmarkNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_infrastructure_bottleneck(
            resource_type="cpu", utilization_percent=95.0
        )
        assert manager.calls[0]["variables"] == {
            "resource_type": "cpu",
            "utilization_percent": 95.0,
        }

    async def test_notify_scaling_recommendation(self) -> None:
        manager = _FakeNotificationManager()
        notifier = BenchmarkNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_scaling_recommendation(title="scale up", impact_score=80.0)
        assert manager.calls[0]["variables"]["title"] == "scale up"


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        inner = RecordingPublisher()
        manager = _FakeNotificationManager()
        publisher = NotifyingPublisher(inner, BenchmarkNotifier(manager))  # type: ignore[arg-type]
        event = BenchmarkStartedEvent(
            source_service="performance-benchmark-framework",
            organization_id=uuid.uuid4(),
            payload={"benchmark_run_id": "x"},
        )
        await publisher(event)
        assert inner.events == [event]
        assert manager.calls == []

    async def test_notifies_only_on_regression_detected(self) -> None:
        inner = RecordingPublisher()
        manager = _FakeNotificationManager()
        publisher = NotifyingPublisher(inner, BenchmarkNotifier(manager))  # type: ignore[arg-type]
        event = RegressionDetectedEvent(
            source_service="performance-benchmark-framework",
            organization_id=uuid.uuid4(),
            payload={
                "performance_regression_id": "x",
                "metric_name": "latency_ms",
                "severity": "critical",
            },
        )
        await publisher(event)
        assert inner.events == [event]
        assert manager.calls[0]["variables"] == {
            "metric_name": "latency_ms",
            "severity": "critical",
        }
