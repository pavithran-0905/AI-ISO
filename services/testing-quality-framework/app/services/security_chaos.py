"""Security test result and chaos experiment result recording.

Publishes ``SecurityScanCompleted``/``ChaosTestCompleted`` on every
recorded result. Notifies Security Issue directly on a non-``PASSED``
security classification.
"""

from __future__ import annotations

from uuid import UUID

from app.chaos.engine import classify_chaos_result
from app.events.domain_events import ChaosTestCompletedEvent, SecurityScanCompletedEvent
from app.models.enums import ChaosFaultType, CheckResultStatus, SecurityTestType
from app.models.security_chaos import ChaosResult, SecurityResult
from app.repositories.security_chaos import ChaosResultRepository, SecurityResultRepository
from app.security.engine import classify_security_result
from app.services.notifications import QaNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "testing-quality-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class SecurityService:
    def __init__(
        self,
        repo: SecurityResultRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: QaNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def record(
        self,
        organization_id: UUID,
        *,
        security_type: SecurityTestType,
        findings_count: int,
        test_run_id: UUID | None = None,
        detail: str = "",
    ) -> SecurityResult:
        status = classify_security_result(findings_count)
        result = await self._repo.create(
            SecurityResult(
                organization_id=organization_id,
                test_run_id=test_run_id,
                security_type=security_type,
                status=status,
                findings_count=findings_count,
                detail=detail,
            )
        )
        await self._publish(
            SecurityScanCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "security_result_id": str(result.id),
                    "security_type": security_type.value,
                    "status": status.value,
                },
            )
        )
        if status != CheckResultStatus.PASSED and self._notifier is not None:
            await self._notifier.notify_security_issue(
                security_type=security_type.value, findings_count=findings_count
            )
        return result


class ChaosService:
    def __init__(
        self, repo: ChaosResultRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def record(
        self,
        organization_id: UUID,
        *,
        fault_type: ChaosFaultType,
        recovery_time_seconds: float,
        target_seconds: float,
        test_run_id: UUID | None = None,
        detail: str = "",
    ) -> ChaosResult:
        status = classify_chaos_result(recovery_time_seconds, target_seconds=target_seconds)
        result = await self._repo.create(
            ChaosResult(
                organization_id=organization_id,
                test_run_id=test_run_id,
                fault_type=fault_type,
                recovery_time_seconds=recovery_time_seconds,
                status=status,
                detail=detail,
            )
        )
        await self._publish(
            ChaosTestCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "chaos_result_id": str(result.id),
                    "fault_type": fault_type.value,
                    "status": status.value,
                },
            )
        )
        return result


__all__ = ["ChaosService", "SecurityService"]
