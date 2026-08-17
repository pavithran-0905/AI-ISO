"""Tests for FastAPI dependency wiring and the notification layer."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from shared_core.exceptions.authentication import AuthenticationError
from shared_core.exceptions.authorization import AuthorizationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.events.domain_events import HardeningStartedEvent, VulnerabilityDetectedEvent
from app.services.audit import AuditService
from app.services.bundle import Repositories
from app.services.certification import ProductionCertificationService
from app.services.hardening_definitions import HardeningProfileService
from app.services.hardening_execution import HardeningRunService
from app.services.notifications import HardeningNotifier, NotifyingPublisher
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
        roles = await deps.get_roles({"roles": ["Admin", " hardening_admin "]})
        assert roles == frozenset({"admin", "hardening_admin"})

    async def test_get_roles_defaults_to_empty(self) -> None:
        roles = await deps.get_roles({})
        assert roles == frozenset()


class TestRequireAdministrator:
    async def test_allows_administrator_role(self) -> None:
        await deps.require_administrator(frozenset({"hardening_admin"}))

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

    def test_get_hardening_profile_service(
        self, db_session: AsyncSession, organization_id: uuid.UUID
    ) -> None:
        repos = deps.get_repos(db_session, organization_id)
        service = deps.get_hardening_profile_service(repos)
        assert isinstance(service, HardeningProfileService)

    def test_get_hardening_run_service(
        self, db_session: AsyncSession, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        repos = deps.get_repos(db_session, organization_id)
        notifier = HardeningNotifier(manager=None)  # type: ignore[arg-type]
        service = deps.get_hardening_run_service(repos, publisher, notifier)
        assert isinstance(service, HardeningRunService)

    def test_get_production_certification_service(
        self, db_session: AsyncSession, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        repos = deps.get_repos(db_session, organization_id)
        notifier = HardeningNotifier(manager=None)  # type: ignore[arg-type]
        service = deps.get_production_certification_service(repos, publisher, notifier)
        assert isinstance(service, ProductionCertificationService)


class _FakeNotificationManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestHardeningNotifier:
    async def test_notify_critical_vulnerability(self) -> None:
        manager = _FakeNotificationManager()
        notifier = HardeningNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_critical_vulnerability(
            package_name="left-pad", cve_id="CVE-2024-0001"
        )
        assert manager.calls[0]["variables"] == {
            "package_name": "left-pad",
            "cve_id": "CVE-2024-0001",
        }

    async def test_notify_certificate_expiring(self) -> None:
        manager = _FakeNotificationManager()
        notifier = HardeningNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_certificate_expiring(subject="api.example.com", days_remaining=10.0)
        assert manager.calls[0]["variables"]["subject"] == "api.example.com"

    async def test_notify_hardening_failed(self) -> None:
        manager = _FakeNotificationManager()
        notifier = HardeningNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_hardening_failed(
            hardening_profile_name="linux-cis", error_message="timed out"
        )
        assert manager.calls[0]["variables"] == {
            "hardening_profile_name": "linux-cis",
            "error_message": "timed out",
        }

    async def test_notify_certification_granted(self) -> None:
        manager = _FakeNotificationManager()
        notifier = HardeningNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_certification_granted(name="core-platform", risk_score=10.0)
        assert manager.calls[0]["variables"]["name"] == "core-platform"

    async def test_notify_certification_expired(self) -> None:
        manager = _FakeNotificationManager()
        notifier = HardeningNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_certification_expired(name="core-platform")
        assert manager.calls[0]["variables"] == {"name": "core-platform"}

    async def test_notify_compliance_failure(self) -> None:
        manager = _FakeNotificationManager()
        notifier = HardeningNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_compliance_failure(framework="soc2", control_id="CC6.1")
        assert manager.calls[0]["variables"] == {"framework": "soc2", "control_id": "CC6.1"}

    async def test_notify_operational_risk(self) -> None:
        manager = _FakeNotificationManager()
        notifier = HardeningNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_operational_risk(
            check_type="monitoring", detail="no alert configured"
        )
        assert manager.calls[0]["variables"]["check_type"] == "monitoring"


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        inner = RecordingPublisher()
        manager = _FakeNotificationManager()
        publisher = NotifyingPublisher(inner, HardeningNotifier(manager))  # type: ignore[arg-type]
        event = HardeningStartedEvent(
            source_service="production-hardening-framework",
            organization_id=uuid.uuid4(),
            payload={"hardening_run_id": "x"},
        )
        await publisher(event)
        assert inner.events == [event]
        assert manager.calls == []

    async def test_notifies_only_on_critical_vulnerability(self) -> None:
        inner = RecordingPublisher()
        manager = _FakeNotificationManager()
        publisher = NotifyingPublisher(inner, HardeningNotifier(manager))  # type: ignore[arg-type]
        event = VulnerabilityDetectedEvent(
            source_service="production-hardening-framework",
            organization_id=uuid.uuid4(),
            payload={
                "vulnerability_scan_id": "x",
                "severity": "critical",
                "package_name": "left-pad",
                "cve_id": "CVE-2024-0001",
            },
        )
        await publisher(event)
        assert inner.events == [event]
        assert manager.calls[0]["variables"] == {
            "package_name": "left-pad",
            "cve_id": "CVE-2024-0001",
        }

    async def test_does_not_notify_on_non_critical_vulnerability(self) -> None:
        inner = RecordingPublisher()
        manager = _FakeNotificationManager()
        publisher = NotifyingPublisher(inner, HardeningNotifier(manager))  # type: ignore[arg-type]
        event = VulnerabilityDetectedEvent(
            source_service="production-hardening-framework",
            organization_id=uuid.uuid4(),
            payload={
                "vulnerability_scan_id": "x",
                "severity": "low",
                "package_name": "left-pad",
                "cve_id": "",
            },
        )
        await publisher(event)
        assert manager.calls == []
