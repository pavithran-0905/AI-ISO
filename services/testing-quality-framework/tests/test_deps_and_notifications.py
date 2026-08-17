"""Tests for FastAPI dependency wiring and the notification layer.

See ``test_repositories.py``'s own module docstring for why every
model/enum starting with ``Test`` is imported under an alias here too
(not that any collide in this particular file, but the convention is
applied uniformly across every test module in this service).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from shared_core.exceptions.authentication import AuthenticationError
from shared_core.exceptions.authorization import AuthorizationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.events.domain_events import QualityGateFailedEvent
from app.events.domain_events import TestStartedEvent as StartedEvent
from app.services.audit import AuditService
from app.services.bundle import Repositories
from app.services.notifications import NotifyingPublisher, QaNotifier
from app.services.quality_gates import QualityGateService
from app.services.test_execution import TestRunService as RunService
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
        roles = await deps.get_roles({"roles": ["Admin", " qa_admin "]})
        assert roles == frozenset({"admin", "qa_admin"})

    async def test_get_roles_defaults_to_empty(self) -> None:
        roles = await deps.get_roles({})
        assert roles == frozenset()


class TestRequireAdministrator:
    async def test_allows_administrator_role(self) -> None:
        await deps.require_administrator(frozenset({"qa_admin"}))

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

    def test_get_test_run_service(
        self, db_session: AsyncSession, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        repos = deps.get_repos(db_session, organization_id)
        service = deps.get_test_run_service(repos, publisher)
        assert isinstance(service, RunService)

    def test_get_quality_gate_service(
        self, db_session: AsyncSession, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        repos = deps.get_repos(db_session, organization_id)
        service = deps.get_quality_gate_service(repos, publisher)
        assert isinstance(service, QualityGateService)


class _FakeNotificationManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestQaNotifier:
    async def test_notify_pipeline_failed(self) -> None:
        manager = _FakeNotificationManager()
        notifier = QaNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_pipeline_failed(pipeline_name="build", reason="timeout")
        assert manager.calls[0]["variables"] == {"pipeline_name": "build", "reason": "timeout"}

    async def test_notify_coverage_dropped(self) -> None:
        manager = _FakeNotificationManager()
        notifier = QaNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_coverage_dropped(coverage_type="unit", current=80.0, previous=90.0)
        assert manager.calls[0]["variables"]["current"] == 80.0

    async def test_notify_performance_regression(self) -> None:
        manager = _FakeNotificationManager()
        notifier = QaNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_performance_regression(
            performance_type="latency", detail="150ms vs 100ms"
        )
        assert manager.calls[0]["variables"]["performance_type"] == "latency"

    async def test_notify_security_issue(self) -> None:
        manager = _FakeNotificationManager()
        notifier = QaNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_security_issue(security_type="owasp_top_10", findings_count=5)
        assert manager.calls[0]["variables"]["findings_count"] == 5

    async def test_notify_quality_gate_failed(self) -> None:
        manager = _FakeNotificationManager()
        notifier = QaNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_quality_gate_failed(gate_name="coverage-gate")
        assert manager.calls[0]["variables"] == {"gate_name": "coverage-gate"}

    async def test_notify_flaky_test_detected(self) -> None:
        manager = _FakeNotificationManager()
        notifier = QaNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_flaky_test_detected(test_case_name="test_login")
        assert manager.calls[0]["variables"] == {"test_case_name": "test_login"}

    async def test_notify_benchmark_regression(self) -> None:
        manager = _FakeNotificationManager()
        notifier = QaNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_benchmark_regression(
            benchmark_name="throughput", detail="800 vs 1000"
        )
        assert manager.calls[0]["variables"]["benchmark_name"] == "throughput"


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        inner = RecordingPublisher()
        manager = _FakeNotificationManager()
        publisher = NotifyingPublisher(inner, QaNotifier(manager))  # type: ignore[arg-type]
        event = StartedEvent(
            source_service="testing-quality-framework",
            organization_id=uuid.uuid4(),
            payload={"test_run_id": "x"},
        )
        await publisher(event)
        assert inner.events == [event]
        assert manager.calls == []

    async def test_notifies_only_on_quality_gate_failed(self) -> None:
        inner = RecordingPublisher()
        manager = _FakeNotificationManager()
        publisher = NotifyingPublisher(inner, QaNotifier(manager))  # type: ignore[arg-type]
        event = QualityGateFailedEvent(
            source_service="testing-quality-framework",
            organization_id=uuid.uuid4(),
            payload={"quality_gate_id": "x", "gate_type": "minimum_coverage"},
        )
        await publisher(event)
        assert inner.events == [event]
        assert manager.calls[0]["variables"] == {"gate_name": "minimum_coverage"}
