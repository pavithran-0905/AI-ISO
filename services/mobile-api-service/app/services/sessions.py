"""Mobile session lifecycle: login, logout, and expiry.

A login is refused -- never silently downgraded -- for a revoked
device or a device whose integrity score fails its own threshold.
Every outcome, success or refusal, is audited; only a refusal is also
notified (Security Alert) and published as ``MobileLoginFailed``, since
there is no session row a failed attempt could otherwise be traced
through.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.authentication.engine import is_session_expired
from app.events.domain_events import MobileLoginFailedEvent, MobileLoginSucceededEvent
from app.models.devices import MobileDevice, MobileSession
from app.models.enums import DeviceTrustStatus, MobileAuditAction, MobileAuthMethod, SessionStatus
from app.repositories.devices import MobileSessionRepository
from app.security.engine import compute_integrity_risk_score, is_device_integrity_acceptable
from app.services.audit import AuditService
from app.services.notifications import MobileNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "mobile-api-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class LoginRefusalReason:
    DEVICE_REVOKED = "device_revoked"
    DEVICE_INTEGRITY = "device_integrity"


class LoginRefusedError(Exception):
    def __init__(self, reason: str, *, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


class SessionService:
    def __init__(
        self,
        repo: MobileSessionRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
        notifier: MobileNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit
        self._notifier = notifier

    async def login(
        self,
        device: MobileDevice,
        *,
        user_id: str,
        auth_method: MobileAuthMethod,
        now: datetime,
        session_max_age_minutes: int,
        integrity_threshold: int = 50,
    ) -> MobileSession:
        """Establish a new session for *device*, raising
        :class:`LoginRefusedError` if the device is revoked or fails
        its own integrity check."""
        if DeviceTrustStatus(device.trust_status) == DeviceTrustStatus.REVOKED:
            await self._refuse(
                device,
                reason=LoginRefusalReason.DEVICE_REVOKED,
                detail=f"Device {device.device_identifier!r} has been revoked.",
                now=now,
            )

        score = compute_integrity_risk_score(
            is_jailbroken=device.is_jailbroken, is_rooted=device.is_rooted
        )
        if not is_device_integrity_acceptable(score, threshold=integrity_threshold):
            if self._notifier is not None:
                await self._notifier.notify_security_alert(
                    device_identifier=device.device_identifier,
                    reason=f"integrity risk score {score} exceeds threshold {integrity_threshold}",
                )
            await self._refuse(
                device,
                reason=LoginRefusalReason.DEVICE_INTEGRITY,
                detail=f"Device {device.device_identifier!r} failed its own integrity check.",
                now=now,
            )

        is_new_device = not await self._repo.has_prior_session(
            device.organization_id, device_id=device.id
        )
        session = await self._repo.create(
            MobileSession(
                organization_id=device.organization_id,
                device_id=device.id,
                user_id=user_id,
                auth_method=auth_method,
                is_new_device=is_new_device,
                issued_at=now,
                expires_at=now + timedelta(minutes=session_max_age_minutes),
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id=device.organization_id,
                action=MobileAuditAction.AUTHENTICATION,
                entity_type="mobile_session",
                entity_id=session.id,
                occurred_at=now,
                actor_id=user_id,
                summary=f"User {user_id!r} authenticated on device {device.device_identifier!r}.",
            )
        await self._publish(
            MobileLoginSucceededEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=device.organization_id,
                payload={
                    "device_id": str(device.id),
                    "device_identifier": device.device_identifier,
                    "platform": (
                        device.platform.value
                        if hasattr(device.platform, "value")
                        else device.platform
                    ),
                    "user_id": user_id,
                    "auth_method": auth_method.value,
                    "is_new_device": is_new_device,
                },
            )
        )
        return session

    async def _refuse(
        self, device: MobileDevice, *, reason: str, detail: str, now: datetime
    ) -> None:
        if self._audit is not None:
            await self._audit.record(
                organization_id=device.organization_id,
                action=MobileAuditAction.AUTHENTICATION,
                entity_type="mobile_device",
                entity_id=device.id,
                occurred_at=now,
                summary=f"Login refused for device {device.device_identifier!r}: {reason}.",
            )
        await self._publish(
            MobileLoginFailedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=device.organization_id,
                payload={"device_identifier": device.device_identifier, "reason": reason},
            )
        )
        raise LoginRefusedError(reason, detail=detail)

    async def logout(self, session: MobileSession, *, now: datetime) -> MobileSession:
        session.status = SessionStatus.REVOKED
        session.revoked_at = now
        return await self._repo.update(session)

    async def expire(self, session: MobileSession) -> MobileSession:
        session.status = SessionStatus.EXPIRED
        return await self._repo.update(session)

    @staticmethod
    def is_expired(session: MobileSession, *, now: datetime) -> bool:
        return is_session_expired(expires_at=session.expires_at, now=now)


__all__ = ["LoginRefusalReason", "LoginRefusedError", "SessionService"]
