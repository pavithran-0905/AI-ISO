"""Pre-flight infrastructure readiness checks.

This process can only genuinely probe the infrastructure it already
holds a live connection to (its own database, its own cache) --
everything else docs/075 names (CPU, memory, OS, DNS, firewall,
SELinux, and so on) would require an installed host agent this build
does not implement. ``record_result`` is therefore the primary path,
the same caller-reported-outcome pattern
``services/developer-portal-service``'s ``WebhookTestService`` uses for
webhook calls it likewise cannot make from inside a request handler:
the caller (an installer agent, a CLI, or this process's own real
database/cache probe) reports what it found, and this service records
and aggregates it.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import ValidationCompletedEvent
from app.models.enums import CheckResultStatus, PreflightCheckType
from app.models.validation import PreflightResult
from app.preflight.engine import aggregate_check_results
from app.repositories.validation import PreflightResultRepository
from app.services.notifications import DeploymentNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "installation-deployment-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class PreflightService:
    def __init__(
        self,
        repo: PreflightResultRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: DeploymentNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def record_result(
        self,
        organization_id: UUID,
        *,
        check_type: PreflightCheckType,
        status: CheckResultStatus,
        detail: str = "",
        installation_session_id: UUID | None = None,
        now: datetime,
    ) -> PreflightResult:
        result = await self._repo.create(
            PreflightResult(
                organization_id=organization_id,
                installation_session_id=installation_session_id,
                check_type=check_type,
                status=status,
                detail=detail,
                checked_at=now,
            )
        )
        await self._publish(
            ValidationCompletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"check_type": check_type.value, "status": status.value},
            )
        )
        if status == CheckResultStatus.FAILED and self._notifier is not None:
            await self._notifier.notify_validation_failed(
                check_type=check_type.value, detail=detail
            )
        return result

    async def compute_overall(self, installation_session_id: UUID) -> CheckResultStatus:
        """The worst-of-N outcome across every check recorded for a
        session so far."""
        results = await self._repo.list_for_session(installation_session_id)
        return aggregate_check_results(CheckResultStatus(result.status) for result in results)


__all__ = ["PreflightService"]
