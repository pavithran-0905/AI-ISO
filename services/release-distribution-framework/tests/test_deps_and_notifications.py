"""Tests for FastAPI dependency wiring and the notification layer."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from shared_core.exceptions.authentication import AuthenticationError
from shared_core.exceptions.authorization import AuthorizationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.events.domain_events import ReleaseCreatedEvent, ReleasePublishedEvent
from app.services.audit import AuditService
from app.services.bundle import Repositories
from app.services.channels import ReleaseChannelConfigService
from app.services.notifications import NotifyingPublisher, ReleaseNotifier
from app.services.promotions import ReleasePromotionService
from app.services.releases import ReleaseVersionService
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
        roles = await deps.get_roles({"roles": ["Admin", " release_admin "]})
        assert roles == frozenset({"admin", "release_admin"})

    async def test_get_roles_defaults_to_empty(self) -> None:
        roles = await deps.get_roles({})
        assert roles == frozenset()


class TestRequireAdministrator:
    async def test_allows_administrator_role(self) -> None:
        await deps.require_administrator(frozenset({"release_admin"}))

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

    def test_get_release_channel_config_service(
        self, db_session: AsyncSession, organization_id: uuid.UUID
    ) -> None:
        repos = deps.get_repos(db_session, organization_id)
        service = deps.get_release_channel_config_service(repos)
        assert isinstance(service, ReleaseChannelConfigService)

    def test_get_release_version_service(
        self, db_session: AsyncSession, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        repos = deps.get_repos(db_session, organization_id)
        notifier = ReleaseNotifier(manager=None)  # type: ignore[arg-type]
        service = deps.get_release_version_service(repos, publisher, notifier)
        assert isinstance(service, ReleaseVersionService)

    def test_get_release_promotion_service(
        self, db_session: AsyncSession, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        repos = deps.get_repos(db_session, organization_id)
        notifier = ReleaseNotifier(manager=None)  # type: ignore[arg-type]
        service = deps.get_release_promotion_service(repos, publisher, notifier)
        assert isinstance(service, ReleasePromotionService)


class _FakeNotificationManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestReleaseNotifier:
    async def test_notify_new_release(self) -> None:
        manager = _FakeNotificationManager()
        notifier = ReleaseNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_new_release(version_label="1.0.0", channel_type="stable")
        assert manager.calls[0]["variables"] == {"version_label": "1.0.0", "channel_type": "stable"}

    async def test_notify_security_release(self) -> None:
        manager = _FakeNotificationManager()
        notifier = ReleaseNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_security_release(version_label="1.0.1")
        assert manager.calls[0]["variables"] == {"version_label": "1.0.1"}

    async def test_notify_lts_release(self) -> None:
        manager = _FakeNotificationManager()
        notifier = ReleaseNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_lts_release(
            version_label="2.0.0", support_ends_at="2030-01-01T00:00:00+00:00"
        )
        assert manager.calls[0]["variables"]["version_label"] == "2.0.0"

    async def test_notify_promotion_complete(self) -> None:
        manager = _FakeNotificationManager()
        notifier = ReleaseNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_promotion_complete(version_label="1.0.0", to_channel="stable")
        assert manager.calls[0]["variables"] == {"version_label": "1.0.0", "to_channel": "stable"}

    async def test_notify_release_failure(self) -> None:
        manager = _FakeNotificationManager()
        notifier = ReleaseNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_release_failure(version_label="1.0.0", error_message="compile error")
        assert manager.calls[0]["variables"] == {
            "version_label": "1.0.0",
            "error_message": "compile error",
        }

    async def test_notify_eol_warning(self) -> None:
        manager = _FakeNotificationManager()
        notifier = ReleaseNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_eol_warning(
            version_label="1.0.0", eol_date="2027-01-01T00:00:00+00:00"
        )
        assert manager.calls[0]["variables"]["version_label"] == "1.0.0"

    async def test_notify_patch_available(self) -> None:
        manager = _FakeNotificationManager()
        notifier = ReleaseNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_patch_available(version_label="2.0.1")
        assert manager.calls[0]["variables"] == {"version_label": "2.0.1"}

    async def test_notify_critical_update(self) -> None:
        manager = _FakeNotificationManager()
        notifier = ReleaseNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_critical_update(version_label="2.0.1")
        assert manager.calls[0]["variables"] == {"version_label": "2.0.1"}


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        inner = RecordingPublisher()
        manager = _FakeNotificationManager()
        publisher = NotifyingPublisher(inner, ReleaseNotifier(manager))  # type: ignore[arg-type]
        event = ReleaseCreatedEvent(
            source_service="release-distribution-framework",
            organization_id=uuid.uuid4(),
            payload={"release_version_id": "x", "version_label": "1.0.0"},
        )
        await publisher(event)
        assert inner.events == [event]
        assert manager.calls == []

    async def test_notifies_only_on_security_release_published(self) -> None:
        inner = RecordingPublisher()
        manager = _FakeNotificationManager()
        publisher = NotifyingPublisher(inner, ReleaseNotifier(manager))  # type: ignore[arg-type]
        event = ReleasePublishedEvent(
            source_service="release-distribution-framework",
            organization_id=uuid.uuid4(),
            payload={
                "release_version_id": "x",
                "version_label": "3.0.0",
                "is_security_release": True,
            },
        )
        await publisher(event)
        assert inner.events == [event]
        assert manager.calls[0]["variables"] == {"version_label": "3.0.0"}

    async def test_does_not_notify_on_non_security_release_published(self) -> None:
        inner = RecordingPublisher()
        manager = _FakeNotificationManager()
        publisher = NotifyingPublisher(inner, ReleaseNotifier(manager))  # type: ignore[arg-type]
        event = ReleasePublishedEvent(
            source_service="release-distribution-framework",
            organization_id=uuid.uuid4(),
            payload={
                "release_version_id": "x",
                "version_label": "3.0.1",
                "is_security_release": False,
            },
        )
        await publisher(event)
        assert inner.events == [event]
        assert manager.calls == []
